"""Model responses cannot add extra checkouts/exits or buy without reaching a shelf."""

import asyncio

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _intent, _persona


def _execute(store, ordering, intent, impulse):
    engine = PatternIntentImpulseEngine(_ScriptedLLM(intent, ImpulseResponse(actions=impulse)), AStarPathFinder(),
                                         SimulationConfig(route_ordering=ordering, budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(_context(store, _persona())))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    return decision, result


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
@pytest.mark.parametrize("extra", [Action.PAY, Action.EXIT, Action.ENTER, Action.MOVE, Action.WANDER])
def test_impulse_stage_only_contributes_shopping_stops(collision_store, ordering, extra):
    unwanted = CustomerAction(nav="leave" if extra == Action.EXIT else "path", target=(4, 1), action=extra,
                              dwell=20, description="unwanted impulse")
    buy = CustomerAction(nav="path", target=(1, 0), face=Face.W, action=Action.BUY, product_sku="sku-b")
    decision, result = _execute(collision_store, ordering, _intent(), [unwanted, buy])
    assert not any(a.description == "unwanted impulse" for a in decision.actions)
    assert sum(e.action == Action.ENTER for e in result.timeline) == 1
    assert sum(e.action == Action.EXIT for e in result.timeline) == 1
    pays = [i for i, e in enumerate(result.timeline) if e.action == Action.PAY]
    assert len(pays) == 1
    assert max(i for i, e in enumerate(result.timeline) if e.action == Action.BUY) < pays[0] < len(result.timeline) - 1
    assert result.total_spent == 500
    resolved, report = resolve_shared_store(collision_store, [result], OperationsConfig(
        restock_every_min=None, checkout_base_sec=60, checkout_item_sec=0, patience_sec=10, patience_sd=0,
    ), seed=1)
    assert report.queued == 1 and report.abandoned == 0
    assert resolved[0].total_spent == 500


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
@pytest.mark.parametrize("nav", ["area", "leave"])
@pytest.mark.parametrize("origin,kind", [("intent", Action.BUY), ("intent", Action.PAY), ("impulse", Action.BUY)])
def test_purchases_and_payment_use_point_routes_despite_conflicting_model_nav(collision_store, ordering, nav, origin, kind):
    collision_store.racks[1].position = (3, 0)  # a different access tile from the planned shelf
    intent = _intent()
    intent.actions = [a for a in intent.actions if a.action != Action.BROWSE]
    next(a for a in intent.actions if a.action == Action.PAY).dwell = 19
    impulse = []
    if origin == "intent":
        changed = next(a for a in intent.actions if a.action == kind)
        changed.nav = nav
        changed.area = (0, 0, 4, 2)
    else:
        impulse.append(CustomerAction(nav=nav, area=(0, 0, 4, 2), target=(2, 0), face=Face.W,
                                      action=Action.BUY, product_sku="sku-b"))
    decision, result = _execute(collision_store, ordering, intent, impulse)
    assert all(a.nav == "path" for a in decision.actions if a.action in (Action.BUY, Action.PAY))
    assert result.total_spent == (500 if origin == "impulse" else 300)
    assert result.timeline[-1].action == Action.EXIT
    expected_tiles = {"sku-a": (1, 0), "sku-b": (2, 0)}
    assert all((e.x, e.y) == expected_tiles[e.product_sku] for e in result.purchases)
    pay = next(e for e in result.timeline if e.action == Action.PAY)
    assert (pay.x, pay.y) in collision_store.counters[0].service_access_tiles(collision_store.grid_size)
    assert pay.duration == 19


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
def test_implicit_browse_from_impulse_stage_keeps_its_existing_meaning(collision_store, ordering):
    browse = CustomerAction(nav="path", target=(1, 0), face=Face.W, description="implicit browse")
    _, result = _execute(collision_store, ordering, _intent(), [browse])
    event = next(e for e in result.timeline if e.description == "implicit browse")
    assert event.action == Action.BROWSE and event.target_rack == "B" and event.origin == "impulse"


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
@pytest.mark.parametrize("exit_mode", ["missing", "path", "area"])
def test_incomplete_model_exit_still_finishes_at_the_exit_after_payment(collision_store, ordering, exit_mode):
    intent = _intent()
    if exit_mode == "missing":
        intent.actions = [a for a in intent.actions if a.action != Action.EXIT]
    else:
        exit_action = next(a for a in intent.actions if a.action == Action.EXIT)
        exit_action.nav = exit_mode
        exit_action.target = (1, 0)
        exit_action.area = (0, 0, 4, 2)
    _, result = _execute(collision_store, ordering, intent, [])
    assert result.timeline[-1].action == Action.EXIT
    assert sum(e.action == Action.EXIT for e in result.timeline) == 1
    assert (result.timeline[-1].x, result.timeline[-1].y) == collision_store.exits[0].position
    pay = next(e for e in result.timeline if e.action == Action.PAY)
    assert result.duration_sec >= pay.elapsed_sec + pay.duration
    assert result.total_spent == 300


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
@pytest.mark.parametrize("shopping", ["none", "planned", "impulse"])
def test_exit_navigation_overrides_a_conflicting_enter_label(collision_store, ordering, shopping):
    intent = _intent()
    if shopping != "planned":
        intent.actions = [a for a in intent.actions if a.action not in (Action.BUY, Action.PAY)]
    exit_action = next(a for a in intent.actions if a.action == Action.EXIT)
    exit_action.action = Action.ENTER  # The model preserves nav=leave but mislabels the final action.
    exit_action.description = "Conflicting exit label"
    impulse = [CustomerAction(nav="path", action=Action.BUY, target=(1, 0), face=Face.W,
                              product_sku="sku-b")] if shopping == "impulse" else []
    _, result = _execute(collision_store, ordering, intent, impulse)
    events = result.timeline
    assert events[-1].action == Action.EXIT
    assert (events[-1].x, events[-1].y) == collision_store.exits[0].position
    assert sum(e.action == Action.ENTER for e in events) == 1
    assert sum(e.action == Action.EXIT for e in events) == 1
    assert events[0].description != exit_action.description
    assert result.total_spent == {"none": 0, "planned": 300, "impulse": 200}[shopping]
    if shopping != "none":
        pay = next(e for e in events if e.action == Action.PAY)
        assert result.duration_sec >= pay.elapsed_sec + pay.duration
