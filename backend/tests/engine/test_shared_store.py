"""Shoppers share one store: stock runs out, staff refill it, and the tills have a line."""

import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.operations import OperationsConfig, OperationsCosts
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Action, Face, Weekday, stable_seed
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
             day: Weekday = Weekday.MON, origin: str = "planned") -> CustomerResult:
    prices = {"chips": 300, "nuts": 350, "caviar": 9000}
    timeline = [TimelineEvent(elapsed_sec=0, x=1, y=5, action=Action.ENTER)]
    t = 10
    for sku, quantity in buys:
        timeline.append(TimelineEvent(elapsed_sec=t, x=1, y=0, action=Action.BUY, target_rack="A", face=Face.E,
                                      product_sku=sku, product_name=sku.title(), price=prices[sku],
                                      quantity=quantity, duration=5, origin=origin))
        t += 5
    if pay:
        timeline.append(TimelineEvent(elapsed_sec=t + 10, x=4, y=1, action=Action.PAY, target_rack="C0", duration=20))
    timeline.append(TimelineEvent(elapsed_sec=t + 40, x=5, y=5, action=Action.EXIT))
    spent = sum(prices[s] * q for s, q in buys)
    return CustomerResult(persona_id=pid, day=day, arrival_time=arrival, timeline=timeline, total_spent=spent)


_NO_LINE = dict(checkout_base_sec=1, checkout_item_sec=0, restock_every_min=None)


@pytest.mark.parametrize("restock", [None, 5, 120])
@pytest.mark.parametrize("substitute", [0.0, 1.0])
def test_zero_stock_overrides_count_as_empty_from_opening_each_day(restock, substitute):
    store = _store()
    shoppers = [_shopper("mon", "10:00:00", [("chips", 1)], day=Weekday.MON),
                _shopper("tue", "10:00:00", [("chips", 1)], day=Weekday.TUE)]
    config = OperationsConfig(stock_overrides={"chips": 0}, substitute_share=substitute,
                              restock_every_min=restock, checkout_base_sec=1, checkout_item_sec=0)
    results, report = resolve_shared_store(store, shoppers, config, seed=1)
    chips = next(s for s in report.stockouts if s.sku == "chips")
    assert report.stockout_faces == 1 and report.shoppers_hit == 2
    assert chips.first_out == "08:00:00" and chips.minutes_out == 2 * 14 * 60
    assert chips.stock == 0 and chips.sold_units == 0
    assert chips.lost_units == (0 if substitute else 2)
    assert chips.substituted_units == (2 if substitute else 0)
    assert [r.total_spent for r in results] == ([350, 350] if substitute else [0, 0])
    assert check_buy_consistency(store, results) == []
    assert all(r.total_spent == 300 for r in shoppers)


def test_maximum_stock_override_stays_per_product_and_shelf_level():
    store = _store()
    store.racks[0].slots.append(store.racks[0].slots[0].model_copy(update={"level": 2}, deep=True))
    results, report = resolve_shared_store(
        store, [_shopper("p", "10:00:00", [("chips", 20_001)])],
        OperationsConfig(stock_overrides={"chips": 10_000}, substitute_share=0, **_NO_LINE), seed=1)
    chips = next(s for s in report.stockouts if s.sku == "chips")
    assert chips.stock == chips.sold_units == 20_000
    assert results[0].total_spent == 6_000_000 and report.lost_units == 1


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


_SEED = stable_seed(3, 0)


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
                                                             checkout_item_sec=0, open_counters=50, crowd_limit=None))
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


def test_tills_follow_an_hourly_schedule_on_one_shared_line():
    shoppers = [_shopper(f"p{i}", "10:59:00", [("chips", 1)]) for i in range(3)]
    config = OperationsConfig(checkout_base_sec=57, checkout_item_sec=3, patience_sec=3600, patience_sd=0,
                              restock_every_min=None, till_schedule={"10": 1, "11": 3})
    results, report = resolve_shared_store(_store(counters=3), shoppers, config, seed=1)
    # One till until 11:00, then all three: the second shopper starts at 11:00, the third too.
    assert [r.queue_wait_sec for r in results] == [0, 35, 35]
    closed = config.model_copy(update={"till_schedule": {"10": 0}})
    results, report = resolve_shared_store(_store(counters=3), shoppers, closed, seed=1)
    assert [r.queue_wait_sec for r in results] == [35, 35, 35]
    assert {h.hour: h.counters_open for h in report.hours} == {"10": 0}


