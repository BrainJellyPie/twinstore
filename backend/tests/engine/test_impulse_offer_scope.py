"""Non-grammar responses cannot use a visible SKU to select an unseen offer."""

import asyncio

import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.rack import BlockFace, Slot, SlotItem
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _persona
from tests.engine.test_llm_impulse_exposure import buy, fixture


@pytest.mark.parametrize("exposure", ["adjacency", "visibility"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("same_offer", [False, True])
@pytest.mark.parametrize("answer", ["canonical", "code"])
def test_impulse_stays_at_the_exposed_placement_even_if_sku_or_offer_is_repeated(exposure, ordering, same_offer, answer):
    store, intent = fixture()
    near, far = store.racks[:2]
    far.slots[0].items[0].sku = "seen"
    far.slots[0].items[0].price = 100 if same_offer else 900
    far.slots[0].items[0].name = "seen" if same_offer else "Unseen premium"
    before = store.model_dump()
    llm = _ScriptedLLM(intent, ImpulseResponse(actions=[buy("seen" if answer == "canonical" else "@P1", (10, 2))]))
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(route_ordering=ordering,
        exposure_model=exposure, budget_tolerance=1))
    decision = asyncio.run(engine.decide_actions(_context(store, _persona(100))))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert decision.trace["exposed_skus"] == ["seen"]
    assert len(result.purchases) == 1 and result.total_spent == 100
    assert result.purchases[0].target_rack == near.id and result.purchases[0].product_name == "seen"
    assert not any(event.target_rack == far.id for event in result.timeline)
    assert decision.dropped_over_budget == 0
    assert store.model_dump() == before


@pytest.mark.parametrize("exposure", ["adjacency", "visibility"])
def test_planned_purchase_still_may_choose_an_offer_outside_the_original_route(exposure):
    store, intent = fixture()
    far = store.racks[1]
    far.slots[0].items[0].sku = "seen"
    far.slots[0].items[0].price = 900
    intent.actions.insert(2, buy("seen", (10, 2)))
    engine = PatternIntentImpulseEngine(_ScriptedLLM(intent, ImpulseResponse()), AStarPathFinder(),
        SimulationConfig(exposure_model=exposure, budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(_context(store, _persona())))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert len(result.purchases) == 1 and result.purchases[0].target_rack == far.id and result.total_spent == 900
    assert next(action for action in decision.actions if action.action == Action.BUY).origin == "planned"


@pytest.mark.parametrize("exposure", ["adjacency", "visibility"])
@pytest.mark.parametrize("answer", ["seen", "@P1"])
def test_locked_observed_offer_cannot_be_replaced_by_an_unseen_unlocked_copy(exposure, answer):
    store, intent = fixture()
    near, far = store.racks[:2]
    near.locked_faces = [BlockFace(block=0, face=near.slots[0].face)]
    far.slots[0].items = [near.slots[0].items[0].model_copy()]
    engine = PatternIntentImpulseEngine(_ScriptedLLM(intent, ImpulseResponse(actions=[buy(answer)])), AStarPathFinder(),
        SimulationConfig(exposure_model=exposure, budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(_context(store, _persona())))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert decision.trace["exposed_skus"] == ["seen"] and decision.dropped_invalid_buys == 1
    assert result.total_spent == 0 and not result.purchases
    assert not any(event.target_rack == far.id for event in result.timeline)


def test_canonical_sku_preserves_the_visibility_models_selected_shelf_level():
    store, intent = fixture()
    rack = store.racks[0]
    original = rack.slots[0]
    original.level = 1
    rack.slots.append(Slot(block=0, face=original.face, level=3, items=[
        SlotItem(sku="seen", name="Eye-level offer", price=700)]))
    engine = PatternIntentImpulseEngine(_ScriptedLLM(intent, ImpulseResponse(actions=[buy("seen", (2, 2))])),
        AStarPathFinder(), SimulationConfig(exposure_model="visibility", budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(_context(store, _persona())))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert len(result.purchases) == 1 and result.total_spent == 700
    assert result.purchases[0].product_level == 3 and result.purchases[0].product_name == "Eye-level offer"
