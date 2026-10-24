"""3-stage LLM pipeline engine. stage1 (pattern) → stage2 (intent) → stage3 (impulse)."""

import logging
from collections.abc import Sequence

from instructor.core.exceptions import InstructorRetryException
from litellm.exceptions import BadRequestError

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.engine import PerCustomerContext, EngineDecision
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, PathFinder, TokenUsage, WEEKDAY_LABELS, stable_seed
from store_emulator.engine.llm_router import EnsembleLLMClient, SimLLM
from store_emulator.engine.llm_client import is_context_overflow
from . import stage1_pattern, stage2_intent, stage3_impulse
from .stage2_intent import IntentResponse
from .stage3_impulse import ImpulseResponse
from store_emulator.engine.routing.route_builder import (
    build_journey, find_exposed_products, integrate_actions, perceive_products,
)
from store_emulator.engine.routing.store_lookup import resolve_buy_placement

logger = logging.getLogger(__name__)


def drop_invalid_buys(actions: Sequence[CustomerAction], store: Store) -> tuple[list[CustomerAction], int]:
    """Drop buys whose product_sku does not exist in any slot (LLM hallucination guard).
    If only PAY remains afterwards, drop it too (no purchases → no payment).
    Returns (kept actions, number of dropped buys).
    """
    valid_skus = {i.sku for r in store.racks for s in r.slots for i in s.items}
    kept: list[CustomerAction] = []
    dropped = 0
    for a in actions:
        if a.action == Action.BUY:
            if not a.product_sku or a.product_sku not in valid_skus:
                logger.info("[drop] LLM hallucinated buy sku=%r — dropped", a.product_sku)
                dropped += 1
                continue
        kept.append(a)
    return _drop_orphan_pay(kept), dropped


def apply_budget(
    actions: list[CustomerAction],
    store: Store,
    budget_max: int,
    tolerance: float | None,
    *,
    max_quantity: int = 6,
) -> tuple[list[CustomerAction], int]:
    """Drop impulse buys (latest first) while spend exceeds budget_max × tolerance.

    Planned buys are never dropped — the shopper came for them. Returns (kept, dropped).
    """
    if tolerance is None or budget_max <= 0:
        return actions, 0
    cap = budget_max * tolerance

    def line_total(a: CustomerAction) -> int:
        placement = resolve_buy_placement(store, target=a.target, face=a.face, sku=a.product_sku,
                                          block=a.product_block, level=a.product_level)
        if placement is None:
            return 0
        item = next((i for i in placement[1].items if i.sku == a.product_sku), None)
        return (item.price if item else 0) * min(max_quantity, max(1, a.quantity))

    spend = sum(line_total(a) for a in actions if a.action == Action.BUY)
    if spend <= cap:
        return actions, 0
    kept = list(actions)
    dropped = 0
    for idx in range(len(kept) - 1, -1, -1):
        a = kept[idx]
        if spend <= cap:
            break
        if a.action == Action.BUY and a.origin == "impulse":
            spend -= line_total(a)
            kept.pop(idx)
            dropped += 1
    return _drop_orphan_pay(kept), dropped


def _drop_orphan_pay(actions: list[CustomerAction]) -> list[CustomerAction]:
    if any(a.action == Action.BUY for a in actions):
        return actions
    return [a for a in actions if a.action != Action.PAY]


def apply_product_limit(actions: list[CustomerAction], maximum: int) -> tuple[list[CustomerAction], int]:
    """Cap purchase lines, retaining planned products before impulse additions; quantities are unchanged."""
    buys = [i for i, action in enumerate(actions) if action.action == Action.BUY]
    allowed = set(sorted(buys, key=lambda i: (actions[i].origin == "impulse", i))[:max(0, maximum)])
    kept = [action for i, action in enumerate(actions) if action.action != Action.BUY or i in allowed]
    return _drop_orphan_pay(kept), len(buys) - len(allowed)


