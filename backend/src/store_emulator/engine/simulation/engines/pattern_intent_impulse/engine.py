"""3-stage LLM pipeline engine. stage1 (pattern) → stage2 (intent) → stage3 (impulse)."""

import logging

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.engine import PerCustomerContext, EngineDecision
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, PathFinder, TokenUsage, WEEKDAY_LABELS, stable_seed
from store_emulator.engine.llm_client import LiteLLMClient
from . import stage1_pattern, stage2_intent, stage3_impulse
from .stage2_intent import IntentResponse
from .stage3_impulse import ImpulseResponse
from store_emulator.engine.routing.route_builder import (
    build_journey, find_exposed_products, integrate_actions, perceive_products,
)
from store_emulator.engine.routing.store_lookup import resolve_buy_placement

logger = logging.getLogger(__name__)


def drop_invalid_buys(actions: list[CustomerAction], store: Store) -> tuple[list[CustomerAction], int]:
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
) -> tuple[list[CustomerAction], int]:
    """Drop impulse buys (latest first) while spend exceeds budget_max × tolerance.

    Planned buys are never dropped — the shopper came for them. Returns (kept, dropped).
    """
    if tolerance is None or budget_max <= 0:
        return actions, 0
    cap = budget_max * tolerance

    def line_total(a: CustomerAction) -> int:
        placement = resolve_buy_placement(store, target=a.target, face=a.face, sku=a.product_sku)
        if placement is None:
            return 0
        item = next((i for i in placement[1].items if i.sku == a.product_sku), None)
        return (item.price if item else 0) * max(1, a.quantity)

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


class PatternIntentImpulseEngine:
    engine_type = "pattern_intent_impulse"

    def __init__(
        self,
        llm: LiteLLMClient,
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
        selection = await self._llm.generate_structured_async(
            stage1_pattern.PatternSelectionResponse, stage1_system, stage1_user, seed=stage_seed("stage1"),
        )
        pattern = pattern_map.get(selection.pattern_id, fallback)
        grammar_override = selection.grammar_override

        # Stage 2: action-sequence generation (store catalog is the cached system prefix).
        stage2_system = stage2_intent.build_system_prompt(context.store, currency)
        stage2_user = stage2_intent.build_user_prompt(
            context.persona, context.arrival_hour, context.concurrent_visitors_in_hour,
            day_of_week, context.cue,
            pattern=pattern, grammar_override=grammar_override, currency=currency,
        )
        intent = await self._llm.generate_structured_async(
            IntentResponse, stage2_system, stage2_user, seed=stage_seed("stage2"),
        )
        for a in intent.actions:
            a.origin = "planned"

        # Exposure is computed on the route the shopper will actually walk (same ordering
        # rule as the final merge), so impulse candidates match the executed path.
        planned = integrate_actions(context.store, intent.actions, [], ordering=cfg.route_ordering)
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
            existing_buys = sum(1 for a in intent.actions if a.action == Action.BUY)
            stage3_system = stage3_impulse.build_system_prompt(
                pattern.max_products, pattern.allow_no_purchase, existing_buys,
                pattern.browse_required_before_buy, currency=currency,
            )
            stage3_user = stage3_impulse.build_user_prompt(
                context.persona, intent, exposed, day_of_week,
                address=context.address, customer_profile=context.customer_profile,
                cue=context.cue, grid_size=context.store.grid_size,
                visibility=visibility, currency=currency,
            )
            impulse = await self._llm.generate_structured_async(
                ImpulseResponse, stage3_system, stage3_user, seed=stage_seed("stage3"),
            )
        else:
            impulse = ImpulseResponse()
        for a in impulse.actions:
            a.origin = "impulse"

        if cfg.route_ordering == "planned":
            merged = integrate_actions(context.store, planned, impulse.actions, ordering="planned")
        else:
            merged = integrate_actions(context.store, intent.actions, impulse.actions, ordering="nearest")
        merged, dropped_invalid = drop_invalid_buys(merged, context.store)
        merged, dropped_budget = apply_budget(
            merged, context.store, context.persona.budget_max, cfg.budget_tolerance,
        )

        return EngineDecision(
            actions=merged,
            engine_type=EngineType.PATTERN_INTENT_IMPULSE.value,
            trace={
                "stage1": selection.model_dump(),
                "stage2": intent.model_dump(),
                "stage3": impulse.model_dump(),
                "exposed_skus": [sku for _, _, sku in exposed],
            },
            dropped_invalid_buys=dropped_invalid,
            dropped_over_budget=dropped_budget,
        )
