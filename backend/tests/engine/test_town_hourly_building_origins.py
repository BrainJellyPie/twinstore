"""Direct and counterfactual origins follow building exposure at the arrival hour."""

from collections import Counter

import pytest

from store_emulator.domain.persona import AGE_GROUPS, Persona
from store_emulator.domain.town import Building, BuildingKind, Town, TownArchetype, Venue, VenueCategory
from store_emulator.engine.town import DemandParams, counterfactual_arrival, estimate_demand, plan_arrivals


def _town():
    return Town(id="town", name="Night origins", archetype=TownArchetype.MIXED, size_m=200,
                focal_venue_id="store", venues=[Venue(id="store", name="Store", category=VenueCategory.CONVENIENCE,
                                                     x=100, y=100)],
                buildings=[Building(id=kind.value, kind=kind, x=100, y=100, visitors=5000)
                           for kind in (BuildingKind.HOSPITAL, BuildingKind.HOTEL, BuildingKind.PARK)])


def _pool(missing_ages=False):
    return [Persona(id=f"p{i}", identity="local", age_group=age, gender="Female", description="", intent="",
                    purpose="snack", arrival_hour=23) for i, age in enumerate(["30s"] if missing_ages else AGE_GROUPS)]


@pytest.mark.parametrize("profile", ["weekday", "weekend", "holiday"])
@pytest.mark.parametrize("seed", [0, 7, 42])
@pytest.mark.parametrize("missing_ages", [False, True])
def test_arrivals_never_draw_from_buildings_absent_at_that_hour(profile, seed, missing_ages):
    town = _town()
    demand = estimate_demand(town, day_type=profile, hours=range(24))
    visitors, arrivals = plan_arrivals(_pool(missing_ages), demand, town, seed=seed)
    assert visitors and len(visitors) == len({p.id for p in visitors})
    params = DemandParams()
    for arrival in arrivals:
        origin = town.get_building(arrival.origin_building_id)
        assert origin is not None
        key = f"visitor:{origin.kind.value}"
        exposure = params.exposure.get(key, params.exposure["visitor"])
        assert exposure["weekday" if profile == "weekday" else "weekend"][arrival.hour] > 0
    night = [a for a in arrivals if a.hour == 23]
    assert night and {a.origin_building_id for a in night} == {"hotel"}


def test_hourly_origin_weights_sum_back_to_demand():
    demand = estimate_demand(_town(), hours=range(24))
    for origin in demand.origin_shares:
        by_hour = origin.model_dump()["hourly_by_age"]
        assert sum(sum(ages.values()) for ages in by_hour.values()) == pytest.approx(origin.expected_visitors, abs=.0001)
    for row in demand.hourly_by_segment:
        value = sum(o.model_dump()["hourly_by_age"].get(row.hour, {}).get(row.age_group, 0)
                    for o in demand.origin_shares if o.segment == row.segment)
        assert value == pytest.approx(row.expected_visitors, abs=.0001)


@pytest.mark.parametrize("hour", [0, 7, 22, 23])
def test_removed_venue_visitors_are_rerouted_to_an_active_building(hour):
    town = _town()
    demand = estimate_demand(town, hours=range(24))
    _, original = plan_arrivals(_pool(), demand, town, seed=42)
    arrivals = [a.model_copy(update={"is_linked_trip": True, "came_from_venue_id": "cafe",
                                    "came_from_venue": "cafe"}) for a in original if a.hour == hour]
    assert arrivals
    positive = {o.building_id for o in estimate_demand(town, hours=[hour]).origin_shares}
    moved = [counterfactual_arrival(a, "cafe", demand, seed=42) for a in arrivals]
    assert {a.origin_building_id for a in moved} <= positive
    assert all(not a.is_linked_trip and not a.came_from_venue_id for a in moved)
    reordered = demand.model_copy(update={"origin_shares": list(reversed(demand.origin_shares))})
    assert [counterfactual_arrival(a, "cafe", reordered, seed=42) for a in arrivals] == moved


def test_other_hours_keep_their_origins_when_one_hours_traffic_changes():
    town = _town()
    base = estimate_demand(town, hours=range(24))
    rush = estimate_demand(town, hours=range(24), hourly_multiplier={12: 5})
    before, notes = plan_arrivals(_pool(), base, town, seed=42)
    after, more_notes = plan_arrivals(_pool(), rush, town, seed=42)
    assert len(after) > len(before)
    by_id = {a.persona_id: a for a in more_notes}
    assert all(a == by_id[a.persona_id] for a in notes)


def test_legacy_origin_reports_still_use_their_available_daily_weights():
    town = _town()
    raw = estimate_demand(town, hours=range(24)).model_dump()
    for origin in raw["origin_shares"]:
        origin.pop("hourly_by_age", None)
    from store_emulator.domain.town import TownDemand
    demand = TownDemand.model_validate(raw)
    _, notes = plan_arrivals(_pool(), demand, town, seed=42)
    assert Counter(a.origin_building_id for a in notes).keys() == {"hotel", "hospital", "park"}
    assert plan_arrivals(_pool(), demand, town, seed=42)[1] == notes