def test_till_hours_count_the_staffed_hours_of_the_day():
    config = OperationsConfig(restock_every_min=None, till_schedule={"08": 0, "12": 3})
    _, report = resolve_shared_store(_store(counters=3), [_shopper("p0", "10:00:00", [("chips", 1)])], config, seed=1)
    # Open 08–22: hour 08 closed, 12 with three tills, the other twelve hours with all three (no run-wide number).
    assert report.till_hours == 13 * 3


@pytest.mark.parametrize("schedule", [{"24": 1}, {"9": 1}, {"ab": 1}, {"10": 51}, {"10": -1},
                                      {"０１": 1}, {"٠١": 1}, {" 1": 1}, {"+1": 1}, {"-1": 1}])
def test_impossible_till_schedules_are_refused(schedule):
    with pytest.raises(ValueError):
        OperationsConfig(till_schedule=schedule)


def test_till_schedule_accepts_both_ends_of_the_day_and_sorts_hours():
    config = OperationsConfig(till_schedule={"23": 50, "00": 0, "12": 1})
    assert list(config.till_schedule.items()) == [("00", 0), ("12", 1), ("23", 50)]


@pytest.mark.parametrize("holding_cost", [0, 200, 400])
def test_a_plan_can_stock_a_product_that_starts_sold_out_when_it_pays(holding_cost):
    from store_emulator.engine.simulation.operations_plan import plan_operations
    store = _store()
    customers = [_shopper("p", "10:00:00", [("chips", 1)])]
    current = OperationsConfig(stock_overrides={"chips": 0}, substitute_share=0, **_NO_LINE)
    before = customers[0].model_dump()
    plan = plan_operations(store, customers, current, OperationsCosts(stock_unit_day=holding_cost), seed=1)
    profitable = holding_cost < 300
    assert plan.current.revenue == 0
    assert plan.best.revenue == (300 if profitable else 0)
    assert plan.config.stock_overrides["chips"] == (1 if profitable else 0)
    assert plan.raised_skus == (["chips"] if profitable else [])
    assert plan.best.net >= plan.current.net
    assert current.stock_overrides == {"chips": 0} and customers[0].model_dump() == before


def test_a_replay_with_the_runs_own_plan_reproduces_it():
    from store_emulator.engine.simulation.operations_plan import replay
    store = generate_store("urban_cvs")
    config = OperationsConfig(stock_per_facing=2, open_counters=1, patience_sec=120)
    shared, customers = _run(store, _crowd(80), config)
    outcome, report, results = replay(store, shared.planned_customers, config, OperationsCosts(), seed=_SEED)
    assert outcome.revenue == shared.summary.total_revenue
    assert report == shared.operations
    assert [r.model_dump() for r in results] == [c.model_dump() for c in customers]


def test_a_plan_never_does_worse_than_the_current_one_and_counts_its_costs():
    from store_emulator.engine.simulation.operations_plan import plan_operations
    store = generate_store("urban_cvs")
    _, customers = _run(store, _crowd(150), None)
    current = OperationsConfig(stock_per_facing=2, restock_every_min=None, patience_sec=120)
    costs = OperationsCosts(till_hour=1500, restock_round=500, stock_unit_day=1)
    plan = plan_operations(store, customers, current, costs, seed=_SEED)
    assert plan.best.net >= plan.current.net and plan.replays > 10
    assert plan.best.labor_cost == round(plan.best.till_hours * 1500)
    assert plan.best.net == plan.best.revenue - plan.best.labor_cost - plan.best.restock_cost - plan.best.holding_cost
    free = plan_operations(store, customers, current, OperationsCosts(), seed=_SEED)
    assert free.best.lost_revenue <= free.current.lost_revenue and free.best.revenue >= free.current.revenue


def test_a_plan_out_of_time_answers_with_the_best_found_so_far():
    from store_emulator.engine.simulation.operations_plan import plan_operations
    store = generate_store("urban_cvs")
    _, customers = _run(store, _crowd(40), None)
    plan = plan_operations(store, customers, OperationsConfig(), OperationsCosts(), seed=_SEED, time_budget_sec=0)
    assert not plan.complete and plan.replays == 1 and plan.config == OperationsConfig()
    assert plan_operations(store, customers, OperationsConfig(), OperationsCosts(), seed=_SEED).complete


