"""Budget pruning agrees with quantities that the timeline actually executes."""
import asyncio

import pytest
from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, TokenUsage, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import entrance_position, face_access_tile
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage1_pattern import PatternSelectionResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse


class ScriptedLLM:
    def __init__(self, planned: list[CustomerAction], impulse: list[CustomerAction]):
        self.responses: dict[str, BaseModel] = {
            "PatternSelectionResponse": PatternSelectionResponse(pattern_id="purposeful"),
            "IntentResponse": IntentResponse(actions=planned),
            "ImpulseResponse": ImpulseResponse(actions=impulse),
        }
        self.calls = 0

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        self.calls += 1
        return response_model.model_validate(self.responses[response_model.__name__].model_dump())

    def reset_usage(self) -> None:
        self.calls = 0

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=self.calls)


@pytest.mark.parametrize("budget_delta", [0, -1])
@pytest.mark.parametrize("max_quantity", [1, 2, 6])
@pytest.mark.parametrize("oversized_origin", ["planned", "impulse"])
def test_budget_uses_executable_quantities(max_quantity, oversized_origin, budget_delta):
    store = generate_store("urban_cvs")
    rack = store.product_racks[0]
    slot = next(slot for slot in rack.slots if len(slot.items) > 1)
    first, second = slot.items[:2]
    for shelf in store.product_racks:
        for facing in shelf.slots:
            for item in facing.items:
                item.price = 100
    tile = face_access_tile(rack, slot.face, store.grid_size, store.walkable_grid())
    assert tile is not None
    planned = [
        CustomerAction(nav="path", target=entrance_position(store), action=Action.ENTER),
        CustomerAction(nav="path", target=tile, face=slot.face, action=Action.BUY, product_sku=first.sku,
                       quantity=100 if oversized_origin == "planned" else 1),
        CustomerAction(nav="path", target=sorted(store.counters[0].service_access_tiles(store.grid_size))[0], action=Action.PAY),
        CustomerAction(nav="leave", action=Action.EXIT),
    ]
    impulse = [CustomerAction(nav="path", target=tile, face=slot.face, action=Action.BUY, product_sku=second.sku,
                              quantity=100 if oversized_origin == "impulse" else 1)]
    fake = ScriptedLLM(planned, impulse)
    config = SimulationConfig(budget_tolerance=1, max_quantity_per_line=max_quantity)
    context = PerCustomerContext(
        store=store, persona=Persona(id="test", identity="Test", age_group="30s", gender="Female",
            description="", intent="", purpose="", budget_max=(max_quantity + 1) * 100 + budget_delta),
        day=Weekday.MON, arrival_hour=12, concurrent_visitors_in_hour=1, cue=BehaviorCue(),
        behavior_patterns=[p for p in BEHAVIOR_PATTERNS if p.id == "purposeful"],
    )
    engine = PatternIntentImpulseEngine(fake, AStarPathFinder(), config)
    decision = asyncio.run(engine.decide_actions(context))
    result = execute_decision(store, "test", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1,
                              max_quantity=max_quantity)
    assert fake.calls == 3
    expected_drop = int(budget_delta < 0)
    assert decision.dropped_over_budget == expected_drop
    assert len(result.purchases) == 2 - expected_drop
    planned_spend = (max_quantity if oversized_origin == "planned" else 1) * 100
    assert result.total_spent == (planned_spend if expected_drop else (max_quantity + 1) * 100)
    assert result.total_spent <= context.persona.budget_max
