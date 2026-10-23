"""Work already underway stays paid when an hourly shift ends."""

import pytest

from store_emulator.domain.operations import CrewShift, OperationsConfig, OperationsCosts
from store_emulator.engine.simulation.operations_plan import replay
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("mode", ["tills", "crew", "roster"])
@pytest.mark.parametrize("staff", [1, 2, 3])
@pytest.mark.parametrize("service", [0, 5, 6, 60, 600])
@pytest.mark.parametrize("customers", [1, 2])
def test_checkouts_spanning_a_shift_end_keep_their_actual_workers_paid(mode, staff, service, customers):
    store = _store(counters=staff)
    for day in store.weekly_schedule:
        day.open_hour, day.close_hour = 8, 10
    config = OperationsConfig(stock_per_facing=20, restock_every_min=None, refill_at=0,
                              checkout_base_sec=service, checkout_item_sec=0, patience_sd=0)
    if mode == "tills":
        config.till_schedule = {"09": 0}
    else:
        config.crew = staff
        if mode == "crew":
            config.crew_schedule = {"09": 0}
        else:
            config.crew_shifts = [CrewShift(start=8, end=9, staff=staff)]
    shoppers = [_shopper(f"p{i}", "08:59:30", [("chips", 1)]) for i in range(customers)]
    before = [shopper.model_dump() for shopper in shoppers]
    money, report, played = replay(store, shoppers, config, OperationsCosts(till_hour=3600), seed=1)
    # Each till starts at 08:59:55. A second shopper uses another till, or follows
    # immediately only if the first checkout leaves time before the shift ends.
    served = min(staff, customers)
    if staff == 1 and customers == 2 and service < 5:
        served = 2
    extra = max(0, service - 5) * min(staff, customers)
    expected = round(staff + extra / 3600, 2)
    assert report.till_hours == expected
    assert report.crew_hours == (expected if mode != "tills" else 0)
    assert money.labor_cost == round(expected * 3600)
    assert sum(not shopper.left_queue for shopper in played) == served
    assert report.counter_utilization == round(served * service / (staff * 3600 + extra), 4)
    assert [shopper.model_dump() for shopper in shoppers] == before


@pytest.mark.parametrize("mode", ["crew", "roster"])
@pytest.mark.parametrize("staff", [1, 2, 3])
@pytest.mark.parametrize("duration", [0, 5, 6, 600, 1800])
def test_refilling_across_a_shift_end_keeps_only_the_working_member_paid(mode, staff, duration):
    store = _store()
    for day in store.weekly_schedule:
        day.open_hour, day.close_hour = 8, 10
    config = OperationsConfig(crew=staff, stock_per_facing=2, refill_at=0.5,
                              refill_face_sec=duration, refill_unit_sec=0,
                              crew_schedule={"09": 0} if mode == "crew" else {},
                              crew_shifts=[CrewShift(start=8, end=9, staff=staff)] if mode == "roster" else [])
    shopper = _shopper("p", "08:59:45", [("chips", 1)], pay=False)
    money, report, _ = replay(store, [shopper], config, OperationsCosts(till_hour=3600), seed=1)
    extra = max(0, duration - 5)
    assert report.face_refills == 1
    assert report.crew_hours == round(staff + extra / 3600, 2)
    # With multiple staff, the last member refills and the cashier finishes on time.
    assert report.till_hours == round(1 + (extra / 3600 if staff == 1 else 0), 2)
    assert money.labor_cost == round(report.crew_hours * 3600)


@pytest.mark.parametrize("mode", ["tills", "crew", "roster"])
@pytest.mark.parametrize("remaining", [0, 1, 2, 3])
@pytest.mark.parametrize("customers", [1, 2, 3])
def test_a_smaller_next_shift_only_adds_overtime_for_workers_no_longer_scheduled(mode, remaining, customers):
    store = _store(counters=3)
    for day in store.weekly_schedule:
        day.open_hour, day.close_hour = 8, 10
    config = OperationsConfig(stock_per_facing=20, restock_every_min=None, refill_at=0,
                              checkout_base_sec=600, checkout_item_sec=0)
    if mode == "tills":
        config.till_schedule = {"09": remaining}
    else:
        config.crew = 3
        if mode == "crew":
            config.crew_schedule = {"09": remaining}
        else:
            config.crew_shifts = [CrewShift(start=8, end=9, staff=3)]
            if remaining:
                config.crew_shifts.append(CrewShift(start=9, end=10, staff=remaining))
    shoppers = [_shopper(f"p{i}", "08:59:30", [("chips", 1)]) for i in range(customers)]
    money, report, _ = replay(store, shoppers, config, OperationsCosts(till_hour=3600), seed=1)
    extra = max(0, customers - remaining) * 595
    expected = round(3 + remaining + extra / 3600, 2)
    assert report.till_hours == expected
    assert report.crew_hours == (expected if mode != "tills" else 0)
    assert money.labor_cost == round(expected * 3600)
    assert report.abandoned == 0


@pytest.mark.parametrize("mode", ["tills", "crew", "roster"])
def test_a_long_checkout_spanning_an_unstaffed_hour_does_not_double_pay_the_next_shift(mode):
    store = _store()
    for day in store.weekly_schedule:
        day.open_hour, day.close_hour = 8, 11
    config = OperationsConfig(stock_per_facing=100, restock_every_min=None, refill_at=0,
                              checkout_base_sec=600, checkout_item_sec=60)
    if mode == "tills":
        config.till_schedule = {"09": 0}
    else:
        config.crew = 1
        if mode == "crew":
            config.crew_schedule = {"09": 0}
        else:
            config.crew_shifts = [CrewShift(start=8, end=9), CrewShift(start=10, end=11)]
    shopper = _shopper("p", "08:59:30", [("chips", 80)])
    money, report, played = replay(store, [shopper], config, OperationsCosts(till_hour=3600), seed=1)
    assert played[0].leave_time == "10:30:05"
    assert report.till_hours == 3
    assert report.crew_hours == (3 if mode != "tills" else 0)
    assert report.counter_utilization == 0.5
    assert money.labor_cost == 10800