def test_a_crowded_shelf_puts_shoppers_off_their_unplanned_picks():
    crowd = [_shopper(f"p{i}", "10:00:00", [("chips", 1)], origin="impulse") for i in range(5)]
    config = OperationsConfig(stock_per_facing=50, crowd_limit=4, crowd_skip=1.0, **_NO_LINE)
    results, report = resolve_shared_store(_store(), crowd, config, seed=1)
    assert all(r.total_spent == 0 for r in results)
    assert "too crowded" in results[0].timeline[1].description
    assert (report.crowd_skipped_units, report.crowd_skipped_revenue) == (5, 1500)
    # Planned picks are made however crowded; a quieter shelf keeps the impulse ones; crowding can be off.
    planned = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(5)]
    assert all(r.total_spent == 300 for r in resolve_shared_store(_store(), planned, config, seed=1)[0])
    quiet = crowd[:3]
    assert all(r.total_spent == 300 for r in resolve_shared_store(_store(), quiet, config, seed=1)[0])
    off = config.model_copy(update={"crowd_limit": None})
    assert resolve_shared_store(_store(), crowd, off, seed=1)[1].crowd_skipped_units == 0


def test_the_report_says_when_each_face_stood_empty():
    shoppers = [_shopper("p0", "10:00:00", [("chips", 1)]), _shopper("p2", "10:31:00", [("chips", 1)])]
    config = OperationsConfig(stock_per_facing=1, substitute_share=0.0, restock_every_min=30,
                              checkout_base_sec=1, checkout_item_sec=0)
    _, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert [(s.rack_id, s.face, s.sku, s.start, s.end) for s in report.empty_spells] == [
        ("A", "E", "chips", 36010, 37800), ("A", "E", "chips", 37870, 79200)]
    assert report.empty_spells[0].name == "Chips" and report.empty_spells[0].day == 1


def test_refills_come_from_the_backroom_and_stop_when_it_runs_dry():
    shoppers = [_shopper("p0", "10:00:00", [("chips", 1)]), _shopper("p1", "10:31:00", [("chips", 1)]),
                _shopper("p2", "11:05:00", [("chips", 1)])]
    config = OperationsConfig(stock_per_facing=1, backroom_per_product=1, substitute_share=0.0, restock_every_min=30,
                              checkout_base_sec=1, checkout_item_sec=0, crowd_limit=None)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert [r.total_spent for r in results] == [300, 300, 0]
    chips = next(b for b in report.backroom if b.sku == "chips")
    assert (chips.level, chips.refilled, chips.dry_day, chips.dry_at) == (1, 1, 1, "11:00:00")
    assert report.refill_short_units == chips.short_units >= 1
    assert report.backroom_units == 3   # chips, nuts and caviar, one each


def test_the_shelves_keep_last_nights_stock_and_a_morning_delivery_refills_the_backroom():
    week = [_shopper("mon", "10:00:00", [("chips", 1)], day=Weekday.MON),
            _shopper("tue", "10:00:00", [("chips", 1)], day=Weekday.TUE),
            _shopper("wed", "10:00:00", [("chips", 1)], day=Weekday.WED)]
    base = dict(stock_per_facing=1, substitute_share=0.0, restock_every_min=None, checkout_base_sec=1,
                checkout_item_sec=0, crowd_limit=None)
    # No backroom at all: nothing refills the shelf after Monday.
    results, report = resolve_shared_store(_store(), week, OperationsConfig(backroom_per_product=0, **base), seed=1)
    assert [r.total_spent for r in results] == [300, 0, 0]
    chips = next(s for s in report.stockouts if s.sku == "chips")
    assert chips.lost_units == 2 and report.deliveries == 0
    # One unit in the backroom, no deliveries: it fills Tuesday's shelf, then nothing is left for Wednesday.
    no_truck = OperationsConfig(backroom_per_product=1, daily_delivery=False, **base)
    assert [r.total_spent for r in resolve_shared_store(_store(), week, no_truck, seed=1)[0]] == [300, 300, 0]
    # With a delivery each morning the backroom is back to one unit before Wednesday's shelf is filled.
    truck = no_truck.model_copy(update={"daily_delivery": True})
    results, report = resolve_shared_store(_store(), week, truck, seed=1)
    assert [r.total_spent for r in results] == [300, 300, 300] and report.deliveries == 1
    # An endless backroom (the default) opens every day with full shelves, as before.
    assert [r.total_spent for r in resolve_shared_store(_store(), week, OperationsConfig(**base), seed=1)[0]] == [300] * 3


