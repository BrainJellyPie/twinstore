"""Linked visitors must come from the venues serving their hour and age group."""

from collections import Counter

import pytest

from store_emulator.domain.persona import AGE_GROUPS, Persona
from store_emulator.domain.town import (
    Building, BuildingKind, HourlySegmentDemand, LinkedTrip, Town, TownArchetype,
    Venue, VenueCategory,
)
from store_emulator.engine.town import estimate_demand, plan_arrivals


def _town(hours: tuple[tuple[int, int], tuple[int, int]]) -> Town:
    return Town(
        id="town", name="Different cafe hours", archetype=TownArchetype.RESIDENTIAL,
        size_m=200, focal_venue_id="store",
        buildings=[Building(id="home", kind=BuildingKind.APARTMENT, x=100, y=100, residents=5000)],
        venues=[
            Venue(id="store", name="Store", category=VenueCategory.CONVENIENCE, x=100, y=100),
            *[Venue(id=f"cafe-{i}", name=f"Cafe {i}", category=VenueCategory.CAFE,
                    x=90 + i * 20, y=100, open_hour=start, close_hour=end)
              for i, (start, end) in enumerate(hours)],
        ],
    )


def _pool() -> list[Persona]:
    return [Persona(id=f"p-{age}", identity="local", age_group=age, gender="Female",
                    description="", intent="", purpose="snack", arrival_hour=12) for age in AGE_GROUPS]


@pytest.mark.parametrize("hours", [
    ((6, 12), (18, 24)), ((0, 12), (12, 24)), ((22, 6), (6, 22)),
    ((23, 0), (0, 23)), ((7, 7), (10, 11)), ((0, 24), (18, 2)),
])
@pytest.mark.parametrize("seed", [0, 7, 42])
@pytest.mark.parametrize("legacy", [False, True])
def test_linked_origins_are_open_at_arrival(hours, seed, legacy):
    town = _town(hours)
    demand = estimate_demand(town, hours=range(24))
    if legacy:
        demand = demand.model_copy(update={"linked_trips": [
            LinkedTrip.model_validate(t.model_dump(exclude={"hourly_by_age"})) for t in demand.linked_trips
        ]})
    visitors, arrivals = plan_arrivals(_pool(), demand, town, seed=seed, scale=5)
    linked = [a for a in arrivals if a.is_linked_trip]
    assert linked
    assert len({p.id for p in visitors}) == len(visitors) == len(arrivals)
    for arrival in linked:
        venue = town.get_venue(arrival.came_from_venue_id)
        assert venue is not None and venue.is_open(arrival.hour), (arrival.hour, arrival.came_from_venue_id)


def test_source_weights_retain_the_hour_and_age_demand():
    town = _town(((6, 12), (18, 24)))
    demand = estimate_demand(town, hours=range(24))
    for trip in demand.linked_trips:
        data = trip.model_dump()["hourly_by_age"]
        assert sum(sum(ages.values()) for ages in data.values()) == pytest.approx(trip.expected_visitors, abs=0.0001)
        for hour, ages in data.items():
            venue = town.get_venue(trip.from_venue_id)
            assert venue is not None and venue.is_open(hour)
            assert all(value > 0 for value in ages.values())
    for row in demand.hourly_by_segment:
        if row.segment == "linked":
            total = sum(t.model_dump()["hourly_by_age"].get(row.hour, {}).get(row.age_group, 0)
                        for t in demand.linked_trips)
            assert total == pytest.approx(row.expected_visitors, abs=0.0001)


@pytest.mark.parametrize("missing_age", [False, True])
def test_linked_sources_use_conditional_weights_and_keep_seeded_pairing(missing_age):
    town = _town(((0, 24), (0, 24)))
    demand = estimate_demand(town, hours=[8, 20])
    # Both cafes have identical daily totals but serve disjoint age/hour combinations.
    trips = [LinkedTrip.model_validate({
        "from_venue_id": f"cafe-{i}", "from_name": f"Cafe {i}", "from_category": "cafe",
        "distance_m": 13, "expected_visitors": 200,
        "hourly_by_age": {8: {"20s" if i == 0 else "60s+": 100},
                          20: {"60s+" if i == 0 else "20s": 100}},
    }) for i in range(2)]
    rows = [HourlySegmentDemand(hour=h, segment="linked", age_group=age, purpose="after cafe visit",
                                source_category="cafe", expected_visitors=100)
            for h in (8, 20) for age in ("20s", "60s+")]
    demand = demand.model_copy(update={"linked_trips": trips, "hourly_by_segment": rows})
    pool = [p for p in _pool() if not missing_age or p.age_group == "30s"]
    original = plan_arrivals(pool, demand, town, seed=42)
    people, arrivals = original
    if missing_age:
        assert {a.age_group for a in arrivals} == {"30s"}
        assert all(a.came_from_venue_id for a in arrivals)  # fall back to that hour's entire age mix
        assert len(Counter(a.came_from_venue_id for a in arrivals)) == 2
    else:
        for a in arrivals:
            expected = 0 if (a.hour == 8) == (a.age_group == "20s") else 1
            assert a.came_from_venue_id == f"cafe-{expected}"
    reordered = demand.model_copy(update={"linked_trips": list(reversed(trips))})
    assert plan_arrivals(pool, reordered, town, seed=42) == original
    busier = demand.model_copy(update={"hourly_by_segment": [
        r.model_copy(update={"expected_visitors": 150}) if r.hour == 8 else r for r in rows
    ]})
    more_people, more_arrivals = plan_arrivals(pool, busier, town, seed=42)
    by_id = {a.persona_id: a for a in more_arrivals}
    assert len(more_people) > len(people)
    assert all(by_id[a.persona_id] == a for a in arrivals)
