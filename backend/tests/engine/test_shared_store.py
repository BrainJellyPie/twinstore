"""Shoppers share one store: stock runs out, staff refill it, and the tills have a line."""

import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.invariants import check_buy_consistency
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine
from store_emulator.engine.simulation.shared_store import counters_needed, resolve_shared_store
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner


def _store(counters: int = 1) -> Store:
    shelf = Rack(id="A", type=RackType.SHELF, shape=[[1]], position=(0, 0), rack_name="Snacks", slots=[
        Slot(block=0, face=Face.E, level=1, items=[
            SlotItem(sku="chips", name="Chips", price=300),
            SlotItem(sku="nuts", name="Nuts", price=350),
            SlotItem(sku="caviar", name="Caviar", price=9000),
        ]),
    ])
    tills = [Rack(id=f"C{i}", type=RackType.COUNTER, shape=[[1]], position=(4, i)) for i in range(counters)]
    return Store(id="s", name="S", type="convenience", grid_size=(6, 6), racks=[shelf, *tills],
                 weekly_schedule=[DaySchedule(day=Weekday(d), open_hour=8, close_hour=22) for d in range(1, 8)])


def _shopper(pid: str, arrival: str, buys: list[tuple[str, int]], *, pay: bool = True,
             day: Weekday = Weekday.MON) -> CustomerResult:
    prices = {"chips": 300, "nuts": 350, "caviar": 9000}
    timeline = [TimelineEvent(elapsed_sec=0, x=1, y=5, action=Action.ENTER)]
    t = 10
    for sku, quantity in buys:
        timeline.append(TimelineEvent(elapsed_sec=t, x=1, y=0, action=Action.BUY, target_rack="A", face=Face.E,
                                      product_sku=sku, product_name=sku.title(), price=prices[sku],
                                      quantity=quantity, duration=5, origin="planned"))
        t += 5
    if pay:
        timeline.append(TimelineEvent(elapsed_sec=t + 10, x=4, y=1, action=Action.PAY, target_rack="C0", duration=20))
    timeline.append(TimelineEvent(elapsed_sec=t + 40, x=5, y=5, action=Action.EXIT))
    spent = sum(prices[s] * q for s, q in buys)
    return CustomerResult(persona_id=pid, day=day, arrival_time=arrival, timeline=timeline, total_spent=spent)


_NO_LINE = dict(checkout_base_sec=1, checkout_item_sec=0, restock_every_min=None)


def test_what_one_shopper_takes_is_gone_for_the_next():
    shoppers = [_shopper(f"p{i}", f"10:0{i}:00", [("chips", 1)]) for i in range(3)]
    config = OperationsConfig(stock_per_facing=2, substitute_share=0.0, **_NO_LINE)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert [r.total_spent for r in results] == [300, 300, 0]
    third = results[2].timeline[1]
    assert third.action == Action.BROWSE and "sold out" in third.description
    assert results[2].lost_units == 1
    chips = next(s for s in report.stockouts if s.sku == "chips")
    assert (chips.sold_units, chips.lost_units, chips.lost_revenue, chips.first_out) == (2, 1, 300, "10:01:10")
    assert report.lost_units == 1 and report.lost_revenue == 300 and report.shoppers_hit == 1
    # The input is left as it was.
    assert shoppers[2].timeline[1].action == Action.BUY and shoppers[2].total_spent == 300


def test_a_sold_out_product_is_replaced_from_the_same_face_at_the_nearest_price():
    shoppers = [_shopper("p0", "10:00:00", [("chips", 1)]), _shopper("p1", "10:05:00", [("chips", 2)])]
    config = OperationsConfig(stock_per_facing=1, substitute_share=1.0, **_NO_LINE)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    pick = results[1].timeline[1]
    assert (pick.action, pick.product_sku, pick.price, pick.quantity) == (Action.BUY, "nuts", 350, 1)
    assert "Chips was sold out" in pick.description
    assert results[1].substituted_units == 1 and results[1].lost_units == 1   # wanted 2, only one nut left
    assert report.substituted_units == 1 and report.substituted_revenue == 350
    assert check_buy_consistency(_store(), results) == []


def test_a_short_shelf_sells_what_is_left():
    results, report = resolve_shared_store(
        _store(), [_shopper("p0", "10:00:00", [("chips", 5)])],
        OperationsConfig(stock_per_facing=3, substitute_share=1.0, **_NO_LINE), seed=1)
    assert results[0].timeline[1].quantity == 3 and results[0].total_spent == 900
    assert results[0].lost_units == 2 and report.lost_units == 2


