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

from instructor.core.exceptions import IncompleteOutputException, InstructorRetryException

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import EngineDecision, PerCustomerContext
from store_emulator.domain.rack import Rack
from store_emulator.domain.store import Store
from store_emulator.domain.types import (
    Action,
    Face,
    PathFinder,
    TokenUsage,
    stable_seed,
)
from store_emulator.engine.llm_router import EnsembleLLMClient, SimLLM
from store_emulator.engine.perception.product_images import ProductImageLoader
from store_emulator.engine.perception import (
    ShelfView,
    category_label,
    directory_text,
    render_face,
    render_store_map,
    store_directory,
)
from store_emulator.engine.perception.shelf_photo import (
    face_key,
    load_shelf_photo,
    photo_chart_view,
)
from store_emulator.engine.routing.route_builder import build_journey, perceive_products
from store_emulator.engine.routing.store_lookup import resolve_buy_placement
from store_emulator.engine.scenario import words_categories

from ..rule_based import (
    PATTERN_IMPULSE_FACTOR,
    ImpulseOutcome,
    RuleBasedEngine,
    ShopperPlan,
)
from .planning import PlanMatch, PlanRecord, match_plan_item, pick_candidate
from .prompt import (
    PLAN_ITEMS_LIMIT,
    EntryDecision,
    PlannedItem,
    ShelfGlance,
    combine_plan_votes,
    combine_votes,
    entry_decision_model,
    glance_system_prompt,
    plan_system_prompt,
    plan_user_prompt,
    resolve,
    user_prompt,
)

logger = logging.getLogger(__name__)

_STOCKED_SHOWN = 8  # categories named as "still stocked at home" in the entrance prompt


def narrate_entry(plan: ShopperPlan, mission: str, reason: str, *, entered: bool) -> ShopperPlan:
    """The model's own words at the door: its mission (and why) becomes the thought of the ENTER step, so
    journeys, speech bubbles and interviews show what this shopper came for, not a blank step."""
    mission, reason = mission.strip(), reason.strip()
    if not mission and not reason:
        return plan
    if not entered:
        text = f"turns away: {reason or mission}"
    elif reason and mission and reason.casefold() not in mission.casefold():
        text = f"{mission} ({reason})"
    else:
        text = mission or reason
    for action in plan.planned:
        if action.action == Action.ENTER:
            action.description = text[:240]
            break
    return plan


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
    view: str = "chart"   # what the glance showed: chart | photo_chart (the 3D photo above the chart)


def _truncated_output(error: BaseException) -> bool:
    # Wrapper text includes generated answers and earlier failures. Only the
    # terminal completion's typed truncation warrants a larger output budget.
    if isinstance(error, InstructorRetryException) and error.failed_attempts:
        error = error.failed_attempts[-1].exception
    return isinstance(error, IncompleteOutputException)