class PatternIntentImpulseEngine:
    engine_type = "pattern_intent_impulse"

    def __init__(
        self,
        llm: SimLLM,
        pathfinder: PathFinder,
        config: SimulationConfig,
    ):
        self._llm = llm
        self._pathfinder = pathfinder
        self._config = config

    def reset_usage(self) -> None:
        self._llm.reset_usage()

    def get_usage(self) -> TokenUsage:
        return self._llm.get_usage()

    def metadata(self) -> dict[str, object]:
        return {"ensemble": self._llm.metadata()} if isinstance(self._llm, EnsembleLLMClient) else {}

    async def decide_actions(
        self,
        context: PerCustomerContext,
    ) -> EngineDecision:
        cfg = self._config
        currency = cfg.currency
        patterns = context.behavior_patterns
        pattern_map = {p.id: p for p in patterns}
        fallback = patterns[0]
        day_of_week = WEEKDAY_LABELS[context.day]

        def stage_seed(stage: str) -> int:
            return stable_seed(context.seed, stage)

        # Stage 1: pattern selection.
        stage1_system = stage1_pattern.build_system_prompt(patterns)
        stage1_user = stage1_pattern.build_user_prompt(
            context.persona, context.arrival_hour, context.store, day_of_week, context.cue,
            address=context.address, customer_profile=context.customer_profile, currency=currency,
        )
        situation = f"\n\n## 오늘의 상황 (Situation)\n{context.situation}" if context.situation else ""
        selection = await self._llm.generate_structured_async(
            stage1_pattern.PatternSelectionResponse, stage1_system, stage1_user + situation, seed=stage_seed("stage1"), route=context.persona.id,
        )
        pattern = pattern_map.get(selection.pattern_id, fallback)
        grammar_override = selection.grammar_override

        # Stage 2: action-sequence generation (store catalog is the cached system prefix).
        records = stage2_intent.catalog_records(context.store)
        intent_records = records
        stage2_system = stage2_intent.build_system_prompt(context.store, currency, records=records)
        stage2_user = stage2_intent.build_user_prompt(
            context.persona, context.arrival_hour, context.concurrent_visitors_in_hour,
            day_of_week, context.cue,
            pattern=pattern, grammar_override=grammar_override, currency=currency,
        )
        recovery_trace: dict[str, object] = {}
        try:
            intent = await self._llm.generate_structured_async(
                stage2_intent.catalog_response_model(IntentResponse, records), stage2_system, stage2_user + situation,
                seed=stage_seed("stage2"), route=context.persona.id,
            )
        except (BadRequestError, InstructorRetryException) as error:
            cause = (error.failed_attempts[-1].exception
                     if isinstance(error, InstructorRetryException) and error.failed_attempts else error)
            maximum = max(4, pattern.max_products)
            if not is_context_overflow(cause) or len(records) <= maximum:
                raise
            logger.info("[intent] input context exceeded; selecting at most %s candidates from all %s offers once",
                        maximum, len(records))
            candidates = await self._llm.generate_structured_async(
                stage2_intent.catalog_selection_model(records, maximum),
                stage2_intent.build_catalog_selection_prompt(context.store, records, maximum, currency),
                stage2_user + situation, max_retries=2, seed=stage_seed("catalog"), route=context.persona.id,
            )
            selected = {code: records[code] for code in candidates.codes}
            intent_records = selected
            intent = await self._llm.generate_structured_async(
                stage2_intent.catalog_response_model(IntentResponse, selected),
                stage2_intent.build_system_prompt(context.store, currency, records=selected, focused=True),
                stage2_user + situation, seed=stage_seed("stage2"), route=context.persona.id,
            )
            recovery_trace["catalog_recovery"] = {"selected_codes": candidates.codes,
                                                  "selected_skus": [item.sku for item in selected.values()]}
        intent = stage2_intent.decode_catalog_response(IntentResponse, intent, intent_records, context.store)
        for a in intent.actions:
            a.origin = "planned"
            if a.action in (Action.BUY, Action.PAY):
                a.nav = "path"
            elif a.action == Action.EXIT:
                a.nav = "leave"

        # Exposure is computed on the route the shopper will actually walk (same ordering
        # rule as the final merge), so impulse candidates match the executed path.
        valid_intent, dropped_invalid = drop_invalid_buys(intent.actions, context.store)
        bounded_intent, dropped_limit = apply_product_limit(valid_intent, pattern.max_products)
        planned = integrate_actions(context.store, bounded_intent, [], ordering=cfg.route_ordering)
        journey = build_journey(context.store, planned, self._pathfinder, cfg.block_move_sec)
        visibility: dict[str, float] | None = None
        if cfg.exposure_model == "visibility":
            seen = perceive_products(context.store, journey, cfg.perception)
            exposed = [(e.rack, e.slot, e.sku) for e in seen]
            visibility = {e.sku: e.visibility for e in seen}
        else:
            exposed = find_exposed_products(context.store, journey)

        # Stage 3: impulse-purchase reactions.
        impulse: ImpulseResponse
        if exposed:
            exposed_offers = {(item.sku, item.name, item.price, item.promo)
                              for _, slot, sku in exposed
                              if (item := next((item for item in slot.items if item.sku == sku), None)) is not None}
            impulse_records = {code: item for code, item in records.items()
                               if (item.sku, item.name, item.price, item.promo) in exposed_offers}
            existing_buys = sum(1 for a in bounded_intent if a.action == Action.BUY)
            stage3_system = stage3_impulse.build_system_prompt(
                pattern.max_products, pattern.allow_no_purchase, existing_buys,
                pattern.browse_required_before_buy, currency=currency, product_codes=True,
            )
            stage3_user = stage3_impulse.build_user_prompt(
                context.persona, intent.model_copy(update={"actions": bounded_intent}), exposed, day_of_week,
                address=context.address, customer_profile=context.customer_profile,
                cue=context.cue, grid_size=context.store.grid_size,
                visibility=visibility, currency=currency, records=impulse_records,
            )
            impulse = await self._llm.generate_structured_async(
                stage2_intent.catalog_response_model(ImpulseResponse, impulse_records), stage3_system, stage3_user + situation,
                seed=stage_seed("stage3"), route=context.persona.id,
            )
            impulse = stage2_intent.decode_catalog_response(ImpulseResponse, impulse, impulse_records, context.store)
        else:
            impulse = ImpulseResponse()
        impulse_actions: list[CustomerAction] = []
        valid_impulse, dropped_impulse_invalid = drop_invalid_buys(impulse.actions, context.store)
        dropped_invalid += dropped_impulse_invalid
        exposed_skus = {sku for _, _, sku in exposed}
        dropped_unexposed = 0
        for a in valid_impulse:
            a.origin = "impulse"
            # This stage contributes shopping stops, not another visit frame.
            # Keep unexpected model output in the trace but out of execution.
            if a.action in (None, Action.BROWSE, Action.BUY):
                a.action = a.action or Action.BROWSE
                a.nav = "path"
                if a.action == Action.BUY and a.product_sku not in exposed_skus:
                    dropped_unexposed += 1
                    continue
                impulse_actions.append(a)
        if len(impulse_actions) != len(impulse.actions):
            logger.info("[drop] ignored %d unusable impulse actions", len(impulse.actions) - len(impulse_actions))

        if cfg.route_ordering == "planned":
            merged = integrate_actions(context.store, planned, impulse_actions, ordering="planned")
        else:
            merged = integrate_actions(context.store, bounded_intent, impulse_actions, ordering="nearest")
        merged, dropped_impulse_invalid = drop_invalid_buys(merged, context.store)
        dropped_invalid += dropped_impulse_invalid
        merged, dropped_budget = apply_budget(
            merged, context.store, context.persona.budget_max, cfg.budget_tolerance,
            max_quantity=cfg.max_quantity_per_line,
        )
        merged, dropped_impulse_limit = apply_product_limit(merged, pattern.max_products)
        dropped_limit += dropped_impulse_limit
        # An initially browsing-only visit has no payment in stage 2. Any buys
        # surviving stage 3 and budget pruning still need a checkout before exit.
        if (context.store.counters and any(a.action == Action.BUY for a in merged)
                and not any(a.action == Action.PAY for a in merged)):
            exit_index = next((i for i, a in enumerate(merged) if a.nav == "leave"), len(merged))
            payment = next((a for a in reversed(intent.actions) if a.action == Action.PAY), None)
            merged.insert(exit_index, payment if payment is not None else CustomerAction(nav="path", action=Action.PAY, dwell=15))
        if not any(a.nav == "leave" for a in merged):
            merged.append(CustomerAction(nav="leave", action=Action.EXIT))

        return EngineDecision(
            actions=merged,
            engine_type=EngineType.PATTERN_INTENT_IMPULSE.value,
            trace={
                **recovery_trace,
                "stage1": selection.model_dump(),
                "stage2": intent.model_dump(),
                "stage3": impulse.model_dump(),
                "exposed_skus": [sku for _, _, sku in exposed],
                "dropped_unexposed_buys": dropped_unexposed,
                "dropped_product_limit": dropped_limit,
            },
            dropped_invalid_buys=dropped_invalid,
            dropped_over_budget=dropped_budget,
        )
