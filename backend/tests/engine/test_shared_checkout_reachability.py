"""Tills in a disconnected customer area cannot absorb this area's queue."""

import pytest

from store_emulator.domain.operations import CrewShift, OperationsConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.routing.test_reachable_service_routes import divided_visit


@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("crew", ["tills", "crew", "roster"])
@pytest.mark.parametrize("reverse", [False, True])
def test_only_reachable_tills_serve_the_queue(transpose, side, crew, reverse):
    store, decision, _ = divided_visit("two", transpose, side, "local")
    store.weekly_schedule = [DaySchedule(day=Weekday.MON, open_hour=10, close_hour=12)]
    if reverse:
        store.racks.reverse()
        # Preserve the original entrance; only the checkout ordering is reversed.
        entry = next(r for r in store.racks if r.id == "entry")
        store.racks.remove(entry)
        store.racks.insert(0, entry)
    planned = [execute_decision(store, f"p{i}", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)
               for i in range(3)]
    config = OperationsConfig(stock_per_facing=20, restock_every_min=None, substitute_share=0,
                              checkout_base_sec=60, checkout_item_sec=0, patience_sec=7200, patience_sd=0,
                              crowd_limit=None, crew=None if crew == "tills" else 2,
                              crew_shifts=[CrewShift(start=10, end=12, staff=2)] if crew == "roster" else [])
    results, report = resolve_shared_store(store, planned, config, seed=42)
    assert [result.queue_wait_sec for result in results] == [0, 60, 120]
    assert [result.total_spent for result in results] == [100, 100, 100]
    assert report.queued == 3 and report.abandoned == 0
    if crew != "tills":
        assert {task.rack_id for task in report.crew_tasks if task.kind == "till"} == {"local-counter"}
    assert all(result.queue_wait_sec == 0 for result in planned)


@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("side", [0, 1])
def test_a_counter_with_service_tiles_on_both_sides_shares_one_capacity(transpose, side):
    store, decision, _ = divided_visit("split", transpose, side, "local")
    planned = [execute_decision(store, f"p{i}", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)
               for i in range(3)]
    results, _ = resolve_shared_store(store, planned, OperationsConfig(
        stock_per_facing=20, checkout_base_sec=60, checkout_item_sec=0, patience_sec=7200, patience_sd=0,
        restock_every_min=None, crowd_limit=None), seed=42)
    assert [result.queue_wait_sec for result in results] == [0, 60, 120]
    assert all(any(event.action == Action.PAY for event in result.timeline) for result in results)


@pytest.mark.parametrize("connected", [False, True])
@pytest.mark.parametrize("crew", [None, 2])
def test_unreachable_capacity_cannot_hide_abandonment_and_lost_sales(connected, crew):
    store, decision, _ = divided_visit("two", False, 0, "local")
    if connected:
        store.racks = [r for r in store.racks if not r.id.startswith("wall-")]
    planned = [execute_decision(store, f"p{i}", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)
               for i in range(3)]
    results, report = resolve_shared_store(store, planned, OperationsConfig(
        stock_per_facing=20, checkout_base_sec=60, checkout_item_sec=0, patience_sec=90, patience_sd=0,
        restock_every_min=None, crew=crew, crowd_limit=None), seed=42)
    assert [r.queue_wait_sec for r in results] == ([0, 0, 60] if connected else [0, 60, 90])
    assert sum(r.total_spent for r in results) == (300 if connected else 200)
    assert report.abandoned_revenue == (0 if connected else 100)
    assert report.abandoned == (0 if connected else 1)
    assert sum(s.sold_units for s in report.stockouts) == 0  # ample stock; the loss is at checkout


@pytest.mark.parametrize("crew", [None, 2])
def test_staffing_a_remote_counter_does_not_open_the_local_one(crew):
    store, decision, _ = divided_visit("two", False, 0, "local")
    store.weekly_schedule = [DaySchedule(day=Weekday.MON, open_hour=10, close_hour=12)]
    remote = next(r for r in store.racks if r.id == "remote-counter")
    store.racks.remove(remote)
    store.racks.insert(1, remote)  # staffing one till/crew member now opens only the remote counter
    planned = [execute_decision(store, "p", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)]
    pay = next(e for e in planned[0].timeline if e.action == Action.PAY)
    config = OperationsConfig(checkout_base_sec=60, checkout_item_sec=0, patience_sec=7200, patience_sd=0,
                              restock_every_min=None, crowd_limit=None, crew=crew,
                              till_schedule={"10": 1, "11": 2} if crew is None else {},
                              crew_schedule={"10": 1, "11": 2} if crew is not None else {})
    results, _ = resolve_shared_store(store, planned, config, seed=42)
    assert results[0].queue_wait_sec == 3600 - pay.elapsed_sec
    assert results[0].total_spent == 100 and not results[0].left_queue
