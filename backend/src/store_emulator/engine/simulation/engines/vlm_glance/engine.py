"""Vision-language shopper engine.

Planning is the rule-based planner (pattern draw, category-matched planned purchases,
planned route). Impulse decisions are made by a VLM that *looks at* the shelves the
shopper passes:

1. Perceive the planned route with the visibility model and rank rack faces by how
   well they are seen.
2. For each of the `max_glances` best-seen faces, the shopper looks (always, or with
   probability look_base × visibility × pattern factor under the "gated" policy).
3. The face is rendered as an image (names, prices, promotion ribbons, numbered
   badges) and the VLM, role-playing the persona with its mood, basket and money left,
   names the product most likely to catch the eye and rates the temptation 0–10.
4. A seeded draw turns that rating into an impulse BROWSE+BUY visit
   (P = buy_scale × interest/10 × level weight), a browse-only stop, or nothing — subject
   to the same budget and item caps as the rule engine. The VLM decides *what* tempts the
   shopper; buy_scale (calibratable) decides *how often* temptation becomes a purchase.

Designed for small local VLMs on CPU (llama.cpp server, OpenAI-compatible API) but
works with any LiteLLM vision model. Every call is seeded per (customer, rack face)
and cacheable, so paired layout comparisons stay exact.
"""

import logging
import random
import threading
from collections import Counter
from dataclasses import asdict, dataclass

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.rack import Rack
from store_emulator.domain.types import Face, PathFinder, TokenUsage, stable_seed
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.perception import render_face
from store_emulator.engine.routing.route_builder import build_journey, perceive_products

from ..rule_based import (
    PATTERN_IMPULSE_FACTOR,
    ImpulseOutcome,
    RuleBasedEngine,
    ShopperPlan,
)
from .prompt import SYSTEM_PROMPT, ShelfGlance, resolve, user_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GlanceRecord:
    persona_id: str
    rack: str
    face: str
    visibility: float
    product: str
    number: int
    interest: int
    reason: str
    resolved_sku: str | None
    resolved_by: str      # none | name | number | invalid | error
    level: int | None
    outcome: str          # buy | look | skip | error


