"""Unreachable model purchases must not consume money or purchase-line allowances."""

import asyncio

import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.rack import Rack
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from store_emulator.engine.validation import validate
from tests.engine.routing.test_unreachable_purchases import separated_store
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _persona


@pytest.mark.parametrize("source", ["planned", "impulse"])
@pytest.mark.parametrize("constraint", ["budget", "lines", "both"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("codes", [False, True])
@pytest.mark.parametrize("obstacle", ["wall", "door"])
@pytest.mark.parametrize("diagonal", [False, True])
def test_disconnected_offer_does_not_prune_reachable_purchases(source, constraint, ordering, codes, obstacle, diagonal):
    store, _ = separated_store(Face.N, obstacle)
    store.racks += [Rack(id="far-in", type="entrance", position=(9, 0), shape=[[1]]),
                    Rack(id="far-out", type="exit", position=(9, 9), shape=[[1]]),
                    Rack(id="far-till", type="counter", position=(7, 8), shape=[[1]])]
    assert not [issue for issue in validate(store) if issue.severity == "error"]
    before = store.model_dump()
    refs = {item.sku: code for code, item in stage2_intent.catalog_records(store).items()}
    near = {"nav": "path", "action": "buy", "product_sku": refs["near"] if codes else "near",
            "target": [2, 2], "face": "N"}
    intent = stage2_intent.IntentResponse.model_validate({"actions": [
        {"nav": "path", "action": "enter"},
        {"nav": "path", "action": "buy", "product_sku": refs["far"] if codes else "far"},
        {"nav": "path", "action": "browse", "target": [2, 2], "face": "N"},
        *([near] if source == "planned" else []),
        {"nav": "path", "action": "pay", "dwell": 19}, {"nav": "leave"},
    ]})
    impulse = ImpulseResponse.model_validate({"actions": [near] if source == "impulse" else []})
    context = _context(store, _persona(0 if constraint == "lines" else 100))
    context.behavior_patterns = [p.model_copy(update={"max_products": 6 if constraint == "budget" else 1})
                                 for p in context.behavior_patterns]
    pathfinder = AStarPathFinder(diagonal=diagonal)
    model = _ScriptedLLM(intent, impulse)
    engine = PatternIntentImpulseEngine(model, pathfinder,
        SimulationConfig(route_ordering=ordering, budget_tolerance=None if constraint == "lines" else 1))
    decision = asyncio.run(engine.decide_actions(context))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, pathfinder, 1)
    if obstacle == "wall":
        assert [(p.product_sku, p.quantity) for p in result.purchases] == [("near", 1)]
        assert result.total_spent == 100 and result.dropped_invalid_buys == 1
        assert decision.dropped_over_budget == decision.trace["dropped_product_limit"] == 0
    else:
        expected = 600 if source == "planned" and constraint == "budget" else 500
        assert result.total_spent == expected and result.dropped_invalid_buys == 0
    payments = [event for event in result.timeline if event.action == Action.PAY]
    assert len(payments) == 1 and payments[0].duration == 19
    assert result.timeline[-1].action == Action.EXIT
    assert store.model_dump() == before
