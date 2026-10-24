"""Purchases introduced by the impulse stage still visit and use the tills."""

import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import entrance_position, face_access_tile
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.test_llm_budget_quantity import ScriptedLLM


def _visit(ordering, purchase, existing_pay=False, *, counterless=False):
    store = generate_store("station_kiosk")
    rack = store.product_racks[0]
    slot = rack.slots[0]
    item = slot.items[0]
    tile = face_access_tile(rack, slot.face, store.grid_size, store.walkable_grid())
    planned = [
        CustomerAction(nav="path", target=entrance_position(store), action=Action.ENTER),
        CustomerAction(nav="path", target=tile, face=slot.face, action=Action.BROWSE),
    ]
    impulse = []
    if purchase != "none":
        buy = CustomerAction(nav="path", target=tile, face=slot.face, action=Action.BUY,
                             product_sku="nonexistent" if purchase == "invalid" else item.sku)
        (planned if purchase == "planned" else impulse).append(buy)
    counter = store.counters[0]
    grid = store.walkable_grid()
    checkout = next(tile for tile in sorted(counter.service_access_tiles(store.grid_size)) if grid[tile[1]][tile[0]])
    if counterless:
        store.racks = [rack for rack in store.racks if rack.id != counter.id]
    if existing_pay:
        planned.append(CustomerAction(nav="path", target=checkout, action=Action.PAY, dwell=19))
    planned.append(CustomerAction(nav="leave", action=Action.EXIT))
    fake = ScriptedLLM(planned, impulse)
    config = SimulationConfig(route_ordering=ordering, budget_tolerance=1)
    context = PerCustomerContext(
        store=store,
        persona=Persona(id="test", identity="Shopper", age_group="30s", gender="Female",
                        description="", intent="", purpose="", budget_max=1 if purchase == "over_budget" else 10000),
        day=Weekday.MON, arrival_hour=12, concurrent_visitors_in_hour=1, cue=BehaviorCue(),
        behavior_patterns=BEHAVIOR_PATTERNS,
    )
    decision = asyncio.run(PatternIntentImpulseEngine(fake, AStarPathFinder(), config).decide_actions(context))
    assert fake.calls == 3
    result = execute_decision(store, "test", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    return store, item, checkout, decision, result


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
@pytest.mark.parametrize("purchase", ["impulse", "planned", "none", "invalid", "over_budget"])
@pytest.mark.parametrize("existing_pay", [False, True])
def test_checkout_matches_surviving_purchases(ordering, purchase, existing_pay):
    store, item, checkout, decision, result = _visit(ordering, purchase, existing_pay)
    bought = purchase in {"impulse", "planned"}
    pays = [event for event in result.timeline if event.action == Action.PAY]
    assert len(pays) == int(bought)
    assert result.total_spent == (item.price if bought else 0)
    if bought:
        pay = pays[0]
        assert (pay.x, pay.y) in store.counters[0].service_access_tiles(store.grid_size)
        assert pay.target_rack == store.counters[0].id
        assert max(e.elapsed_sec for e in result.purchases) < pay.elapsed_sec < result.timeline[-1].elapsed_sec
        if existing_pay:
            assert (pay.x, pay.y) == checkout and pay.duration == 19
    assert decision.dropped_invalid_buys == int(purchase == "invalid")
    assert decision.dropped_over_budget == int(purchase == "over_budget")
    _, report = resolve_shared_store(store, [result], OperationsConfig(restock_every_min=None), seed=1)
    assert report.queued == int(bought)


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
def test_impulse_only_baskets_join_the_line_and_can_be_abandoned(ordering):
    store, item, _, _, first = _visit(ordering, "impulse")
    second = first.model_copy(update={"persona_id": "second"}, deep=True)
    resolved, report = resolve_shared_store(store, [first, second], OperationsConfig(
        open_counters=1, checkout_base_sec=60, checkout_item_sec=0, patience_sec=10, patience_sd=0,
        restock_every_min=None, crowd_limit=None,
    ), seed=1)
    assert report.queued == 2 and report.abandoned == 1
    assert sum(r.total_spent for r in resolved) == item.price
    assert sum(r.left_queue for r in resolved) == 1
    assert first.total_spent == second.total_spent == item.price


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
@pytest.mark.parametrize("purchase", ["planned", "impulse", "none"])
@pytest.mark.parametrize("existing_pay", [False, True])
def test_counterless_layout_does_not_invent_a_payment_location(ordering, purchase, existing_pay):
    store, item, _, _, result = _visit(ordering, purchase, existing_pay=existing_pay, counterless=True)
    assert not store.counters
    assert result.total_spent == (0 if purchase == "none" else item.price)
    assert not any(event.action == Action.PAY for event in result.timeline)
    assert result.timeline[-1].action == Action.EXIT