class VLMGlanceEngine(RuleBasedEngine):
    engine_type = "vlm_glance"

    def __init__(self, llm: SimLLM, pathfinder: PathFinder, config: SimulationConfig,
                 image_loader: ProductImageLoader | None = None):
        super().__init__(pathfinder, config)
        self._llm = llm
        self._image_loader = image_loader
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
        if vcfg.directory_shuffle or vcfg.directory_examples != 3 or vcfg.directory_prices:  # else the cached one
            directory = directory_text(store_directory(
                store, examples=vcfg.directory_examples,
                rng=random.Random(stable_seed(context.seed, "directory")) if vcfg.directory_shuffle else None,
            ), cfg.currency, item_prices=vcfg.directory_prices)
        # A trip of known size plans that many (up to the schema limit), whatever the default cap.
        max_items = (min(PLAN_ITEMS_LIMIT, persona.basket_size) if persona.basket_size > 0
                     else min(vcfg.max_plan_items, plan.pattern.max_products))
        system = plan_system_prompt(max_items=max_items, image=bool(image), store_type=store.type)
        needs = self._needs(context)
        prompt = plan_user_prompt(
            persona, context.cue, plan.pattern, day=context.day, hour=context.arrival_hour,
            situation=context.situation, budget=persona.budget_max if persona.budget_max > 0 else None,
            currency=cfg.currency, directory=directory, needs=needs,
        )
        decision, model, agreement, error = await self._ask_plan(
            entry_decision_model(max_items), system, prompt, image or None, context,
        )
        if decision is None:
            with self._log_lock:
                answered = any(p.source != "fallback" for p in self.plan_log)
            if not answered:
                # Until the model has answered once in this run, a failure is the model's (a key turned down, no
                # credit, a server that is down), not this shopper's: the shopper fails and is tried again, and a run
                # whose model never answers stops with the error rather than finishing as a vision run of rule-based
                # shoppers.
                raise RuntimeError(f"the vision model did not answer: {error[:300]}")
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
            return narrate_entry(self.close_plan(store, plan, []), decision.mission, decision.reason, entered=False)

        catalog = self._catalog_for(store)
        limit = int(plan.budget * plan.tolerance) if plan.budget is not None and plan.tolerance is not None else None
        plan.spend_limit = limit
        resolved: list[tuple[str, str, str, str]] = []
        # A trip of known breadth (Persona.basket_kinds, e.g. from a past receipt) keeps the model's
        # first categories in its priority order; asked for n items, models otherwise spread them over
        # n categories (1.04 products per category against 1.43 on real receipts).
        kinds = persona.basket_kinds if persona.basket_size > 0 else 0
        kept: list[str] = []
        items = list(decision.items)
        if kinds and persona.category_rates:
            # Under the breadth limit, what the household has run out of keeps its place, then the
            # categories it buys most often: a model that lists an extra category first otherwise
            # pushed a needed staple out of the trip, and kept categories the household never buys
            # (18 % of planned products, 8 % on real receipts).
            needed = {n.split(" (they usually take", 1)[0].casefold() for n in (needs[0] if needs else [])}
            rates = {k.casefold(): v for k, v in persona.category_rates.items()}

            def priority(it: PlannedItem) -> tuple[bool, float]:
                m = match_plan_item(it, catalog)
                cat = category_label(m.candidates[0][0]).casefold() if m.candidates else ""
                return (cat not in needed, -rates.get(cat, 0.0))

            items = sorted(items, key=priority)
        for i, item in enumerate(items):
            label = item.product or item.category
            if i >= max_items:
                resolved.append((label, "", "cap", ""))
                continue
            match = match_plan_item(item, catalog)
            entry = pick_candidate(
                match, chosen=plan.chosen, remaining=limit - plan.spend if limit is not None else None,
                attention=cfg.perception.level_attention, promo_multiplier=cfg.engines.rule_based.promo_multiplier,
                rng=plan.rng,
            ) if match.candidates else None
            if entry is None:
                how = match.how
                if match.candidates:
                    how = "unavailable" if any(e[2].sku not in plan.chosen for e in match.candidates) else "duplicate"
                if how == "unresolved":
                    logger.info(f"[vlm_glance] {persona.id}: could not resolve planned item {label!r}")
                resolved.append((label, "", how, ""))
                continue
            rack, slot, sku_item, _, _ = entry
            if kinds and category_label(rack) not in kept and len(kept) >= kinds:
                resolved.append((label, sku_item.sku, "breadth", category_label(rack)))
                continue
            quantity = min(item.qty, cfg.max_quantity_per_line)
            if limit is not None and sku_item.price > 0:
                quantity = min(quantity, max(0, (limit - plan.spend) // sku_item.price))
            if quantity < 1:
                resolved.append((label, sku_item.sku, "over_budget", category_label(rack)))
                continue
            if not self.add_planned_buy(store, plan, middle, rack, slot, sku_item, f"came for {label}", quantity=quantity):
                resolved.append((label, sku_item.sku, "unreachable", category_label(rack)))
                continue
            resolved.append((label, sku_item.sku, match.how, category_label(rack)))
            if category_label(rack) not in kept:
                kept.append(category_label(rack))
        if kinds and kept:
            # Fill the trip to its size with more products of the kept categories, drawn as the rule
            # planner draws them (shelf attention, price, the shopper's usual products).
            usual = frozenset(p.lower() for p in persona.usual_products)
            before = len(plan.buys)
            self._fill_to_size(store, plan, middle, kept, min(max_items, persona.basket_size), usual, kinds, kept,
                               spend_limit=limit)
            for buy in plan.buys[before:]:
                placement = resolve_buy_placement(store, target=buy.target, face=buy.face, sku=buy.product_sku,
                                                 block=buy.product_block, level=buy.product_level)
                category = category_label(placement[0]) if placement is not None else ""
                resolved.append(("(same category)", buy.product_sku, "breadth_fill", category))
        plan.trace = {"plan_source": source, "entered": True, "mission": decision.mission}
        self._record_plan(PlanRecord(persona.id, plan.pattern.id, source, True, decision.mission, decision.reason,
                                     named, tuple(resolved), model=model, agreement=agreement))
        return narrate_entry(self.close_plan(store, plan, middle), decision.mission, decision.reason, entered=True)

    def _needs(self, context: PerCustomerContext) -> tuple[list[str], list[str]] | None:
        """Which usual categories the household has run out of this trip: one seeded draw per category
        at its rate (Persona.category_rates), most frequent first, times the situation's measured need
        ratio for that kind of product (summer: more water; a big match: more beer) and, when the format's
        profile has one, the part of the day's (evening: more beer and ice cream). The model then
        plans the trip; the draw only sets what is missing at home, as a seeded draw sets impulse
        purchases."""
        rates = context.persona.category_rates
        if not rates:
            return None
        rng = random.Random(stable_seed(context.seed, "needs"))
        out: list[str] = []
        stocked: list[str] = []
        fx, hour = self._fx, context.arrival_hour
        for category, rate in sorted(rates.items(), key=lambda kv: (-kv[1], kv[0])):
            p = rate
            if fx.need or fx.hour_need:
                cats = words_categories(category)
                m = (fx.need_for(cats) if fx.need else 1.0) * (fx.hour_need_for(hour, cats) if fx.hour_need else 1.0)
                p = min(0.98, rate * m)
            (out if rng.random() < p else stocked).append(category)
        usual = self._usual_by_category(context.store, context.persona.usual_products)
        # What the household takes in a category it needs: without it the planner chooses there like a
        # stranger, whenever the household's favourite is not among the first usual products it is shown.
        out = [f"{c} (they usually take {' or '.join(usual[c][:2])})" if usual.get(c) else c for c in out]
        return out, stocked[:_STOCKED_SHOWN]

    def _usual_by_category(self, store: Store, products: list[str]) -> dict[str, list[str]]:
        """The persona's usual products grouped by the rack (category) that holds them, in their order."""
        if not products:
            return {}
        racks_of: dict[str, set[str]] = {}
        for rack, _, item, _, _ in self._catalog_for(store):
            if rack.rack_name:
                racks_of.setdefault(item.name.lower(), set()).add(rack.rack_name)
        out: dict[str, list[str]] = {}
        for name in products:
            for cat in sorted(racks_of.get(name.lower(), set())):
                if name not in out.setdefault(cat, []):
                    out[cat].append(name)
        return out

    async def _ask_plan(
        self, schema: type[EntryDecision], system: str, prompt: str, image: str | None, context: PerCustomerContext,
    ) -> tuple[EntryDecision | None, str, float | None, str]:
        """(decision, answering model, agreement, error) for one entrance plan."""
        seed = stable_seed(context.seed, "vlm-plan")
        route = context.persona.id
        # A long shopping list must fit. Measured on Claude Haiku and Qwen Flash: ~60 tokens per item
        # (category, full product name, qty, JSON punctuation) plus ~150 for mission and reason; at
        # 36/item a third of supermarket plans were cut off and silently fell back to the rule plan.
        max_tokens = max(self._config.engines.vlm_glance.plan_max_tokens, 200 + 70 * schema.items_limit)
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
        error = ""
        for budget in (max_tokens, 2 * max_tokens):  # a cut-off answer gets one retry with twice the room
            try:
                if image is None:
                    decision = await self._llm.generate_structured_async(
                        schema, system, prompt, seed=seed, route=route, max_retries=1, max_tokens=budget,
                    )
                else:
                    decision = await self._llm.generate_structured_with_image_async(
                        schema, system, prompt, image, seed=seed, route=route, max_retries=1, max_tokens=budget,
                    )
            except Exception as e:  # noqa: BLE001 — a failed plan falls back to the rule plan
                error = f"{type(e).__name__}: {e}"
                if _truncated_output(e):
                    continue
                return None, model, None, error
            return decision, model, None, ""
        return None, model, None, error

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
        if vcfg.glance_order == "shuffle":
            def order(f: tuple[Rack, Face, float]) -> tuple[float, float]:
                return (-f[2], random.Random(stable_seed(context.seed, "glance_order", f[0].id, f[1].value)).random())
            ranked = sorted(faces.values(), key=order)[:vcfg.max_glances]
        else:
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
            view = render_face(rack, face, currency=cfg.currency, width=vcfg.image_width, rng=marks_rng,
                               image_loader=self._image_loader)
            if not view.items:
                continue
            shown = "chart"
            if vcfg.shelf_view == "photo_chart":
                # A face without a stored photo (rendered before an edit, or never) is shown as the chart alone.
                photo = load_shelf_photo(vcfg.shelf_views_dir, face_key(rack, face, cfg.currency))
                if photo is not None:
                    view = photo_chart_view(view, photo)
                    shown = "photo_chart"
            prompt = user_prompt(
                persona, context.cue, plan.pattern, view,
                basket=self._basket_names(context, plan),
                money_left=None if plan.budget is None or plan.tolerance is None
                else int(plan.budget * plan.tolerance) - plan.spend,
                currency=cfg.currency,
                situation=context.situation,
            )
            calls += 1
            glance, model, agreement, votes, error = await self._ask(
                view, prompt, context, rack, face.value, photo=shown == "photo_chart")
            if glance is None:
                errors += 1
                logger.warning(f"[vlm_glance] {persona.id} {rack.rack_name}/{face.value}: {error}")
                self._record(GlanceRecord(persona.id, rack.rack_name, face.value, visibility, "", 0, 0, "",
                                          None, "error", None, "error", model, None, votes, view=shown))
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
                model, agreement, votes, view=shown,
            ))

        out.trace = {"vlm_calls": calls, "vlm_buys": buys, "vlm_looks": looks,
                     "vlm_invalid": invalid, "vlm_errors": errors}
        return out

    async def _ask(
        self, view: ShelfView, prompt: str, context: PerCustomerContext, rack: Rack, face: str, *, photo: bool = False,
    ) -> tuple[ShelfGlance | None, str, float | None, tuple[tuple[str, str, int], ...], str]:
        """(glance, answering model, agreement, votes, error) for one shelf glance."""
        seed = stable_seed(context.seed, "vlm", rack.id, face)
        route = context.persona.id
        system = glance_system_prompt(context.store.type, photo=photo)
        if isinstance(self._llm, EnsembleLLMClient) and self._llm.mode == "vote":
            answers = await self._llm.ask_all_with_image(
                ShelfGlance, system, prompt, view.data_url(), seed=seed, route=route, max_retries=1,
            )
            votes = tuple((a.member, a.answer.product if a.answer else "", a.answer.interest if a.answer else -1)
                          for a in answers)
            ok = [(a.member, a.answer) for a in answers if a.answer is not None]
            if not ok:
                return None, "vote", None, votes, "; ".join(a.error for a in answers)
            combined, agreement = combine_votes(view, ok)
            return combined, "vote", agreement, votes, ""
        model = self._llm.member_for(route).name if isinstance(self._llm, EnsembleLLMClient) else ""
        budget = self._config.engines.vlm_glance.llm.max_tokens
        error = ""
        # A cut-off answer (e.g. the model first echoes the schema's description) gets one retry with
        # twice the room, as plans do; anything else is a failed glance.
        for max_tokens in (None, 2 * budget):
            try:
                glance = await self._llm.generate_structured_with_image_async(
                    ShelfGlance, system, prompt, view.data_url(), seed=seed, route=route,
                    max_retries=1, **({} if max_tokens is None else {"max_tokens": max_tokens}),
                )
            except Exception as e:  # noqa: BLE001 — one failed glance must not fail the customer
                error = f"{type(e).__name__}: {e}"
                if _truncated_output(e):
                    continue
                return None, model, None, (), error
            return glance, model, None, (), ""
        return None, model, None, (), error

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
        bought = [r for r in named if r[1] and r[2] not in ("over_budget", "unreachable", "duplicate", "breadth")]
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
            "shelf_view": vlm.shelf_view,
            "views": dict(Counter(g.view for g in log)),
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