def test_staff_refill_the_shelves_on_schedule_and_the_time_empty_is_counted():
    shoppers = [_shopper("p0", "10:00:00", [("chips", 1)]), _shopper("p1", "10:20:00", [("chips", 1)]),
                _shopper("p2", "10:31:00", [("chips", 1)])]
    config = OperationsConfig(stock_per_facing=1, substitute_share=0.0, restock_every_min=30,
                              checkout_base_sec=1, checkout_item_sec=0)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert [r.total_spent for r in results] == [300, 0, 300]
    chips = next(s for s in report.stockouts if s.sku == "chips")
    # Empty from 10:00:10 until the 10:30 refill, then from 10:31:10 to closing at 22:00.
    assert chips.minutes_out == pytest.approx(29 + 50 / 60 + 11 * 60 + 28 + 50 / 60, abs=0.1)
    assert report.restocks >= 1


def test_every_day_opens_with_full_shelves():
    shoppers = [_shopper("mon", "10:00:00", [("chips", 1)], day=Weekday.MON),
                _shopper("tue", "10:00:00", [("chips", 1)], day=Weekday.TUE)]
    results, report = resolve_shared_store(
        _store(), shoppers, OperationsConfig(stock_per_facing=1, substitute_share=0.0, **_NO_LINE), seed=1)
    assert [r.total_spent for r in results] == [300, 300] and report.days == 2 and report.lost_units == 0


def test_shoppers_wait_for_a_free_till_and_the_rest_of_the_visit_moves():
    shoppers = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(3)]
    config = OperationsConfig(checkout_base_sec=57, checkout_item_sec=3, patience_sec=1000, patience_sd=0,
                              restock_every_min=None)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert [r.queue_wait_sec for r in results] == [0, 60, 120]
    pay = results[2].timeline[2]
    assert pay.action == Action.PAY and pay.elapsed_sec == 25 + 120 and pay.duration == 60
    assert results[2].timeline[-1].elapsed_sec == 145 + 60 + 10       # left 10 s after paying, as planned
    assert results[2].leave_time == "10:03:35"
    assert report.queued == 3 and report.avg_wait_sec == 60 and report.max_wait_sec == 120
    assert report.hours[0].hour == "10" and report.hours[0].arrivals == 3


def test_more_tills_shorten_the_line():
    shoppers = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(3)]
    config = OperationsConfig(checkout_base_sec=57, checkout_item_sec=3, patience_sd=0, restock_every_min=None)
    results, report = resolve_shared_store(_store(counters=3), shoppers, config, seed=1)
    assert [r.queue_wait_sec for r in results] == [0, 0, 0] and report.counters == 3
    one_open = config.model_copy(update={"open_counters": 1})
    results, report = resolve_shared_store(_store(counters=3), shoppers, one_open, seed=1)
    assert [r.queue_wait_sec for r in results] == [0, 60, 120]
    assert (report.counters, report.counters_in_layout) == (1, 3)


def test_a_shopper_out_of_patience_leaves_the_basket_on_the_shelf():
    shoppers = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(3)]
    shoppers.append(_shopper("late", "10:03:00", [("chips", 1)]))
    config = OperationsConfig(stock_per_facing=3, substitute_share=0.0, checkout_base_sec=57, checkout_item_sec=3,
                              patience_sec=90, patience_sd=0, restock_every_min=None)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    gone = results[2]
    assert gone.left_queue and gone.queue_wait_sec == 90 and gone.total_spent == 0
    assert gone.timeline[1].action == Action.BROWSE and "put back" in gone.timeline[1].description
    assert gone.timeline[2].action == Action.WANDER and gone.timeline[2].duration == 90
    assert gone.timeline[-1].elapsed_sec == 25 + 90 + 10
    # The chips the shopper put back at 10:01:55 are on the shelf for the next one.
    assert results[3].total_spent == 300
    assert report.abandoned == 1 and report.abandoned_units == 1 and report.abandoned_revenue == 300
    assert report.hours[0].abandoned == 1


def test_a_shopper_with_nothing_left_to_buy_skips_the_tills():
    shoppers = [_shopper("p0", "10:00:00", [("caviar", 1)]), _shopper("p1", "10:00:30", [("caviar", 1)])]
    config = OperationsConfig(stock_per_facing=1, substitute_share=0.0, checkout_base_sec=600,
                              restock_every_min=None)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert results[1].timeline[2].action == Action.WANDER and results[1].queue_wait_sec == 0
    assert report.queued == 1


