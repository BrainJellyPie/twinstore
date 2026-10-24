"""The 3-stage LLM engine, exercised with a scripted fake client (no network, no cost)."""

import asyncio

from pydantic import BaseModel

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, TokenUsage, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import (
    PatternIntentImpulseEngine,
)
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage1_pattern import (
    PatternSelectionResponse,
)
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import (
    IntentResponse,
)
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import (
    ImpulseResponse,
)


class _ScriptedLLM:
    """Returns canned responses per response model and records every prompt."""

    def __init__(self, intent: IntentResponse, impulse: ImpulseResponse) -> None:
        self.intent, self.impulse = intent, impulse
        self.calls: list[tuple[str, str, str, int | None]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        self.calls.append((response_model.__name__, system_prompt, user_prompt, seed))
        if response_model is PatternSelectionResponse:
            return response_model.model_validate({"pattern_id": "exploratory"})
        if response_model.__name__ == "IntentResponse":
            return response_model.model_validate(self.intent.model_dump())
        return response_model.model_validate(self.impulse.model_dump())

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage()


def _persona(budget_max: int = 1000) -> Persona:
    return Persona(
        id="P1", identity="student", age_group="20s", gender="Female", description="d", intent="snack",
        purpose="snack", preferred_categories=["snacks"], budget_min=100, budget_max=budget_max,
    )


def _context(store: Store, persona: Persona) -> PerCustomerContext:
    return PerCustomerContext(
        store=store, persona=persona, day=Weekday.MON, arrival_hour=12, concurrent_visitors_in_hour=3,
        cue=BehaviorCue(), behavior_patterns=BEHAVIOR_PATTERNS, seed=42,
    )


def _intent() -> IntentResponse:
    return IntentResponse(actions=[
        CustomerAction(nav="path", target=(0, 2), action=Action.ENTER),
        CustomerAction(nav="path", target=(1, 0), face=Face.E, action=Action.BROWSE),
        CustomerAction(nav="path", target=(1, 0), face=Face.E, action=Action.BUY, product_sku="sku-a", quantity=3),
        CustomerAction(nav="path", target=(4, 1), action=Action.PAY),
        CustomerAction(nav="leave", action=Action.EXIT),
    ])


def test_engine_tags_origin_drops_hallucinations_and_keeps_quantity(collision_store):
    impulse = ImpulseResponse(actions=[
        CustomerAction(nav="path", target=(1, 0), face=Face.W, action=Action.BROWSE),
        CustomerAction(nav="path", target=(1, 0), face=Face.W, action=Action.BUY, product_sku="sku-b"),
        CustomerAction(nav="path", target=(1, 0), face=Face.W, action=Action.BUY, product_sku="sku-ghost"),
    ])
    llm = _ScriptedLLM(_intent(), impulse)
    config = SimulationConfig(budget_tolerance=None)
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), config)  # type: ignore[arg-type]  # duck-typed fake
    decision = asyncio.run(engine.decide_actions(_context(collision_store, _persona())))

    buys = [a for a in decision.actions if a.action == Action.BUY]
    assert {(a.product_sku, a.origin) for a in buys} == {("sku-a", "planned"), ("sku-b", "impulse")}
    assert decision.dropped_invalid_buys == 1
    # Seeds are derived per stage from the customer seed.
    seeds = [c[3] for c in llm.calls]
    assert len(set(seeds)) == len(seeds) == 3

    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    line_a = next(e for e in result.purchases if e.product_sku == "sku-a")
    assert line_a.quantity == 3 and line_a.origin == "planned"
    assert result.total_spent == 3 * 100 + 200
    assert result.dropped_invalid_buys == 1


def test_budget_tolerance_drops_impulse_but_never_planned(collision_store):
    impulse = ImpulseResponse(actions=[
        CustomerAction(nav="path", target=(1, 0), face=Face.W, action=Action.BUY, product_sku="sku-b", quantity=5),
    ])
    llm = _ScriptedLLM(_intent(), impulse)
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(budget_tolerance=1.0))  # type: ignore[arg-type]
    decision = asyncio.run(engine.decide_actions(_context(collision_store, _persona(budget_max=400))))
    buys = [a.product_sku for a in decision.actions if a.action == Action.BUY]
    assert buys == ["sku-a"]  # planned 3×100 kept, impulse 5×200 dropped
    assert decision.dropped_over_budget == 1


def test_stage2_catalog_is_in_the_cacheable_system_prompt(collision_store):
    llm = _ScriptedLLM(_intent(), ImpulseResponse())
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(currency="KRW"))  # type: ignore[arg-type]
    asyncio.run(engine.decide_actions(_context(collision_store, _persona())))
    _, system, user, _ = next(c for c in llm.calls if c[0] == "IntentResponse")
    assert "A item" in system and "A item" not in user        # catalog in the shared prefix
    assert "student" in user and "student" not in system      # persona in the customer suffix
    assert "원(KRW)" in system and "100원" in system           # currency-aware wording


def test_exposure_is_computed_on_the_walked_route(collision_store):
    llm = _ScriptedLLM(_intent(), ImpulseResponse())
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig())  # type: ignore[arg-type]
    decision = asyncio.run(engine.decide_actions(_context(collision_store, _persona())))
    exposed = decision.trace["exposed_skus"]
    assert isinstance(exposed, list)
    impulse_prompt = next((c for c in llm.calls if c[0] == "ImpulseResponse"), None)
    if exposed:
        assert impulse_prompt is not None and "시인성=" in impulse_prompt[2]
