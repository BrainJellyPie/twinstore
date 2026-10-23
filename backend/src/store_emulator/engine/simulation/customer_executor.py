import logging
import random

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, PathFinder, Weekday

from ..routing.route_builder import build_journey
from ..routing.timeline_builder import build_timeline

logger = logging.getLogger(__name__)


def execute_decision(
    store: Store,
    persona_id: str,
    day: Weekday,
    arrival_time: str,
    decision: EngineDecision,
    pathfinder: PathFinder,
    block_move_sec: float,
    *,
    rng: random.Random | None = None,
    max_quantity: int = 6,
) -> CustomerResult:
    journey = build_journey(store, decision.actions, pathfinder, block_move_sec)
    result = build_timeline(
        persona_id, day, arrival_time,
        journey, store, block_move_sec=block_move_sec,
        rng=rng, max_quantity=max_quantity,
    )
    result.engine_type = decision.engine_type
    skus = {item.sku for rack in store.racks for slot in rack.slots for item in slot.items}
    invalid = sum(action.action == Action.BUY and (not action.product_sku or action.product_sku not in skus)
                  for action in decision.actions)
    dropped = sum(action.action == Action.BUY for action in decision.actions) - sum(
        step.action.action == Action.BUY for step in journey)
    if dropped > invalid:
        logger.warning("Skipped %d unreachable purchases for persona %s", dropped - invalid, persona_id)
    result.dropped_invalid_buys = decision.dropped_invalid_buys + invalid
    result.dropped_over_budget = decision.dropped_over_budget
    return result