def test_units_in_the_backroom_are_held_at_a_cost_too():
    from store_emulator.engine.simulation.operations_plan import replay
    shoppers = [_shopper("p0", "10:00:00", [("chips", 1)])]
    config = OperationsConfig(stock_per_facing=2, backroom_per_product=10, crowd_limit=None, **_NO_LINE)
    outcome, _, _ = replay(_store(), shoppers, config, OperationsCosts(stock_unit_day=1), seed=1)
    assert outcome.stock_units == 3 * 2 + 3 * 10 and outcome.holding_cost == 36


@pytest.mark.parametrize("bad", [{"backroom_per_product": -1}, {"backroom_overrides": {"chips": -1}},
                                 {"backroom_overrides": {"chips": 1_000_001}}])
def test_impossible_backrooms_are_refused(bad):
    with pytest.raises(ValueError):
        OperationsConfig(**bad)


# One crew for the tills and the shelves.
_CREW = dict(substitute_share=0.0, checkout_base_sec=1, checkout_item_sec=0, crowd_limit=None, refill_unit_sec=0)


def test_a_crew_member_refills_a_face_once_it_is_down_to_its_refill_point():
    shoppers = [_shopper("p0", "10:00:00", [("chips", 1)]), _shopper("p1", "10:00:20", [("chips", 2)]),
                _shopper("p2", "10:01:00", [("chips", 1)])]
    config = OperationsConfig(crew=2, stock_per_facing=2, refill_at=0.5, refill_face_sec=60, **_CREW)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    # p0 leaves one: down to half, the second crew member goes (60 s). p1 finds one of two; at 10:01:10 the face is
    # full again just as p2 takes from it, and down to half once more.
    assert [r.total_spent for r in results] == [300, 300, 300] and results[1].lost_units == 1
    assert report.face_refills == 2 and report.refill_wait_min == 1.0 and report.refills_unfinished == 0
    assert report.restocks == 0 and report.crew_refill_hours == round(120 / 3600, 2)
    assert report.crew_hours == 2 * 14 and report.till_hours == 14 and report.counters == 1
    assert {h.hour: (h.counters_open, h.crew_on_duty) for h in report.hours} == {"10": (1, 2)}
    # Who did what, for playback: the second member refilled chips twice, the first served the three at the till.
    refills = [(c.member, c.rack_id, c.face, c.sku, c.start, c.end) for c in report.crew_tasks if c.kind == "refill"]
    assert refills == [(1, "A", "E", "chips", 36010, 36070), (1, "A", "E", "chips", 36070, 36130)]
    tills = [(c.member, c.rack_id, c.start) for c in report.crew_tasks if c.kind == "till"]
    assert tills == [(0, "C0", 36025), (0, "C0", 36045), (0, "C0", 36085)]
    assert [c.start for c in report.crew_tasks] == sorted(c.start for c in report.crew_tasks)


@pytest.mark.parametrize("crew, wait", [(1, 105), (2, 0)])
def test_a_refill_takes_the_only_person_on_duty_away_from_the_till(crew, wait):
    shoppers = [_shopper("p0", "10:00:00", [("chips", 1)])]
    config = OperationsConfig(crew=crew, stock_per_facing=2, refill_face_sec=120, **_CREW)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    # The pick at 10:00:10 leaves the face at half; alone, the cashier refills it until 10:02:10 while the shopper
    # waits from 10:00:25. With two on duty the first stays at the till.
    assert results[0].queue_wait_sec == wait and report.face_refills == 1


def test_crew_hours_follow_the_hourly_crew_schedule():
    config = OperationsConfig(crew=1, crew_schedule={"08": 0, "12": 2}, **_CREW)
    _, report = resolve_shared_store(_store(), [_shopper("p0", "10:00:00", [("chips", 1)])], config, seed=1)
    assert report.crew_hours == 0 + 2 + 12 * 1 and report.till_hours == 0 + 1 + 12


def test_a_crew_finds_an_empty_backroom_once_and_moves_on():
    shoppers = [_shopper("p0", "10:00:00", [("chips", 7)]), _shopper("p1", "10:05:00", [("chips", 5)])]
    config = OperationsConfig(crew=2, stock_per_facing=12, backroom_per_product=0, **_CREW)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert [r.total_spent for r in results] == [2100, 1500]
    assert report.face_refills == 0 and report.refill_short_units == 7
    assert [(b.sku, b.short_units) for b in report.backroom] == [("chips", 7)]


