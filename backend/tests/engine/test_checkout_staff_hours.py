"""Staffed till time includes the checkouts that finish after the store closes."""

import pytest

from store_emulator.domain.operations import OperationsConfig, OperationsCosts
from store_emulator.domain.types import Action
from store_emulator.engine.simulation.operations_plan import replay
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("scheduled", [False, True])
@pytest.mark.parametrize("counters", [1, 2, 3])
@pytest.mark.parametrize("service", [0, 1, 30, 600])
@pytest.mark.parametrize("customers", [1, 2, 10])
def test_checkouts_finishing_late_count_in_staff_time_and_cost(scheduled, counters, service, customers):
    store = _store(counters=counters)
    for schedule in store.weekly_schedule:
        schedule.open_hour, schedule.close_hour = 21, 22
    if not scheduled:
        store.weekly_schedule = []
    shoppers = [_shopper(f"p{index}", "21:59:30", [("chips", 1)]) for index in range(customers)]
    config = OperationsConfig(stock_per_facing=20, restock_every_min=None, substitute_share=0,
                              checkout_base_sec=service, checkout_item_sec=0, patience_sec=7200,
                              patience_sd=0, crowd_limit=None, refill_at=0)
    before = [shopper.model_dump() for shopper in shoppers]
    costs = OperationsCosts(till_hour=1000)
    result, report, played = replay(store, shoppers, config, costs, seed=1)
    arrival = 21 * 3600 + 59 * 60 + 30
    finish = max(arrival + event.elapsed_sec + event.duration for shopper in played
                 for event in shopper.timeline if event.action == Action.PAY)
    opening = 21 * 3600
    closing = 22 * 3600 if scheduled else arrival + max(shopper.duration_sec for shopper in shoppers)
    paid_seconds = counters * (max(closing, finish) - opening)
    assert report.abandoned == 0
    assert report.till_hours == round(paid_seconds / 3600, 2)
    assert result.labor_cost == round(report.till_hours * costs.till_hour)
    assert report.counter_utilization == round(customers * service / paid_seconds, 4)
    # The same cashiers with no shelf work need the same time in crew mode.
    crew_result, crew_report, crew_played = replay(store, shoppers, config.model_copy(update={"crew": counters}), costs, seed=1)
    assert crew_report.till_hours == report.till_hours
    assert crew_result.labor_cost == result.labor_cost
    assert [shopper.leave_time for shopper in crew_played] == [shopper.leave_time for shopper in played]
    assert [shopper.model_dump() for shopper in shoppers] == before


@pytest.mark.parametrize("counters", [0, 1])
def test_zero_service_is_distinct_from_a_store_without_tills(counters):
    shopper = _shopper("p", "10:00:00", [("chips", 1)])
    before = shopper.model_dump()
    config = OperationsConfig(checkout_base_sec=0, checkout_item_sec=0)
    _, report, played = replay(_store(counters=counters), [shopper], config, OperationsCosts(), seed=1)
    pay = next(event for event in played[0].timeline if event.action == Action.PAY)
    assert pay.duration == (0 if counters else 20)
    assert played[0].duration_sec == shopper.duration_sec - (20 if counters else 0)
    assert report.counter_utilization == 0
    assert report.queued == counters
    assert shopper.model_dump() == before