class VLMGlanceEngine(RuleBasedEngine):
    engine_type = "vlm_glance"

    def __init__(self, llm: LiteLLMClient, pathfinder: PathFinder, config: SimulationConfig):
        super().__init__(pathfinder, config)
        self._llm = llm
        self._log_lock = threading.Lock()
        self.glance_log: list[GlanceRecord] = []

    def reset_usage(self) -> None:
        self._llm.reset_usage()
        with self._log_lock:
            self.glance_log = []

    def get_usage(self) -> TokenUsage:
        return self._llm.get_usage()

    async def _impulse(self, context: PerCustomerContext, plan: ShopperPlan) -> ImpulseOutcome:
        cfg = self._config
        vcfg = cfg.engines.vlm_glance
        max_items = cfg.engines.rule_based.max_impulse_items
        store, persona = context.store, context.persona
        out = ImpulseOutcome()
        factor = PATTERN_IMPULSE_FACTOR.get(plan.pattern.id, 1.0)
        if factor <= 0 or vcfg.max_glances == 0:
            return out

        journey = build_journey(store, plan.planned, self._pathfinder, cfg.block_move_sec)
        faces: dict[tuple[str, Face], tuple[Rack, Face, float]] = {}
        for seen in perceive_products(store, journey, cfg.perception):
            key = (seen.rack.id, seen.slot.face)
            if key not in faces or seen.visibility > faces[key][2]:
                faces[key] = (seen.rack, seen.slot.face, seen.visibility)
        ranked = sorted(faces.values(), key=lambda f: (-f[2], f[0].id, f[1].value))[:vcfg.max_glances]

        calls = buys = looks = invalid = errors = 0
        for rack, face, visibility in ranked:
            if out.buys >= max_items and out.looks >= max_items:
                break
            # Per-face random streams: whether a face is looked at and how a temptation resolves
            # do not depend on earlier answers, so two models (or two layouts) see the same
            # glances and draws — paired comparisons stay paired.
            look_u = random.Random(stable_seed(context.seed, "vlm_glance", "look", rack.id, face.value)).random()
            buy_u = random.Random(stable_seed(context.seed, "vlm_glance", "buy", rack.id, face.value)).random()
            look_p = min(1.0, vcfg.look_base * visibility * factor)
            if vcfg.glance_policy == "gated" and look_u >= look_p:
                continue
            marks_rng = random.Random(stable_seed(context.seed, "marks", rack.id, face.value)) if vcfg.shuffle_marks else None
            view = render_face(rack, face, currency=cfg.currency, width=vcfg.image_width, rng=marks_rng)
            if not view.items:
                continue
            prompt = user_prompt(
                persona, context.cue, plan.pattern, view,
                basket=self._basket_names(context, plan),
                money_left=None if persona.budget_max <= 0 else int(plan.budget * plan.tolerance) - plan.spend,
                currency=cfg.currency,
            )
            calls += 1
            try:
                glance = await self._llm.generate_structured_with_image_async(
                    ShelfGlance, SYSTEM_PROMPT, prompt, view.data_url(),
                    seed=stable_seed(context.seed, "vlm", rack.id, face.value), max_retries=1,
                )
            except Exception as e:  # noqa: BLE001 — one failed glance must not fail the customer
                errors += 1
                logger.warning(f"[vlm_glance] {persona.id} {rack.rack_name}/{face.value}: {type(e).__name__}: {e}")
                self._record(GlanceRecord(persona.id, rack.rack_name, face.value, visibility, "", 0, 0, "",
                                          None, "error", None, "error"))
                continue

            hit, how = resolve(view, glance)
            outcome = "skip"
            if hit is None:
                invalid += how == "invalid"
            elif hit.item.sku not in plan.chosen and glance.interest > 0:
                weight = cfg.perception.level_attention.get(hit.slot.level, 0.7) if vcfg.weight_by_level else 1.0
                tempted = min(1.0, glance.interest / 10 * weight)
                why = f"spots {hit.item.name}" + (f" — {glance.reason}" if glance.reason else "")
                buy_now = buy_u < vcfg.buy_scale * tempted and self.can_buy_more(plan, out.buys, hit.item.price)
                if buy_now and self.add_impulse_buy(store, plan, out, rack, hit.slot, hit.item, why):
                    outcome = "buy"
                    buys += 1
                elif (not buy_now and buy_u < tempted and out.looks < max_items
                      and self.add_impulse_look(store, plan, out, rack, hit.slot, why)):
                    outcome = "look"
                    looks += 1
            self._record(GlanceRecord(
                persona.id, rack.rack_name, face.value, visibility, glance.product, glance.number, glance.interest,
                glance.reason, hit.item.sku if hit else None, how, hit.slot.level if hit else None, outcome,
            ))

        out.trace = {"vlm_calls": calls, "vlm_buys": buys, "vlm_looks": looks,
                     "vlm_invalid": invalid, "vlm_errors": errors}
        return out

    def _basket_names(self, context: PerCustomerContext, plan: ShopperPlan) -> list[str]:
        names: list[str] = []
        for rack in context.store.product_racks:
            for slot in rack.slots:
                for item in slot.items:
                    if item.sku in plan.chosen and item.name not in names:
                        names.append(item.name)
        return names

    def metadata(self) -> dict[str, object]:
        """Every glance of the run plus summary counts (saved as output/vlm_glance_meta.json)."""
        with self._log_lock:
            log = list(self.glance_log)
        answered = [g for g in log if g.resolved_by != "error"]
        picked = [g for g in answered if g.resolved_sku is not None]
        vlm = self._config.engines.vlm_glance
        return {
            "model": vlm.llm.model,
            "api_base": vlm.llm.api_base,
            "glance_policy": vlm.glance_policy,
            "max_glances": vlm.max_glances,
            "image_width": vlm.image_width,
            "glances": len(log),
            "errors": len(log) - len(answered),
            "noticed_rate": round(len(picked) / len(answered), 4) if answered else 0.0,
            "mean_interest": round(sum(g.interest for g in picked) / len(picked), 2) if picked else 0.0,
            "interest_hist": {str(k): v for k, v in sorted(Counter(g.interest for g in answered).items())},
            "buy_scale": vlm.buy_scale,
            "resolved_by": dict(Counter(g.resolved_by for g in log)),
            "outcomes": dict(Counter(g.outcome for g in log)),
            "picked_level": {str(k): v for k, v in sorted(Counter(g.level for g in picked if g.level).items())},
            "records": [asdict(g) for g in log],
        }

    def _record(self, record: GlanceRecord) -> None:
        with self._log_lock:
            self.glance_log.append(record)
