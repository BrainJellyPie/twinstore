"""A run's neighborhood visitors follow its layout and scenario: the hours the store opens each day, the effect sizes
of the store's format and the scenario's day type; a scenario that changes some hours keeps every other visitor
paired with the baseline."""

import pytest

from store_emulator.application import town as town_service
from store_emulator.application.scenarios import get_preset
from store_emulator.domain.persona import AGE_GROUPS, Persona
from store_emulator.domain.scenario import DayType
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.town import Town, TownArchetype, TownDemand, TownSpec
from store_emulator.domain.types import Weekday
from store_emulator.engine.scenario import compile_scenario, priors_for
from store_emulator.engine.town import estimate_demand, generate_town


@pytest.fixture(scope="module")
def town() -> Town:
    return generate_town(TownSpec(archetype=TownArchetype.RESIDENTIAL, seed=3, size_m=400))


def _pool() -> list[Persona]:
    return [
        Persona(id=f"d{day}-{age.rstrip('+')}-{hour}", day=Weekday(day), identity="local", age_group=age,
                gender="Female", description="", intent="", purpose="snack", arrival_hour=hour)
        for day in range(1, 8) for age in AGE_GROUPS for hour in (8, 13, 20)
    ]


def _store(store_type: str = "Convenience store", schedule: list[DaySchedule] | None = None) -> Store:
    return Store(id="s", name="Corner", type=store_type, grid_size=(10, 10), weekly_schedule=schedule or [])


def test_visitors_come_in_the_hours_the_layout_opens_each_day(town: Town):
    store = _store(schedule=[
        DaySchedule(day=Weekday.MON, open_hour=0, close_hour=24),
        DaySchedule(day=Weekday.TUE, open_hour=8, close_hour=20),
        DaySchedule(day=Weekday.SUN, is_open=False),
    ])
    visitors, _ = town_service.town_visitors(town, _pool(), seed=1, scale=0.5, scenario=None, store=store)
    hours = {day: {p.arrival_hour for p in visitors if p.day == day} for day in Weekday}
    assert min(hours[Weekday.MON]) < 7  # a 24-hour day has night visitors
    assert hours[Weekday.TUE] and hours[Weekday.TUE] <= set(range(8, 20))
    assert not hours[Weekday.SUN] and not hours[Weekday.WED]  # closed, or not on the schedule
    legacy, _ = town_service.town_visitors(town, _pool(), seed=1, scale=0.5, scenario=None, store=_store())
    assert {p.arrival_hour for p in legacy} <= set(range(7, 24)) and {p.day for p in legacy} == set(Weekday)


@pytest.mark.parametrize("scenario_id, day_types", [
    (None, ["weekday"] * 5 + ["weekend"] * 2),
    ("rainy_commute", ["weekday"] * 5 + ["weekend"] * 2),
    ("heatwave_weekend", ["weekend"] * 7),
    ("holiday_season", ["holiday"] * 7),
])
@pytest.mark.parametrize("store_type", ["Convenience store", "supermarket"])
def test_visitors_follow_the_scenarios_day_type_and_the_store_formats_effect_sizes(
    town: Town, monkeypatch: pytest.MonkeyPatch, scenario_id: str | None, day_types: list[str], store_type: str,
):
    calls: list[tuple[object, object]] = []

    def recording(demand_town: Town, **kwargs: object) -> TownDemand:
        calls.append((kwargs["day_type"], kwargs["traffic_multiplier"]))
        return estimate_demand(demand_town, **kwargs)  # type: ignore[arg-type]  # forwards the call's own arguments

    monkeypatch.setattr(town_service, "estimate_demand", recording)
    scenario = get_preset(scenario_id) if scenario_id else None
    town_service.town_visitors(town, _pool(), seed=1, scale=0.05, scenario=scenario, store=_store(store_type))
    assert [day_type for day_type, _ in calls] == list(dict.fromkeys(day_types))
    # A weekend or holiday scenario runs on the neighborhood's own weekend/holiday profile, so its day-type effect
    # is not applied on top; the rest of the scenario (heat, rain…) is, at the store format's effect sizes.
    profiled = scenario is not None and day_types[0] in ("weekend", "holiday") and scenario_id != "rainy_commute"
    effective = scenario.model_copy(update={"day_type": DayType.WEEKDAY}) if profiled and scenario else scenario
    traffic = compile_scenario(effective, priors_for(store_type)).base_traffic if effective is not None else 1.0
    assert all(multiplier == traffic for _, multiplier in calls)


def test_a_scenario_that_changes_some_hours_keeps_every_other_visitor_paired(town: Town):
    store = _store(schedule=[DaySchedule(day=Weekday(day), open_hour=7, close_hour=23) for day in range(1, 8)])
    base, _ = town_service.town_visitors(town, _pool(), seed=1, scale=0.2, scenario=None, store=store)
    rush, _ = town_service.town_visitors(town, _pool(), seed=1, scale=0.2, scenario=get_preset("lunch_rush"),
                                         store=store)

    def outside_lunch(people: list[Persona]) -> set[str]:
        return {p.id for p in people if not 11 <= p.arrival_hour <= 13}

    assert len(rush) > len(base) and outside_lunch(rush) == outside_lunch(base)
    assert {p.id for p in base} <= {p.id for p in rush}  # the busier lunch rows keep their first visitors
