"""Vision-language shopper engine.

Planning (plan_policy "vlm", the default): the route style (behavior pattern), budget and caps
are drawn as in the rule engine; then ONE VLM call at the entrance decides whether the shopper
goes in, their mission and up to max_plan_items planned purchases, from the persona (including
its neighborhood context), mood, time, the day's situation, budget, a text store directory and
(entrance_image) the directory map. Named items are resolved to SKUs (see planning.py); failed
calls fall back to the rule plan for that customer. Because the model read the situation, the
scenario's numeric demand and walk-out multipliers are not applied to a VLM plan. With
plan_policy "rule" the rule-based planner is used unchanged.

Impulse decisions are made by a VLM that *looks at* the shelves the shopper passes:

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
from store_emulator.domain.engine import EngineDecision, PerCustomerContext
from store_emulator.domain.rack import Rack
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face, PathFinder, TokenUsage, stable_seed
from store_emulator.engine.llm_router import EnsembleLLMClient, SimLLM
from store_emulator.engine.perception import (
    ShelfView,
    category_label,
    directory_text,
    render_face,
    render_store_map,
    store_directory,
)
from store_emulator.engine.routing.route_builder import build_journey, perceive_products

from ..rule_based import (
    PATTERN_IMPULSE_FACTOR,
    ImpulseOutcome,
    RuleBasedEngine,
    ShopperPlan,
)
from .planning import PlanMatch, PlanRecord, match_plan_item, pick_candidate
from .prompt import (
    SYSTEM_PROMPT,
    EntryDecision,
    PlannedItem,
    ShelfGlance,
    combine_plan_votes,
    combine_votes,
    entry_decision_model,
    plan_system_prompt,
    plan_user_prompt,
    resolve,
    user_prompt,
)

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
    model: str = ""       # ensemble member that answered (mixture) or "vote"
    agreement: float | None = None  # vote mode: share of members that named the winner
    votes: tuple[tuple[str, str, int], ...] = ()  # vote mode: (member, product, interest)


class VLMGlanceEngine(RuleBasedEngine):
    engine_type = "vlm_glance"

    def __init__(self, llm: SimLLM, pathfinder: PathFinder, config: SimulationConfig):
        super().__init__(pathfinder, config)
        self._llm = llm
        self._log_lock = threading.Lock()
        self.glance_log: list[GlanceRecord] = []
        self.plan_log: list[PlanRecord] = []
        # Directory text and map image of the current store (one store per run).
        self._entrance: tuple[Store, str, str] | None = None

    def reset_usage(self) -> None:
        self._llm.reset_usage()
        with self._log_lock:
            self.glance_log = []
            self.plan_log = []

    async def decide_actions(self, context: PerCustomerContext) -> EngineDecision:
        if self._config.engines.vlm_glance.plan_policy == "vlm":
            plan = await self._vlm_plan(context)
        else:
            plan = self._plan(context)
        impulse = await self._impulse(context, plan) if plan.entered else ImpulseOutcome()
        return self._finish(context, plan, impulse)

    # ── planning ──────────────────────────────────────────────────────────

    def _entrance_view(self, store: Store) -> tuple[str, str]:
        """(directory text, map image data URL or "") of `store`, cached for the run's store."""
        if self._entrance is None or self._entrance[0] is not store:
            vcfg = self._config.engines.vlm_glance
            text = directory_text(store_directory(store), self._config.currency)
            image = render_store_map(store, width=vcfg.image_width).data_url() if vcfg.entrance_image else ""
            self._entrance = (store, text, image)
        return self._entrance[1], self._entrance[2]

    async def _vlm_plan(self, context: PerCustomerContext) -> ShopperPlan:
        cfg = self._config
        vcfg = cfg.engines.vlm_glance
        store, persona = context.store, context.persona
        plan, middle = self._begin_plan(context)
        directory, image = self._entrance_view(store)
        max_items = min(vcfg.max_plan_items, plan.pattern.max_products)
        system = plan_system_prompt(max_items=max_items, image=bool(image))
        prompt = plan_user_prompt(
            persona, context.cue, plan.pattern, day=context.day, hour=context.arrival_hour,
            situation=context.situation, budget=persona.budget_max if persona.budget_max > 0 else None,
            currency=cfg.currency, directory=directory,
        )
        decision, model, agreement, error = await self._ask_plan(
            entry_decision_model(max_items), system, prompt, image or None, context,
        )
        if decision is None:
            logger.warning(f"[vlm_glance] plan for {persona.id} failed, using the rule plan: {error[:200]}")
            fallback = self._plan(context)
            fallback.trace = {**fallback.trace, "plan_source": "fallback", "plan_error": error[:200]}
            self._record_plan(PlanRecord(persona.id, fallback.pattern.id, "fallback", True, "", "", (),
                                         model=model, error=error[:300]))
            return fallback

        source = "vote" if agreement is not None else "vlm"
        named = tuple((i.category, i.product, i.qty) for i in decision.items)
        if not decision.enter:
            plan.walk_out, plan.entered = True, False
            plan.trace = {"plan_source": source, "entered": False, "mission": decision.mission}
            self._record_plan(PlanRecord(persona.id, plan.pattern.id, source, False, decision.mission,
                                         decision.reason, named, model=model, agreement=agreement))
            return self.close_plan(store, plan, [])

        catalog = self._catalog_for(store)
        limit = int(plan.budget * plan.tolerance)
        resolved: list[tuple[str, str, str, str]] = []
        for i, item in enumerate(decision.items):
            label = item.product or item.category
            if i >= max_items:
                resolved.append((label, "", "cap", ""))
                continue
            match = match_plan_item(item, catalog)
            entry = pick_candidate(
                match, chosen=plan.chosen, remaining=limit - plan.spend,
                attention=cfg.perception.level_attention, promo_multiplier=cfg.engines.rule_based.promo_multiplier,
                rng=plan.rng,
            ) if match.candidates else None
            if entry is None:
                how = match.how if not match.candidates else "duplicate"
                if how == "unresolved":
                    logger.info(f"[vlm_glance] {persona.id}: could not resolve planned item {label!r}")
                resolved.append((label, "", how, ""))
                continue
            rack, slot, sku_item, _, _ = entry
            quantity = min(item.qty, cfg.max_quantity_per_line, max(0, (limit - plan.spend) // max(1, sku_item.price)))
            if quantity < 1:
                resolved.append((label, sku_item.sku, "over_budget", category_label(rack)))
                continue
            if not self.add_planned_buy(store, plan, middle, rack, slot, sku_item, f"came for {label}", quantity=quantity):
                resolved.append((label, sku_item.sku, "unreachable", category_label(rack)))
                continue
            resolved.append((label, sku_item.sku, match.how, category_label(rack)))
        plan.trace = {"plan_source": source, "entered": True, "mission": decision.mission}
        self._record_plan(PlanRecord(persona.id, plan.pattern.id, source, True, decision.mission, decision.reason,
                                     named, tuple(resolved), model=model, agreement=agreement))
        return self.close_plan(store, plan, middle)

    async def _ask_plan(
        self, schema: type[EntryDecision], system: str, prompt: str, image: str | None, context: PerCustomerContext,
    ) -> tuple[EntryDecision | None, str, float | None, str]:
        """(decision, answering model, agreement, error) for one entrance plan."""
        seed = stable_seed(context.seed, "vlm-plan")
        route = context.persona.id
        max_tokens = self._config.engines.vlm_glance.plan_max_tokens
        if isinstance(self._llm, EnsembleLLMClient) and self._llm.mode == "vote":
            answers = await self._llm.ask_all_with_image(
                schema, system, prompt, image, seed=seed, route=route, max_retries=1, max_tokens=max_tokens,
            )
            ok = [(a.member, a.answer) for a in answers if a.answer is not None]
            if not ok:
                return None, "vote", None, "; ".join(a.error for a in answers)
            catalog = self._catalog_for(context.store)

            def key(item: PlannedItem) -> str:
                match: PlanMatch = match_plan_item(item, catalog)
                return match.key or f"text:{(item.product or item.category).strip().lower()}"

            combined, agreement = combine_plan_votes(list(ok), key)
            return combined, "vote", agreement, ""
        model = self._llm.member_for(route).name if isinstance(self._llm, EnsembleLLMClient) else ""
        try:
            if image is None:
                decision = await self._llm.generate_structured_async(
                    schema, system, prompt, seed=seed, route=route, max_retries=1, max_tokens=max_tokens,
                )
            else:
                decision = await self._llm.generate_structured_with_image_async(
                    schema, system, prompt, image, seed=seed, route=route, max_retries=1, max_tokens=max_tokens,
                )
        except Exception as e:  # noqa: BLE001 — a failed plan falls back to the rule plan
            return None, model, None, f"{type(e).__name__}: {e}"
        return decision, model, None, ""

    def _record_plan(self, record: PlanRecord) -> None:
        with self._log_lock:
            self.plan_log.append(record)

    # ── impulse ───────────────────────────────────────────────────────────

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
                situation=context.situation,
            )
            calls += 1
            glance, model, agreement, votes, error = await self._ask(view, prompt, context, rack, face.value)
            if glance is None:
                errors += 1
                logger.warning(f"[vlm_glance] {persona.id} {rack.rack_name}/{face.value}: {error}")
                self._record(GlanceRecord(persona.id, rack.rack_name, face.value, visibility, "", 0, 0, "",
                                          None, "error", None, "error", model, None, votes))
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
                model, agreement, votes,
            ))

        out.trace = {"vlm_calls": calls, "vlm_buys": buys, "vlm_looks": looks,
                     "vlm_invalid": invalid, "vlm_errors": errors}
        return out

    async def _ask(
        self, view: ShelfView, prompt: str, context: PerCustomerContext, rack: Rack, face: str,
    ) -> tuple[ShelfGlance | None, str, float | None, tuple[tuple[str, str, int], ...], str]:
        """(glance, answering model, agreement, votes, error) for one shelf glance."""
        seed = stable_seed(context.seed, "vlm", rack.id, face)
        route = context.persona.id
        if isinstance(self._llm, EnsembleLLMClient) and self._llm.mode == "vote":
            answers = await self._llm.ask_all_with_image(
                ShelfGlance, SYSTEM_PROMPT, prompt, view.data_url(), seed=seed, route=route, max_retries=1,
            )
            votes = tuple((a.member, a.answer.product if a.answer else "", a.answer.interest if a.answer else -1)
                          for a in answers)
            ok = [(a.member, a.answer) for a in answers if a.answer is not None]
            if not ok:
                return None, "vote", None, votes, "; ".join(a.error for a in answers)
            combined, agreement = combine_votes(view, ok)
            return combined, "vote", agreement, votes, ""
        model = self._llm.member_for(route).name if isinstance(self._llm, EnsembleLLMClient) else ""
        try:
            glance = await self._llm.generate_structured_with_image_async(
                ShelfGlance, SYSTEM_PROMPT, prompt, view.data_url(), seed=seed, route=route, max_retries=1,
            )
        except Exception as e:  # noqa: BLE001 — one failed glance must not fail the customer
            return None, model, None, (), f"{type(e).__name__}: {e}"
        return glance, model, None, (), ""

    def _basket_names(self, context: PerCustomerContext, plan: ShopperPlan) -> list[str]:
        names: list[str] = []
        for rack in context.store.product_racks:
            for slot in rack.slots:
                for item in slot.items:
                    if item.sku in plan.chosen and item.name not in names:
                        names.append(item.name)
        return names

    def plan_summary(self) -> dict[str, object]:
        """Counts over the run's entrance plans (empty under plan_policy "rule")."""
        with self._log_lock:
            plans = list(self.plan_log)
        asked = [p for p in plans if p.source != "fallback"]
        entered = [p for p in asked if p.enter]
        named = [r for p in entered for r in p.resolved if r[2] != "cap"]
        bought = [r for r in named if r[1] and r[2] not in ("over_budget", "unreachable", "duplicate")]
        categories = Counter(r[3] for r in bought if r[3])
        by_model: dict[str, dict[str, object]] = {}
        for name in sorted({p.model for p in plans if p.model}):
            mine = [p for p in plans if p.model == name]
            mine_asked = [p for p in mine if p.source != "fallback"]
            by_model[name] = {
                "plans": len(mine), "errors": len(mine) - len(mine_asked),
                "enter_rate": round(sum(p.enter for p in mine_asked) / len(mine_asked), 4) if mine_asked else None,
                "mean_items": round(sum(len(p.items) for p in mine_asked if p.enter)
                                    / max(1, sum(1 for p in mine_asked if p.enter)), 3),
            }
        return {
            "plans": len(plans),
            "plan_errors": len(plans) - len(asked),
            "enter_rate": round(len(entered) / len(asked), 4) if asked else None,
            "mean_items_named": round(sum(len(p.items) for p in entered) / len(entered), 3) if entered else 0.0,
            "mean_items_bought": round(len(bought) / len(entered), 3) if entered else 0.0,
            "resolution_rate": round(sum(1 for r in named if r[1]) / len(named), 4) if named else None,
            "resolved_by": dict(Counter(r[2] for r in named)),
            "top_categories": [[label, n] for label, n in categories.most_common(8)],
            "by_model": by_model,
            "mean_agreement": round(sum(p.agreement for p in asked if p.agreement is not None)
                                    / max(1, sum(1 for p in asked if p.agreement is not None)), 3)
            if any(p.agreement is not None for p in asked) else None,
        }

    def metadata(self) -> dict[str, object]:
        """Every plan and glance of the run plus summary counts (saved as output/vlm_glance_meta.json)."""
        with self._log_lock:
            log = list(self.glance_log)
            plans = list(self.plan_log)
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
            "by_model": {
                name: {"glances": sum(1 for g in log if g.model == name),
                       "picks": sum(1 for g in picked if g.model == name),
                       "mean_interest": round(sum(g.interest for g in picked if g.model == name)
                                              / max(1, sum(1 for g in picked if g.model == name)), 2)}
                for name in sorted({g.model for g in log if g.model})
            },
            "mean_agreement": round(sum(g.agreement for g in answered if g.agreement is not None)
                                    / max(1, sum(1 for g in answered if g.agreement is not None)), 3)
            if any(g.agreement is not None for g in answered) else None,
            "ensemble": self._llm.metadata() if isinstance(self._llm, EnsembleLLMClient) else None,
            "plan_policy": vlm.plan_policy,
            "entrance_image": vlm.entrance_image,
            "max_plan_items": vlm.max_plan_items,
            "planning": self.plan_summary() if vlm.plan_policy == "vlm" else None,
            "records": [asdict(g) for g in log],
            "plan_records": [asdict(p) for p in plans],
        }

    def _record(self, record: GlanceRecord) -> None:
        with self._log_lock:
            self.glance_log.append(record)
