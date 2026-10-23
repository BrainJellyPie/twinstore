"""Customers leaving do not close the store or remove its scheduled fixed costs."""

import pytest

from store_emulator.domain.operations import CrewShift, MemoryConfig, OperationsConfig, OperationsCosts
from store_emulator.domain.types import Weekday
from store_emulator.engine.simulation.customer_memory import simulate_weeks
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("staffing, hours", [("tills", 13), ("crew", 26), ("roster", 16)])
@pytest.mark.parametrize("days", [(Weekday.MON,), (Weekday.MON, Weekday.WED)])
@pytest.mark.parametrize("labor, holding", [(1000, 0), (0, 1), (1000, 1)])
@pytest.mark.parametrize("reserve", [None, 0, 4])
def test_empty_future_weeks_keep_the_original_operating_days_and_costs(staffing, hours, days, labor, holding, reserve):
    store = _store(counters=2)
    shoppers = [_shopper(f"day-{int(day)}", "09:05:00", [("chips", 1)], day=day) for day in days]
    config = OperationsConfig(
        stock_per_facing=2, backroom_per_product=reserve, daily_delivery=False, restock_every_min=None,
        open_counters=1, till_schedule={"10": 0}, checkout_base_sec=1, checkout_item_sec=0,
        crew=None if staffing == "tills" else 2, crew_schedule={} if staffing == "tills" else {"10": 0},
        crew_shifts=[CrewShift(start=8, end=16, staff=2)] if staffing == "roster" else [],
    )
    memory = MemoryConfig(weeks=3, weekly_churn=1, leave_per_missing_unit=0,
                          leave_after_line=0, leave_per_wait_minute=0)
    costs = OperationsCosts(till_hour=labor, stock_unit_day=holding)
    before = [shopper.model_dump() for shopper in shoppers]
    report = simulate_weeks(store, shoppers, config, memory, costs, seed=1)
    fixed = len(days) * (hours * labor + (6 + 3 * (reserve or 0)) * holding)
    assert report.weeks[0].net == report.weeks[0].revenue - fixed
    for week in report.weeks[1:]:
        assert week.shoppers == week.ideal_shoppers == week.revenue == 0
        assert week.net == -fixed
    assert report.net == report.revenue - 3 * fixed
    assert [shopper.model_dump() for shopper in shoppers] == before


@pytest.mark.parametrize("roster, hours", [(False, 42), (True, 44)])
def test_a_weekday_losing_its_only_customer_keeps_that_days_staff_and_stock_cost(roster, hours):
    store = _store()
    shoppers = [_shopper("keeper", "09:05:00", [("chips", 1)], day=Weekday.MON),
                _shopper("leaver", "09:05:00", [("caviar", 1)], day=Weekday.TUE),
                _shopper("keeper", "10:05:00", [("nuts", 1)], day=Weekday.WED)]
    config = OperationsConfig(stock_per_facing=2, stock_overrides={"caviar": 0}, substitute_share=0,
                              checkout_base_sec=1, checkout_item_sec=0, restock_every_min=None,
                              crew=1 if roster else None, crew_shifts=[
                                  CrewShift(start=8, end=12, days=[1], staff=2),
                                  CrewShift(start=8, end=16, days=[2], staff=3),
                                  CrewShift(start=10, end=22, days=[3]),
                              ] if roster else [])
    report = simulate_weeks(store, shoppers, config,
                            MemoryConfig(weeks=3, leave_per_missing_unit=1, weekly_churn=0,
                                         leave_after_line=0, leave_per_wait_minute=0),
                            OperationsCosts(till_hour=1000, stock_unit_day=2), seed=1)
    assert [week.shoppers for week in report.weeks] == [2, 1, 1]
    assert [week.revenue for week in report.weeks] == [650, 650, 650]
    assert [week.net for week in report.weeks] == [650 - hours * 1000 - 4 * 3 * 2] * 3


@pytest.mark.parametrize("crew", [None, 1, 2])
def test_legacy_stores_keep_the_original_observed_hours_after_customer_loss(crew):
    store = _store()
    store.weekly_schedule = []
    shoppers = [_shopper("p", "10:05:00", [("chips", 1)])]
    report = simulate_weeks(store, shoppers, OperationsConfig(crew=crew, checkout_base_sec=1, checkout_item_sec=0),
                            MemoryConfig(weeks=3, weekly_churn=1), OperationsCosts(till_hour=1000), seed=1)
    assert report.weeks[0].net < report.weeks[0].revenue
    for week in report.weeks[1:]:
        assert week.shoppers == week.revenue == 0
        assert week.net == report.weeks[0].net - report.weeks[0].revenue


@pytest.mark.parametrize("delivery, sold", [(False, 2), (True, 3)])
def test_empty_calendar_days_still_refill_shelves_and_receive_deliveries(delivery, sold):
    from store_emulator.engine.simulation.shared_store import resolve_shared_store
    shoppers = [_shopper("mon", "10:00:00", [("chips", 1)], day=Weekday.MON),
                _shopper("wed-first", "10:00:00", [("chips", 1)], day=Weekday.WED),
                _shopper("wed-last", "10:06:00", [("chips", 1)], day=Weekday.WED)]
    calendar = [*shoppers, _shopper("tue-gone", "10:00:00", [("caviar", 1)], day=Weekday.TUE)]
    before = [shopper.model_dump() for shopper in calendar]
    config = OperationsConfig(stock_per_facing=1, backroom_overrides={"chips": 1},
                              daily_delivery=delivery, restock_every_min=5, substitute_share=0,
                              checkout_base_sec=1, checkout_item_sec=0, crowd_limit=None)
    results, report = resolve_shared_store(_store(), shoppers, config, seed=1, calendar=calendar)
    assert len(results) == len(shoppers) == 3
    assert report.queued == sold
    assert report.days == 3 and report.deliveries == int(delivery)
    assert sum(result.total_spent for result in results) == sold * 300
    assert [shopper.model_dump() for shopper in calendar] == before


def test_a_lost_visit_does_not_cancel_that_days_delivery_cycle_in_later_weeks():
    shoppers = [_shopper("mon", "10:00:00", [("chips", 1)], day=Weekday.MON),
                _shopper("tue-gone", "10:00:00", [("caviar", 1)], day=Weekday.TUE),
                _shopper("wed-first", "10:00:00", [("chips", 1)], day=Weekday.WED),
                _shopper("wed-last", "10:06:00", [("chips", 1)], day=Weekday.WED)]
    config = OperationsConfig(stock_per_facing=1, stock_overrides={"caviar": 0}, backroom_overrides={"chips": 1},
                              daily_delivery=True, restock_every_min=5, substitute_share=0,
                              checkout_base_sec=1, checkout_item_sec=0, crowd_limit=None)
    report = simulate_weeks(_store(), shoppers, config,
                            MemoryConfig(weeks=3, leave_per_missing_unit=1, weekly_churn=0,
                                         leave_after_line=0, leave_per_wait_minute=0), OperationsCosts(), seed=1)
    assert [week.shoppers for week in report.weeks] == [4, 3, 3]
    assert [week.revenue for week in report.weeks] == [900, 900, 900]
