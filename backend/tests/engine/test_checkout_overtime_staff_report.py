"""Hourly capacity must include the last shift that actually serves after closing."""

import pytest

from store_emulator.domain.operations import CrewShift, OperationsConfig, OperationsReport
from store_emulator.domain.types import Weekday
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("day", list(Weekday))
@pytest.mark.parametrize("closing", [22, 24])
@pytest.mark.parametrize("staff,tills", [(1, 1), (3, 2)])
def test_overtime_capacity_uses_the_retained_shift(day, closing, staff, tills):
    store = _store(counters=tills)
    for schedule in store.weekly_schedule:
        schedule.open_hour, schedule.close_hour = closing - 1, closing
    config = OperationsConfig(crew=1, crew_shifts=[CrewShift(start=closing - 1, end=closing, staff=staff)],
        checkout_base_sec=1, checkout_item_sec=0, patience_sec=60, patience_sd=0, refill_at=0)
    shoppers = [_shopper("before", f"{closing - 1:02d}:58:00", [("chips", 1)], day=day),
                _shopper("after", f"{closing - 1:02d}:59:50", [("chips", 1)], day=day)]
    before = [shopper.model_dump() for shopper in shoppers]
    customers, report = resolve_shared_store(store, shoppers, config, seed=1)
    assert [customer.total_spent for customer in customers] == [300, 300]
    assert not any(customer.left_queue for customer in customers)
    hours = {hour.hour: hour for hour in OperationsReport.model_validate_json(report.model_dump_json()).hours}
    assert set(hours) == {f"{closing - 1:02d}", f"{closing % 24:02d}"}
    for hour in hours.values():
        assert hour.counters_open == min(staff, tills)
        assert hour.crew_on_duty == staff
        assert hour.arrivals == 1
    assert [shopper.model_dump() for shopper in shoppers] == before


def test_a_last_shift_with_nobody_on_duty_still_reports_zero_and_abandonment():
    store = _store()
    config = OperationsConfig(crew=1, crew_shifts=[CrewShift(start=8, end=21)],
        checkout_base_sec=1, checkout_item_sec=0, patience_sec=60, patience_sd=0, refill_at=0)
    customers, report = resolve_shared_store(store, [_shopper("late", "21:59:50", [("chips", 1)])], config, seed=1)
    assert customers[0].left_queue and customers[0].total_spent == 0
    assert report.hours[0].counters_open == report.hours[0].crew_on_duty == 0


def test_hourly_capacity_keeps_its_maximum_over_the_simulated_weekdays():
    store = _store(counters=4)
    config = OperationsConfig(crew=1, crew_shifts=[CrewShift(start=8, end=22, days=[1], staff=1),
        CrewShift(start=8, end=10, days=[2], staff=4), CrewShift(start=10, end=22, days=[2], staff=2)],
        checkout_base_sec=1, checkout_item_sec=0, patience_sec=60, patience_sd=0, refill_at=0)
    shoppers = [_shopper("mon", "09:00:00", [("chips", 1)], day=Weekday.MON),
                _shopper("tue", "11:00:00", [("chips", 1)], day=Weekday.TUE)]
    _, report = resolve_shared_store(store, shoppers, config, seed=1)
    assert {hour.hour: (hour.counters_open, hour.crew_on_duty) for hour in report.hours} == {"09": (4, 4), "11": (2, 2)}
