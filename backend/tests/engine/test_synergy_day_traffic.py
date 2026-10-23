"""The area model and its basket study must apply day-type traffic exactly once."""

import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import DayType, EventKind, LocalEvent, Scenario, ScenarioPriors, Weather
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.town import Building, BuildingKind, Town, TownArchetype, Venue, VenueCategory
from store_emulator.domain.types import Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.scenario import compile_scenario, priors_for
from store_emulator.engine.town import estimate_demand
from store_emulator.engine.town import vlm_synergy
from tests.engine.test_reproducibility import _RecordingEngine


@pytest.fixture
def town():
    return Town(id="town", name="Town", archetype=TownArchetype.RESIDENTIAL, size_m=200, focal_venue_id="store",
                buildings=[Building(id="homes", kind=BuildingKind.APARTMENT, x=90, y=100, residents=5000)],
                venues=[Venue(id="store", name="Store", category=VenueCategory.CONVENIENCE, x=100, y=100),
                        Venue(id="cafe", name="Cafe", category=VenueCategory.CAFE, x=110, y=100)])


def _store(kind):
    return Store(id="store", name="Store", type=kind, grid_size=(3, 3),
                 weekly_schedule=[DaySchedule(day=d, open_hour=8, close_hour=10) for d in Weekday])


def _scenario(day):
    return Scenario(day_type=day, weather=Weather.RAIN, traffic_multiplier=1.4, budget_multiplier=1.2,
                    hourly_traffic={8: 0.5, 9: 1.7},
                    events=[LocalEvent(kind=EventKind.FESTIVAL, start_hour=9, end_hour=10, intensity=0.6)])


@pytest.mark.parametrize("profile", ["weekday", "weekend", "holiday"])
@pytest.mark.parametrize("day", list(DayType))
@pytest.mark.parametrize("kind", ["Convenience store", "supermarket"])
@pytest.mark.parametrize("calibrated", [False, True])
def test_synergy_demand_matches_the_selected_day_profile(town, monkeypatch, profile, day, kind, calibrated):
    scenario = _scenario(day)
    custom = ScenarioPriors(day_traffic={"weekday": 1, "weekend": 1.8, "public_holiday": 0.4,
                                       "holiday_season": 2.1, "school_vacation": 0.6}) if calibrated else None
    config = SimulationConfig(seed=5, scenario=scenario, scenario_priors=custom)
    recorded = []

    class CapturedDemand(Exception):
        pass

    def capture(_pool, demand, _town, **_kwargs):
        recorded.append(demand)
        raise CapturedDemand

    monkeypatch.setattr(vlm_synergy, "plan_arrivals", capture)
    with pytest.raises(CapturedDemand):
        asyncio.run(vlm_synergy.vlm_basket_synergy(
            town, "cafe", _store(kind), [], config=config, engine=_RecordingEngine(),
            pathfinder=AStarPathFinder(), cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS,
            customers=4, day_type=profile,
        ))
    profiled = ((profile == "weekend" and day == DayType.WEEKEND)
                or (profile == "holiday" and day in (DayType.PUBLIC_HOLIDAY, DayType.HOLIDAY_SEASON)))
    effective = scenario.model_copy(update={"day_type": DayType.WEEKDAY}) if profiled else scenario
    effects = compile_scenario(effective, priors_for(kind, custom))
    expected = estimate_demand(town, day_type=profile, hours=[8, 9], traffic_multiplier=effects.base_traffic,
                               hourly_multiplier=effects.traffic_by_hour)
    assert recorded[0].total_daily_visitors == expected.total_daily_visitors
    assert recorded[0].hourly_totals == expected.hourly_totals


@pytest.mark.parametrize("day,profile", [
    (DayType.WEEKEND, "weekend"), (DayType.PUBLIC_HOLIDAY, "holiday"), (DayType.HOLIDAY_SEASON, "holiday"),
])
def test_deduplicating_traffic_preserves_day_budget_and_situation(town, day, profile):
    scenario = _scenario(day)
    config = SimulationConfig(seed=5, scenario=scenario)
    pool = [Persona(id="p", identity="local", age_group="30s", gender="Female", description="", intent="",
                    purpose="snack", arrival_hour=8, budget_min=1000, budget_max=3000)]
    engine = _RecordingEngine()
    result = asyncio.run(vlm_synergy.vlm_basket_synergy(
        town, "cafe", _store("Convenience store"), pool, config=config, engine=engine,
        pathfinder=AStarPathFinder(), cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS,
        customers=4, day_type=profile,
    ))
    assert result.panel_customers == 4 and engine.contexts
    effects = compile_scenario(scenario)
    for context in engine.contexts.values():
        assert context.persona.budget_max == round(3000 * effects.budget)
        assert context.persona.budget_min == round(1000 * effects.budget)
        assert context.situation == effects.situation