def test_faces_still_waiting_at_closing_are_counted():
    shoppers = [_shopper("late", "21:50:00", [("chips", 1), ("nuts", 1)], pay=False)]
    config = OperationsConfig(crew=1, stock_per_facing=2, refill_face_sec=1800, **_CREW)
    _, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    # The only crew member is refilling chips until 22:20; nuts waits, and nobody refills after closing.
    assert report.face_refills == 1 and report.refills_unfinished == 1 and report.refill_backlog_max == 1


@pytest.mark.parametrize("bad", [{"crew_schedule": {"10": 1}}, {"crew": 1, "crew_schedule": {"24": 1}},
                                 {"crew": 1, "crew_schedule": {"10": 101}}, {"crew": 0}, {"crew": 1, "refill_at": 1}])
def test_impossible_crews_are_refused(bad):
    with pytest.raises(ValueError):
        OperationsConfig(**bad)


def test_a_crew_replay_reproduces_the_run_and_a_crew_plan_counts_crew_hours():
    from store_emulator.engine.simulation.operations_plan import plan_operations, replay
    store = generate_store("urban_cvs")
    config = OperationsConfig(crew=2, stock_per_facing=2, patience_sec=120)
    shared, customers = _run(store, _crowd(80), config)
    assert shared.operations is not None and shared.operations.face_refills > 0
    outcome, report, results = replay(store, shared.planned_customers, config, OperationsCosts(), seed=_SEED)
    assert outcome.revenue == shared.summary.total_revenue and report == shared.operations
    assert [r.model_dump() for r in results] == [c.model_dump() for c in customers]
    costs = OperationsCosts(till_hour=1500, stock_unit_day=1)
    plan = plan_operations(store, shared.planned_customers, config, costs, seed=_SEED)
    assert plan.best.net >= plan.current.net and plan.config.crew is not None
    assert plan.best.labor_cost == round(plan.best.crew_hours * 1500) and plan.best.crew_hours > 0
    assert plan.current.labor_cost == round(report.crew_hours * 1500)
    assert outcome.face_refills == report.face_refills > 0 and outcome.restocks == 0


@pytest.mark.parametrize("duration, arrival, crowded", [
    (600, "10:10:10", False), (610, "10:10:10", False),
    (611, "10:10:10", True), (1200, "10:10:10", True),
    (20, "10:00:19", True), (20, "10:00:20", False), (20, "10:00:21", False),
])
def test_crowding_counts_long_browsing_stops_until_their_end(duration, arrival, crowded):
    observer = _shopper("observer", "10:00:00", [], pay=False)
    observer.timeline.insert(1, TimelineEvent(elapsed_sec=10, x=1, y=0, action=Action.BROWSE,
                                             target_rack="A", face=Face.E, duration=duration))
    observer.timeline[-1].elapsed_sec = duration + 20
    buyer = _shopper("buyer", arrival, [("chips", 1)], origin="impulse")
    before = [r.model_dump() for r in [observer, buyer]]
    config = OperationsConfig(stock_per_facing=10, crowd_limit=2, crowd_skip=1, **_NO_LINE)
    results, report = resolve_shared_store(_store(), [observer, buyer], config, seed=1)
    assert report.crowd_skipped_units == int(crowded)
    assert results[1].total_spent == (0 if crowded else 300)
    assert [r.model_dump() for r in [observer, buyer]] == before


# A roster of shifts.
def test_shifts_put_their_staff_on_duty_by_weekday_and_hour():
    from store_emulator.domain.operations import CrewShift
    shifts = [CrewShift(start=8, end=12), CrewShift(start=12, end=22, days=[1], staff=2)]
    config = OperationsConfig(crew=1, crew_shifts=shifts, **_CREW)
    assert [config.crew_on_duty(1, hour) for hour in (7, 8, 11, 12, 21, 22)] == [0, 1, 1, 2, 2, 0]
    assert config.crew_on_duty(2, 13) == 0
    shoppers = [_shopper("mon", "13:00:00", [("chips", 1)], day=Weekday.MON),
                _shopper("tue", "13:00:00", [("chips", 1)], day=Weekday.TUE)]
    results, report = resolve_shared_store(_store(), shoppers, config.model_copy(update={"patience_sec": 60, "patience_sd": 0}),
                                           seed=1)
    assert report.crew_hours == (4 + 10 * 2) + 4
    assert [r.left_queue for r in results] == [False, True]   # nobody on duty on Tuesday afternoon
    assert {h.hour: h.crew_on_duty for h in report.hours} == {"13": 2}   # the most any day has


