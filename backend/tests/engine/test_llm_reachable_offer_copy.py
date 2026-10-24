"""Repeated identical offers should resolve to the shopper's accessible placement."""

import asyncio

import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.rack import Rack
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from store_emulator.engine.validation import validate
from tests.engine.routing.test_reachable_service_routes import divided_visit
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _persona


@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("codes", [False, True])
@pytest.mark.parametrize("hint", ["missing", "remote", "local"])
@pytest.mark.parametrize("remote_first", [False, True])
@pytest.mark.parametrize("same_offer", [False, True])
def test_same_offer_uses_reachable_copy_without_substituting_different_price(transpose, side, codes, hint, remote_first, same_offer):
    store, _, _ = divided_visit("two", transpose, side, "local")
    local = next(r for r in store.racks if r.id == "product")
    def point(x, y):
        return (y, x) if transpose else (x, y)
    remote = Rack(id="remote-product", type="shelf", position=point(2 if side else 7, 3), shape=[[1]],
                  slots=[slot.model_copy(deep=True) for slot in local.slots])
    remote.slots[0].items[0].price = 100 if same_offer else 500
    store.racks.insert(0 if remote_first else len(store.racks), remote)
    assert not [issue for issue in validate(store) if issue.severity == "error"]
    original = store.model_dump()
    target = None if hint == "missing" else point((2 if side else 7) if hint == "remote" else (7 if side else 2), 2)
    records = stage2_intent.catalog_records(store)
    code = next(code for code, item in records.items() if item.price == remote.slots[0].items[0].price)
    intent = stage2_intent.IntentResponse.model_validate({"actions": [
        {"nav": "path", "action": "enter"},
        {"nav": "path", "action": "buy", "product_sku": code if codes else "tea", "target": target},
        {"nav": "path", "action": "pay"}, {"nav": "leave"},
    ]})
    pathfinder = AStarPathFinder()
    decision = asyncio.run(PatternIntentImpulseEngine(_ScriptedLLM(intent, ImpulseResponse()), pathfinder,
        SimulationConfig()).decide_actions(_context(store, _persona(1000))))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, pathfinder, 1)
    local_selected = not codes and (hint == "local" or (hint == "missing" and not remote_first))
    if same_offer or local_selected:
        assert result.total_spent == 100 and len(result.purchases) == 1
        assert result.purchases[0].target_rack == "product"
        assert result.dropped_invalid_buys == 0
    else:
        assert result.total_spent == 0 and not result.purchases
        assert result.dropped_invalid_buys == 1
    assert result.timeline[-1].action == Action.EXIT
    assert store.model_dump() == original
