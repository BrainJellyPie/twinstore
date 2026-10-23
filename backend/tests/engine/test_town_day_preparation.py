"""Town runs prepare only simulated days and share demand across matching consecutive days."""

import pytest

from store_emulator.application import town as town_service
from store_emulator.application.scenarios import get_preset
from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import Scenario
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.town import TownSpec
from store_emulator.engine.town import generate_town


@pytest.mark.parametrize("only_days,expected_days,expected_calls", [
    ([], [1, 5, 7], 2), ([5], [5], 1), ([1, 7], [1, 7], 2), ([2], [], 0),
])
def test_only_requested_days_are_prepared_without_losing_other_days_age_examples(
    monkeypatch, only_days, expected_days, expected_calls,
):
    town = generate_town(TownSpec(size_m=200, seed=24102493))
    pool = [Persona(id=f"p{day}", day=day, identity="Visitor", age_group=age, gender="Female",
                    description="", intent="", purpose="snack") for day, age in [(1, "20s"), (5, "40s"), (7, "60s+")]]
    estimate, plan = town_service.estimate_demand, town_service.plan_arrivals
    calls, days = [], []

    def demand(*args, **kwargs):
        calls.append(1)
        return estimate(*args, **kwargs)

    def arrivals(people, *args, **kwargs):
        assert people == pool  # Other days still supply an age absent from the simulated day.
        days.append(int(kwargs["day"]))
        return plan(people, *args, **kwargs)

    monkeypatch.setattr(town_service, "estimate_demand", demand)
    monkeypatch.setattr(town_service, "plan_arrivals", arrivals)
    people, notes = town_service.town_visitors(town, pool, seed=9, scale=0.1,
        scenario=Scenario(only_days=only_days), store=None)
    assert days == expected_days
    assert len(calls) == expected_calls
    assert {int(p.day) for p in people} == set(expected_days)
    assert len(people) == len(notes)


@pytest.mark.parametrize("different_hours,scenario_id,expected_calls", [
    (False, None, 2), (True, None, 3), (False, "heatwave_weekend", 1), (True, "heatwave_weekend", 2),
])
def test_demand_reuse_respects_day_profile_and_each_layout_schedule(monkeypatch, different_hours, scenario_id, expected_calls):
    town = generate_town(TownSpec(size_m=200, seed=24102493))
    pool = [Persona(id=f"p{day}", day=day, identity="Visitor", age_group="20s", gender="Female",
                    description="", intent="", purpose="snack") for day in range(1, 8)]
    store = Store(id="s", name="Store", type="Convenience store", grid_size=(5, 5), weekly_schedule=[
        DaySchedule(day=day, open_hour=9 if different_hours and day >= 3 else 8, close_hour=20)
        for day in range(1, 8)
    ])
    estimate = town_service.estimate_demand
    calls = []

    def demand(*args, **kwargs):
        calls.append(1)
        return estimate(*args, **kwargs)

    monkeypatch.setattr(town_service, "estimate_demand", demand)
    people, _ = town_service.town_visitors(town, pool, seed=9, scale=0.1,
        scenario=get_preset(scenario_id) if scenario_id else None, store=store)
    assert len(calls) == expected_calls
    assert {int(p.day) for p in people} == set(range(1, 8))
    assert all(store.is_open_at(p.day, p.arrival_hour) for p in people)