def test_the_last_shift_stays_until_the_last_shopper_has_paid():
    from store_emulator.domain.operations import CrewShift
    late = _shopper("late", "21:59:50", [("chips", 1)])   # pays at 22:00:15, after closing
    config = OperationsConfig(crew=1, crew_shifts=[CrewShift(start=8, end=22)], patience_sec=60, patience_sd=0, **_CREW)
    results, report = resolve_shared_store(_store(), [late], config, seed=1)
    assert not results[0].left_queue and results[0].total_spent == 300
    assert report.crew_hours == pytest.approx(14 + 16 / 3600, abs=0.01)


@pytest.mark.parametrize("bad", [{"start": 10, "end": 10}, {"start": 12, "end": 9}, {"start": 8, "end": 12, "days": [0]},
                                 {"start": 8, "end": 12, "days": [1, 1]}, {"start": 8, "end": 25}, {"start": 8, "end": 12, "staff": 0}])
def test_impossible_shifts_are_refused(bad):
    from store_emulator.domain.operations import CrewShift
    with pytest.raises(ValueError):
        CrewShift(**bad)


def test_shifts_need_a_crew():
    from store_emulator.domain.operations import CrewShift
    with pytest.raises(ValueError):
        OperationsConfig(crew_shifts=[CrewShift(start=8, end=12)])


def test_a_roster_covers_each_hours_need_with_workable_shifts():
    from store_emulator.domain.operations import RosterRules
    from store_emulator.engine.simulation.operations_plan import cover
    need = {hour: 2 if 12 <= hour < 16 else 1 for hour in range(8, 22)}
    shifts = cover(need, RosterRules(min_hours=4, max_hours=8))
    assert [(s.start, s.end, s.staff) for s in shifts] == [(8, 16, 1), (12, 20, 1), (18, 22, 1)]
    covered = {hour: sum(s.staff for s in shifts if s.start <= hour < s.end) for hour in need}
    assert all(covered[hour] >= need[hour] for hour in need)
    assert cover({}, RosterRules()) == []
    with pytest.raises(ValueError):
        RosterRules(min_hours=6, max_hours=4)


def test_a_plan_answers_with_a_roster_when_asked():
    from store_emulator.domain.operations import RosterRules
    from store_emulator.engine.simulation.operations_plan import plan_operations
    store = generate_store("urban_cvs")
    config = OperationsConfig(crew=2, stock_per_facing=2, patience_sec=120)
    shared, _ = _run(store, _crowd(80), config)
    costs = OperationsCosts(till_hour=1500, stock_unit_day=1)
    plan = plan_operations(store, shared.planned_customers, config, costs, seed=_SEED, roster=RosterRules(min_hours=4, max_hours=8))
    shifts = plan.config.crew_shifts
    assert shifts and all(4 <= s.end - s.start <= 8 for s in shifts)
    assert plan.best.labor_cost == round(plan.best.crew_hours * 1500)
    # Starting from that roster, the search keeps it a roster and never does worse.
    again = plan_operations(store, shared.planned_customers, plan.config, costs, seed=_SEED)
    assert again.config.crew_shifts and again.best.net >= again.current.net


