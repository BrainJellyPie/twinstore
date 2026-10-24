"""An existing profitable plan must not bypass requested staffing ceilings."""

import pytest

from store_emulator.domain.operations import CrewShift, MemoryConfig, OperationsConfig, OperationsCosts, RosterRules
from store_emulator.engine.simulation.operations_plan import plan_operations, replay
from store_emulator.engine.simulation.customer_memory import simulate_weeks
from tests.engine.test_shared_store import _shopper, _store


def initial(kind):
    settings = dict(stock_per_facing=10, patience_sec=10, patience_sd=0,
                    checkout_base_sec=60, checkout_item_sec=0, restock_every_min=None,
                    substitute_share=0, crowd_limit=None)
    if kind == "tills":
        return OperationsConfig(open_counters=3, till_schedule={"09": 0, "10": 3, "23": 4}, **settings)
    if kind == "all_tills":
        return OperationsConfig(open_counters=None, **settings)
    if kind == "crew":
        return OperationsConfig(crew=3, crew_schedule={"09": 0, "10": 4, "23": 5}, **settings)
    return OperationsConfig(crew=3, crew_shifts=[
        CrewShift(start=8, end=12, staff=2), CrewShift(start=10, end=18, staff=2, days=[1, 2]),
        CrewShift(start=12, end=20, staff=3, days=[3]),
    ], **settings)


@pytest.mark.parametrize("kind", ["tills", "all_tills", "crew", "roster"])
@pytest.mark.parametrize("limit", [1, 2])
@pytest.mark.parametrize("budget", [0, 0.05])
def test_requested_ceiling_holds_even_when_the_old_plan_earns_more(kind, limit, budget):
    store = _store(counters=3)
    shoppers = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(6)]
    current = initial(kind)
    before = current.model_dump()
    costs = OperationsCosts()
    current_outcome = replay(store, shoppers, current, costs, seed=1)[0]
    plan = plan_operations(store, shoppers, current, costs, seed=1, max_tills=limit, max_crew=limit,
                           time_budget_sec=budget)
    saved = OperationsConfig.model_validate(plan.config.model_dump())
    if saved.crew is None:
        assert saved.open_counters is not None and saved.open_counters <= limit
        assert all(n <= limit for n in saved.till_schedule.values())
        if kind == "tills":
            assert saved.till_schedule["09"] == 0
    else:
        assert saved.crew <= limit
        assert all(n <= limit for n in saved.crew_schedule.values())
        assert all(saved.crew_on_duty(day, hour) <= limit for day in range(1, 8) for hour in range(24))
        if kind == "crew":
            assert saved.crew_schedule["09"] == 0
    assert plan.current == current_outcome
    assert plan.current_config.model_dump() == before == current.model_dump()
    assert replay(store, shoppers, saved, costs, seed=1)[0] == plan.best


def test_roster_rebuild_obeys_both_shift_lengths_and_overlapping_staff_limit():
    store = _store(counters=3)
    current = initial("roster")
    current.crew_shifts[0].end = 10
    plan = plan_operations(store, [_shopper("p", "10:00:00", [("chips", 1)])], current, OperationsCosts(),
                           seed=1, max_crew=1, roster=RosterRules(min_hours=4, max_hours=6), time_budget_sec=0)
    assert plan.config.crew_shifts
    assert all(4 <= shift.end - shift.start <= 6 for shift in plan.config.crew_shifts)
    assert all(plan.config.crew_on_duty(day, hour) <= 1 for day in range(1, 8) for hour in range(24))


def test_uncapped_roster_keeps_existing_simultaneous_staff():
    store = _store(counters=3)
    current = initial("roster")
    plan = plan_operations(store, [_shopper("p", "10:00:00", [("chips", 1)])], current, OperationsCosts(),
                           seed=1, time_budget_sec=0)
    assert plan.config == current
    assert plan.config.crew_on_duty(1, 10) == 4


@pytest.mark.parametrize("kind", ["tills", "crew", "roster"])
def test_retention_projection_uses_the_same_bounded_config_as_the_returned_plan(kind):
    store = _store(counters=3)
    shoppers = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(6)]
    memory = MemoryConfig(weeks=2)
    costs = OperationsCosts(till_hour=100)
    plan = plan_operations(store, shoppers, initial(kind), costs, seed=1, max_tills=1, max_crew=1,
                           time_budget_sec=0, memory=memory)
    assert plan.best_weeks == simulate_weeks(store, shoppers, plan.config, memory, costs, seed=1)
    assert plan.current_weeks == simulate_weeks(store, shoppers, plan.current_config, memory, costs, seed=1)


def test_till_limit_does_not_add_checkout_capacity_to_a_store_without_counters():
    store = _store(counters=0)
    shoppers = [_shopper("p", "10:00:00", [("chips", 1)])]
    plan = plan_operations(store, shoppers, OperationsConfig(), OperationsCosts(), seed=1,
                           max_tills=1, time_budget_sec=0)
    assert plan.config.open_counters is None
    assert plan.best.till_hours == 0
