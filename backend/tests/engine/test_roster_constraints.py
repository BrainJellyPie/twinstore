"""Requested staffing constraints must survive planning and saving an existing roster."""

import pytest

from store_emulator.domain.operations import CrewShift, OperationsConfig, OperationsCosts, RosterRules
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine.simulation.operations_plan import cover, plan_operations, replay
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("length", [1, 2, 3, 9, 10, 14])
@pytest.mark.parametrize("days", [[], [1], [1, 3]])
@pytest.mark.parametrize("budget", [0, 0.5])
def test_new_shift_limits_apply_to_existing_rosters(length, days, budget):
    store = _store()
    config = OperationsConfig(crew=1, crew_shifts=[CrewShift(start=8, end=8 + length, days=days)])
    before = config.model_dump()
    shoppers = [_shopper("p", "08:05:00", [("chips", 1)])]
    costs = OperationsCosts(till_hour=1)
    plan = plan_operations(store, shoppers, config, costs, seed=1,
                           roster=RosterRules(min_hours=4, max_hours=8), time_budget_sec=budget)
    saved = OperationsConfig.model_validate(plan.config.model_dump())
    assert saved.crew_shifts
    assert all(4 <= shift.end - shift.start <= 8 for shift in saved.crew_shifts)
    assert {day for shift in saved.crew_shifts for day in (shift.days or range(1, 8))} == set(days or range(1, 8))
    assert config.model_dump() == before
    assert replay(store, shoppers, saved, costs, seed=1)[0] == plan.best


def test_rebuilding_a_roster_keeps_other_weekdays_and_their_opening_hours():
    store = _store()
    store.weekly_schedule[1] = DaySchedule(day=Weekday.TUE, open_hour=12, close_hour=22)
    config = OperationsConfig(crew=1, crew_shifts=[
        CrewShift(start=8, end=10, days=[1]), CrewShift(start=12, end=14, days=[2], staff=3),
    ])
    plan = plan_operations(store, [_shopper("p", "08:05:00", [("chips", 1)])], config,
                           OperationsCosts(till_hour=1), seed=1, roster=RosterRules(), time_budget_sec=0)
    assert plan.config.crew_on_duty(1, 8) == 1
    assert plan.config.crew_on_duty(2, 12) == 3
    assert plan.config.crew_on_duty(2, 8) == 0
    assert all(plan.config.crew_on_duty(3, hour) == 0 for hour in range(24))
    assert all(4 <= shift.end - shift.start <= 8 for shift in plan.config.crew_shifts)


def test_rebuilding_does_not_schedule_closed_or_unspecified_weekdays():
    store = _store()
    store.weekly_schedule = [DaySchedule(day=Weekday.MON, open_hour=8, close_hour=22),
                             DaySchedule(day=Weekday.TUE, is_open=False)]
    config = OperationsConfig(crew=1, crew_shifts=[CrewShift(start=8, end=10)])
    plan = plan_operations(store, [_shopper("p", "08:05:00", [("chips", 1)])], config,
                           OperationsCosts(), seed=1, roster=RosterRules(), time_budget_sec=0)
    assert {day for shift in plan.config.crew_shifts for day in shift.days} == {1}
    assert all(plan.config.crew_on_duty(day, hour) == 0 for day in range(2, 8) for hour in range(24))


def test_a_roster_with_no_staff_during_opening_does_not_restore_default_staff():
    store = _store()
    config = OperationsConfig(crew=2, crew_shifts=[CrewShift(start=0, end=1)], patience_sec=10, patience_sd=0)
    shoppers = [_shopper("p", "08:05:00", [("chips", 1)])]
    costs = OperationsCosts(till_hour=100000)
    plan = plan_operations(store, shoppers, config, costs, seed=1, roster=RosterRules(), time_budget_sec=0)
    assert all(plan.config.crew_on_duty(day, hour) == 0 for day in range(1, 8) for hour in range(8, 22))
    assert plan.best.crew_hours == 0
    assert replay(store, shoppers, OperationsConfig.model_validate(plan.config.model_dump()), costs, seed=1)[0] == plan.best


def test_overlapping_large_crews_stay_within_the_per_shift_staff_limit():
    config = OperationsConfig(crew=1, crew_shifts=[CrewShift(start=8, end=10, staff=100) for _ in range(2)])
    plan = plan_operations(_store(), [_shopper("p", "08:05:00", [("chips", 1)])], config,
                           OperationsCosts(), seed=1, roster=RosterRules(), time_budget_sec=0)
    saved = OperationsConfig.model_validate(plan.config.model_dump())
    assert saved.crew_on_duty(1, 8) == 200
    assert all(shift.staff <= 100 and 4 <= shift.end - shift.start <= 8 for shift in saved.crew_shifts)


def test_a_plan_that_needs_too_many_shifts_is_not_returned_as_unsavable_config():
    config = OperationsConfig(crew=1, crew_shifts=[
        CrewShift(start=8, end=22, staff=day, days=[day]) for day in range(1, 8)
    ])
    with pytest.raises(ValueError, match="at most 60"):
        plan_operations(_store(), [_shopper("p", "08:05:00", [("chips", 1)])], config,
                        OperationsCosts(), seed=1, roster=RosterRules(min_hours=1, max_hours=1), time_budget_sec=0)


@pytest.mark.parametrize("start, length", [(0, 1), (10, 1), (22, 2), (8, 3)])
@pytest.mark.parametrize("staff", [1, 100])
def test_short_operating_windows_cannot_silently_shorten_requested_shifts(start, length, staff):
    need = {hour: staff for hour in range(start, start + length)}
    with pytest.raises(ValueError, match="shortest shift.*exceeds the operating window"):
        cover(need, RosterRules(min_hours=4, max_hours=8))
    # Zero staffing does not need any shift; an exact-length window is feasible.
    assert cover(dict.fromkeys(need, 0), RosterRules()) == []
    shifts = cover(need, RosterRules(min_hours=length, max_hours=length))
    assert all(shift.end - shift.start == length for shift in shifts)
    assert all(sum(shift.staff for shift in shifts if shift.start <= hour < shift.end) >= staff for hour in need)