@pytest.mark.parametrize("shelf_units", [1, 2, 5])
@pytest.mark.parametrize("backroom_units", [0, 1, 5])
@pytest.mark.parametrize("daily_delivery", [False, True])
@pytest.mark.parametrize("override_only", [False, True])
@pytest.mark.parametrize("restock", [None, 30])
@pytest.mark.parametrize("crew", [None, 1, 2, 4])
def test_finite_backrooms_never_sell_more_than_shelves_plus_received_stock(
    shelf_units, backroom_units, daily_delivery, override_only, restock, crew,
):
    store = _store()
    shoppers = [_shopper(f"d{day}-{hour}", f"{hour:02}:05:00", [("chips", shelf_units + 1)], day=Weekday(day))
                for day in range(1, 8) for hour in [10, 11, 12]]
    before = [shopper.model_dump() for shopper in shoppers]
    config = OperationsConfig(
        stock_per_facing=shelf_units, backroom_per_product=None if override_only else backroom_units,
        backroom_overrides={"chips": backroom_units} if override_only else {},
        daily_delivery=daily_delivery, restock_every_min=restock, substitute_share=0,
        crew=crew, refill_face_sec=1, refill_unit_sec=0,
        crowd_limit=None, checkout_base_sec=1, checkout_item_sec=0,
    )
    results, report = resolve_shared_store(store, shoppers, config, seed=1)
    sold = sum(event.quantity for result in results for event in result.timeline if event.action == Action.BUY)
    received = backroom_units * (7 if daily_delivery else 1)
    assert shelf_units <= sold <= shelf_units + received
    if not daily_delivery:
        assert sold == shelf_units + backroom_units
        assert report.deliveries == 0
    if backroom_units == 0:
        assert sold == shelf_units and report.deliveries == 0
    assert report.backroom_units == backroom_units * (1 if override_only else 3)
    if not daily_delivery or backroom_units == 0:
        assert report.refill_short_units > 0
    if crew is None and daily_delivery and restock is None and backroom_units >= shelf_units:
        assert report.refill_short_units == 0
    assert check_buy_consistency(store, results) == []
    assert [shopper.model_dump() for shopper in shoppers] == before


def test_two_shelves_draw_from_the_same_product_backroom():
    store = _store()
    store.racks.append(store.racks[0].model_copy(update={"id": "B", "position": (0, 2)}, deep=True))
    shoppers = [_shopper(str(index), arrival, [("chips", 1)])
                for index, arrival in enumerate(["10:00:00", "10:01:00", "10:31:00", "10:32:00", "11:01:00", "11:02:00"])]
    for index, shopper in enumerate(shoppers):
        if index % 2:
            shopper.timeline[1] = shopper.timeline[1].model_copy(update={"target_rack": "B", "y": 2})
    config = OperationsConfig(stock_per_facing=1, backroom_per_product=1, restock_every_min=30,
                              substitute_share=0, crowd_limit=None, checkout_base_sec=1, checkout_item_sec=0)
    results, report = resolve_shared_store(store, shoppers, config, seed=1)
    assert sum(result.total_spent for result in results) == 900
    assert report.backroom_units == 3
    assert next(stats for stats in report.backroom if stats.sku == "chips").refilled == 1
    assert check_buy_consistency(store, results) == []


@pytest.mark.parametrize("trigger", ["pick", "refill_complete"])
@pytest.mark.parametrize("refill_seconds", [30, 120])
@pytest.mark.parametrize("checkout_seconds", [1, 30])
def test_shoppers_at_the_till_are_served_before_a_same_time_refill(trigger, refill_seconds, checkout_seconds):
    first = _shopper("first", "10:00:00", [("chips", 1)])
    if trigger == "pick":
        second = _shopper("second", "10:00:15", [("chips", 2)])
        stock, point = 3, 0
    else:
        first.timeline[2].elapsed_sec = 10 + refill_seconds
        first.timeline[-1].elapsed_sec = 50 + refill_seconds
        second = _shopper("second", "10:00:15", [("nuts", 2)], pay=False)
        stock, point = 2, 0.5
    config = OperationsConfig(crew=1, stock_per_facing=stock, refill_at=point,
                              refill_face_sec=refill_seconds, refill_unit_sec=0,
                              checkout_base_sec=checkout_seconds, checkout_item_sec=0,
                              substitute_share=0, crowd_limit=None, patience_sec=1000, patience_sd=0)
    before = [shopper.model_dump() for shopper in [first, second]]
    results, report = resolve_shared_store(_store(), [first, second], config, seed=1)
    assert results[0].queue_wait_sec == 0
    assert report.face_refills >= 1
    assert check_buy_consistency(_store(), results) == []
    assert [shopper.model_dump() for shopper in [first, second]] == before