def test_patience_and_substitution_follow_the_shopper_not_the_layout():
    shoppers = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(30)]
    config = OperationsConfig(stock_per_facing=10, substitute_share=0.5, checkout_base_sec=40, patience_sec=200,
                              restock_every_min=None)
    first = resolve_shared_store(_store(), shoppers, config, seed=7)
    again = resolve_shared_store(_store(), shoppers, config, seed=7)
    assert [r.model_dump() for r in first[0]] == [r.model_dump() for r in again[0]]
    assert first[1] == again[1]
    other = resolve_shared_store(_store(), shoppers, config, seed=8)
    assert [r.model_dump() for r in other[0]] != [r.model_dump() for r in first[0]]


def test_tills_needed_keep_the_hour_within_the_target_wait():
    config = OperationsConfig(checkout_base_sec=60, checkout_item_sec=0, target_wait_sec=10)
    burst = [(Weekday.MON, 36_000.0, 1)] * 4
    assert counters_needed(burst, config) == {"10": 4}
    spread = [(Weekday.MON, 36_000.0 + 120 * i, 1) for i in range(10)]
    assert counters_needed(spread, config) == {"10": 1}


def test_a_layout_without_tills_has_no_line():
    store = _store(counters=0)
    results, report = resolve_shared_store(store, [_shopper("p0", "10:00:00", [("chips", 1)])],
                                           OperationsConfig(), seed=1)
    assert report.counters == 0 and report.queued == 0 and results[0].total_spent == 300


def _crowd(count: int) -> list[Persona]:
    return [Persona(id=f"c{i}", day=Weekday.SAT, arrival_hour=17, identity="shopper", age_group="30s",
                    gender="Female", description="Saturday rush", intent="snacks", purpose="snacks",
                    budget_min=1000, budget_max=6000) for i in range(count)]


def _run(store: Store, people: list[Persona], operations: OperationsConfig | None):
    config = SimulationConfig(engine_type=EngineType.RULE_BASED, seed=3, operations=operations)
    pathfinder = AStarPathFinder()
    runner = PerCustomerSimulationRunner(config, RuleBasedEngine(pathfinder, config), pathfinder, sample_cue,
                                         BEHAVIOR_PATTERNS)
    return asyncio.run(runner.run(store, people, path_heatmap=False))


def test_a_crowded_day_in_a_shared_store_runs_out_and_queues_end_to_end():
    store = generate_store("urban_cvs")
    people = _crowd(120)
    alone, alone_customers = _run(store, people, None)
    shared, customers = _run(store, people, OperationsConfig(stock_per_facing=1, restock_every_min=None,
                                                             open_counters=1, patience_sec=120))
    assert alone.operations is None
    report = shared.operations
    assert report is not None and report.counters == 1
    assert report.stockout_faces > 0 and report.lost_units + report.substituted_units > 0
    assert report.queued > 0 and report.max_wait_sec > 0
    # Revenue is what shoppers actually paid for, and no pick names a product the face does not carry.
    assert shared.summary.total_revenue == sum(c.total_spent for c in customers)
    assert shared.summary.total_revenue < alone.summary.total_revenue
    assert shared.diagnostics.buy_violations == alone.diagnostics.buy_violations
    assert {c.persona_id for c in customers} == {c.persona_id for c in alone_customers}


def test_plenty_of_stock_and_tills_leave_the_day_as_it_was():
    store = generate_store("urban_cvs")
    people = _crowd(20)
    alone, alone_customers = _run(store, people, None)
    shared, customers = _run(store, people, OperationsConfig(stock_per_facing=1000, checkout_base_sec=0,
                                                             checkout_item_sec=0, open_counters=50))
    assert shared.summary.total_revenue == alone.summary.total_revenue
    assert [c.total_spent for c in customers] == [c.total_spent for c in alone_customers]
    assert shared.operations is not None and shared.operations.lost_units == 0


def test_a_shopper_meets_a_sold_out_product_the_same_way_whatever_the_route():
    config = OperationsConfig(stock_per_facing=1, substitute_share=0.5, **_NO_LINE)
    outcomes = set()
    for detour in (0, 1, 3):
        first = _shopper("p0", "10:00:00", [("chips", 1)])
        second = _shopper("p1", "10:05:00", [("chips", 1)])
        for i in range(detour):   # a longer walk before the same pick
            second.timeline.insert(1, TimelineEvent(elapsed_sec=1 + i, x=1, y=4 - i, action=Action.MOVE))
        results, _ = resolve_shared_store(_store(), [first, second], config, seed=11)
        pick = next(e for e in results[1].timeline if e.product_sku in ("chips", "nuts"))
        outcomes.add((pick.action, pick.product_sku))
    assert len(outcomes) == 1