@pytest.mark.parametrize("crew", [1, 2, 100])
@pytest.mark.parametrize("time_budget", [0, 0.2])
def test_an_unstaffed_day_keeps_a_valid_default_crew_when_a_plan_is_saved(crew, time_budget):
    from store_emulator.engine.simulation.operations_plan import plan_operations, replay
    store = _store()
    config = OperationsConfig(crew=crew, crew_schedule={f"{hour:02d}": 0 for hour in range(24)},
                              patience_sec=10, patience_sd=0, **_CREW)
    shoppers = [_shopper("p", "10:00:00", [("chips", 1)])]
    before = config.model_dump()
    plan = plan_operations(store, shoppers, config, OperationsCosts(till_hour=100000),
                           seed=1, max_crew=1, time_budget_sec=time_budget)
    saved = OperationsConfig.model_validate(plan.config.model_dump())
    assert saved.crew is not None and saved.crew >= 1
    assert replay(store, shoppers, saved, OperationsCosts(till_hour=100000), seed=1)[0] == plan.best
    assert config.model_dump() == before


@pytest.mark.parametrize("crew", [None, 1, 2, 4])
@pytest.mark.parametrize("shelf_units, reserve", [(1, 0), (1, 1), (3, 1), (3, 3), (3, 6)])
@pytest.mark.parametrize("override_only", [False, True])
@pytest.mark.parametrize("arrival", ["10:00:40", "10:04:40"])
@pytest.mark.parametrize("later_day", [Weekday.MON, Weekday.TUE])
def test_returned_baskets_conserve_finite_stock_after_refill(crew, shelf_units, reserve, override_only, arrival, later_day):
    shoppers = [_shopper("blocking", "10:00:00", [("nuts", 1)]),
                _shopper("returns", arrival, [("chips", shelf_units)])]
    for index, at in enumerate(["10:15:00", "10:30:00", "10:45:00", "11:00:00", "11:15:00"]):
        shoppers.append(_shopper(f"later-{index}", at, [("chips", shelf_units)], day=later_day))
    config = OperationsConfig(
        stock_per_facing=shelf_units, backroom_per_product=None if override_only else reserve,
        backroom_overrides={"chips": reserve} if override_only else {}, daily_delivery=False,
        crew=crew, refill_face_sec=1, refill_unit_sec=0, restock_every_min=5,
        checkout_base_sec=600, checkout_item_sec=0, patience_sec=30, patience_sd=0,
        substitute_share=0, crowd_limit=None,
    )
    before = [shopper.model_dump() for shopper in shoppers]
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1)
    assert results[1].left_queue and results[1].total_spent == 0
    sold = sum(event.quantity for result in results for event in result.timeline
               if event.action == Action.BUY and event.product_sku == "chips")
    # Returning the basket must neither destroy units nor create extra stock, even after a partial/full refill.
    assert sold == shelf_units + reserve
    assert report.deliveries == 0
    assert check_buy_consistency(_store(), results) == []
    assert [shopper.model_dump() for shopper in shoppers] == before
    assert resolve_shared_store(_store(), shoppers, config, seed=1) == (results, report)


@pytest.mark.parametrize("crew", [2, 4])
def test_returned_stock_restarts_refills_on_other_faces_of_the_same_product(crew):
    store = _store()
    store.racks.append(store.racks[0].model_copy(update={"id": "B", "position": (0, 2)}, deep=True))
    shoppers = [_shopper("blocking", "10:00:00", [("nuts", 1)]),
                _shopper("returns", "10:04:40", [("chips", 1)]),
                _shopper("empties-B", "10:04:50", [("chips", 1)], pay=False),
                _shopper("after-return", "10:06:00", [("chips", 1)], pay=False)]
    for shopper in shoppers[2:]:
        shopper.timeline[1] = shopper.timeline[1].model_copy(update={"target_rack": "B", "y": 2})
    config = OperationsConfig(
        stock_per_facing=1, backroom_overrides={"chips": 1}, daily_delivery=False,
        crew=crew, refill_face_sec=1, refill_unit_sec=0, checkout_base_sec=600, checkout_item_sec=0,
        patience_sec=30, patience_sd=0, substitute_share=0, crowd_limit=None,
    )
    before = [shopper.model_dump() for shopper in shoppers]
    results, report = resolve_shared_store(store, shoppers, config, seed=1)
    assert results[1].left_queue and results[1].total_spent == 0
    assert results[2].total_spent == results[3].total_spent == 300
    # B's first attempt exhausted the shared backroom; A's returned basket makes B refillable immediately.
    assert any(task.kind == "refill" and task.rack_id == "B" and task.start == 10 * 3600 + 5 * 60 + 35
               for task in report.crew_tasks)
    assert check_buy_consistency(store, results) == []
    assert [shopper.model_dump() for shopper in shoppers] == before
