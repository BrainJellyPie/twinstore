import json
import re
from pathlib import Path

import pytest

from store_emulator.domain.persona import AGE_GROUPS, AgeGroup, Persona
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.town import (
    BuildingKind,
    RoadKind,
    Town,
    TownArchetype,
    TownArrival,
    TownSpec,
    Venue,
    VenueCategory,
)
from store_emulator.domain.types import Weekday
from store_emulator.engine.town import (
    estimate_demand,
    generate_town,
    place_venue,
    plan_arrivals,
    remove_venue,
    synergy_analysis,
    town_context_text,
    town_from_overpass,
    with_store_hours,
)

FIXTURE = Path(__file__).parent / "fixtures" / "osm_sample.json"  # synthetic, not real OSM data


@pytest.fixture(scope="module")
def residential() -> Town:
    return generate_town(TownSpec(archetype=TownArchetype.RESIDENTIAL, seed=11))


def _focal(town: Town) -> Venue:
    focal = town.get_venue(town.focal_venue_id)
    assert focal is not None
    return focal


def _persona(pid: str, age: AgeGroup, hour: int) -> Persona:
    return Persona(
        id=pid, identity="local", age_group=age, gender="Female", description="", intent="", purpose="snack",
        arrival_hour=hour,
    )


def test_generation_is_deterministic():
    spec = TownSpec(archetype=TownArchetype.UNIVERSITY, seed=5, size_m=600)
    assert generate_town(spec).model_dump() == generate_town(spec).model_dump()
    assert generate_town(spec.model_copy(update={"seed": 6})).model_dump() != generate_town(spec).model_dump()


@pytest.mark.parametrize("archetype", list(TownArchetype))
def test_every_archetype_builds_a_consistent_town(archetype: TownArchetype):
    town = generate_town(TownSpec(archetype=archetype, seed=2, size_m=600, n_competitors=3,
                                  neighbor_categories=[VenueCategory.CAFE]))
    focal = [v for v in town.venues if v.is_focal]
    assert len(focal) == 1 and focal[0].id == town.focal_venue_id
    assert focal[0].category == VenueCategory.CONVENIENCE
    assert sum(1 for v in town.venues if v.category == VenueCategory.CONVENIENCE and not v.is_focal) == 3
    assert len({v.id for v in town.venues}) == len(town.venues)
    assert len({b.id for b in town.buildings}) == len(town.buildings)
    assert all(0 <= b.x <= town.size_m and 0 <= b.y <= town.size_m for b in town.buildings)
    assert any(r.kind == RoadKind.ARTERIAL for r in town.roads)
    cafe = next(v for v in town.venues if v.category == VenueCategory.CAFE)
    assert abs(cafe.x - focal[0].x) + abs(cafe.y - focal[0].y) < 150  # requested neighbor sits near the store


def test_archetypes_differ_in_population():
    def totals(archetype: TownArchetype) -> dict[str, int]:
        town = generate_town(TownSpec(archetype=archetype, seed=3))
        return {
            "residents": sum(b.residents for b in town.buildings),
            "workers": sum(b.workers for b in town.buildings),
            "students": sum(b.students for b in town.buildings),
        }

    business, residential, university = (
        totals(TownArchetype.BUSINESS_DISTRICT), totals(TownArchetype.RESIDENTIAL), totals(TownArchetype.UNIVERSITY),
    )
    assert business["workers"] > 2 * business["residents"]
    assert residential["residents"] > 2 * residential["workers"]
    assert university["students"] > 3 * residential["students"]

    town = generate_town(TownSpec(archetype=TownArchetype.MIXED, seed=3))
    apartments = [b.residents for b in town.buildings if b.kind == BuildingKind.APARTMENT]
    offices = [b.workers for b in town.buildings if b.kind == BuildingKind.OFFICE]
    assert apartments and all(40 <= r <= 320 for r in apartments)
    assert offices and all(30 <= w <= 900 for w in offices)


def test_residential_demand_is_plausible(residential: Town):
    demand = estimate_demand(residential)
    total = demand.total_daily_visitors
    assert 200 < total < 2500
    assert sum(demand.hourly_totals) == pytest.approx(total, rel=1e-3)
    assert all(v == 0 for v in demand.hourly_totals[:7])
    assert sum(r.expected_visitors for r in demand.hourly_by_segment) == pytest.approx(total, rel=1e-3)
    assert sum(o.share for o in demand.origin_shares) + demand.linked_visitors / total == pytest.approx(1, abs=0.01)
    assert {r.age_group for r in demand.hourly_by_segment} <= set(AGE_GROUPS)
    assert 0 < demand.market_share < 1
    assert 0 < demand.catchment_radius_50_m <= demand.catchment_radius_80_m
    assert demand.store_shares[0].expected_visitors >= demand.store_shares[-1].expected_visitors

    weekend = estimate_demand(residential, day_type="weekend")
    assert weekend.segment_totals["worker"] < demand.segment_totals["worker"]
    holiday = estimate_demand(residential, day_type="holiday")
    assert holiday.segment_totals["worker"] < weekend.segment_totals["worker"]


def test_multipliers_scale_demand(residential: Town):
    base = estimate_demand(residential)
    doubled = estimate_demand(residential, traffic_multiplier=2.0)
    assert doubled.total_daily_visitors == pytest.approx(2 * base.total_daily_visitors, rel=1e-3)
    spiked = estimate_demand(residential, hourly_multiplier={12: 3.0})
    assert spiked.hourly_totals[12] == pytest.approx(3 * base.hourly_totals[12], rel=1e-3)
    assert spiked.hourly_totals[13] == pytest.approx(base.hourly_totals[13], rel=1e-3)
    steeper = estimate_demand(residential, beta=12.0)
    assert steeper.catchment_radius_80_m < base.catchment_radius_80_m


def test_competitor_next_door_reduces_focal_demand(residential: Town):
    focal = _focal(residential)
    base = estimate_demand(residential).total_daily_visitors
    rival = place_venue(residential, VenueCategory.CONVENIENCE, focal.x + 20, focal.y, name="Rival", venue_id="rival")
    after = estimate_demand(rival)
    assert after.total_daily_visitors < 0.9 * base
    assert next(s for s in after.store_shares if s.venue_id == "rival").expected_visitors > 0
    assert estimate_demand(remove_venue(rival, "rival")).total_daily_visitors == pytest.approx(base)


def test_cafe_next_door_adds_linked_trips(residential: Town):
    focal = _focal(residential)
    base = estimate_demand(residential)
    with_cafe = place_venue(residential, VenueCategory.CAFE, focal.x + 10, focal.y, name="Corner Cafe")
    after = estimate_demand(with_cafe)
    assert after.total_daily_visitors > base.total_daily_visitors
    assert after.linked_visitors > base.linked_visitors
    assert next(t for t in after.linked_trips if t.from_name == "Corner Cafe").expected_visitors > 1
    assert after.direct_visitors == pytest.approx(base.direct_visitors)


def test_synergy_analysis_signs():
    town = generate_town(TownSpec(seed=4, size_m=400, n_competitors=1, venue_density=0.0))
    focal = _focal(town)
    town = place_venue(town, VenueCategory.CAFE, focal.x + 12, focal.y, venue_id="cafe-next-door")
    town = place_venue(town, VenueCategory.CONVENIENCE, focal.x - 30, focal.y, venue_id="rival-next-door")
    rows = {r.venue_id: r for r in synergy_analysis(town)}
    assert set(rows) == {v.id for v in town.venues if not v.is_focal}
    assert rows["cafe-next-door"].role == "complement" and rows["cafe-next-door"].effect_on_focal_visitors > 0
    assert rows["rival-next-door"].role == "competitor" and rows["rival-next-door"].effect_on_focal_pct < -5


def test_venue_editing_guards(residential: Town):
    with pytest.raises(ValueError):
        remove_venue(residential, residential.focal_venue_id)
    with pytest.raises(ValueError):
        place_venue(residential, VenueCategory.CAFE, 1.0, 1.0, venue_id=residential.focal_venue_id)
    edited = place_venue(residential, VenueCategory.BAR, 10.0, 10.0)
    assert len(edited.venues) == len(residential.venues) + 1
    assert (edited.venues[-1].open_hour, edited.venues[-1].close_hour) == (17, 2)
    assert edited.venues[-1].is_open(1) and not edited.venues[-1].is_open(12)


def test_plan_arrivals(residential: Town):
    demand = estimate_demand(residential)
    pool = [_persona(f"{age}-{hour}", age, hour) for age in AGE_GROUPS for hour in (8, 12, 19)]
    visitors, arrivals = plan_arrivals(pool, demand, residential, seed=1, scale=0.2, day=Weekday.TUE)
    expected = 0.2 * demand.total_daily_visitors
    assert len(visitors) == len(arrivals)
    assert abs(len(visitors) - expected) < 0.2 * expected
    assert len({p.id for p in visitors}) == len(visitors)
    pool_ids = {p.id for p in pool}
    for persona, arrival in zip(visitors, arrivals):
        assert arrival.persona_id == persona.id
        assert arrival.source_persona_id in pool_ids and persona.id.startswith(f"{arrival.source_persona_id}~t")
        assert persona.arrival_hour == arrival.hour and 7 <= arrival.hour < 24
        assert persona.age_group == arrival.age_group and persona.day == Weekday.TUE
        assert arrival.walk_min == pytest.approx(arrival.distance_m / 80, abs=0.06)
        if arrival.is_linked_trip:
            assert arrival.came_from_venue and residential.get_venue(arrival.came_from_venue_id) is not None
        else:
            assert residential.get_building(arrival.origin_building_id) is not None
    assert any(a.is_linked_trip for a in arrivals) and any(a.segment == "resident" for a in arrivals)
    # Visitors keep their pool persona's arrival hour when one matches.
    assert all(a.source_persona_id.endswith(f"-{a.hour}") for a in arrivals if a.hour in (8, 12, 19))

    again, _ = plan_arrivals(pool, demand, residential, seed=1, scale=0.2, day=Weekday.TUE)
    assert [p.id for p in again] == [p.id for p in visitors]
    other, _ = plan_arrivals(pool, demand, residential, seed=2, scale=0.2, day=Weekday.TUE)
    assert [p.id for p in other] != [p.id for p in visitors]
    assert all("~t" not in p.id for p in pool)
    with pytest.raises(ValueError):
        plan_arrivals([], demand, residential, seed=1)


def test_visitor_ids_follow_their_demand_row_so_a_changed_row_keeps_other_visitors_paired(residential: Town):
    pool = [_persona(f"{age}-{hour}", age, hour) for age in AGE_GROUPS for hour in (8, 12, 19)]
    base = estimate_demand(residential)
    rush = estimate_demand(residential, hourly_multiplier={12: 1.7})  # a lunch rush changes only the noon rows
    visitors, arrivals = plan_arrivals(pool, base, residential, seed=1, scale=0.3, day=Weekday.TUE)
    rushed, rushed_arrivals = plan_arrivals(pool, rush, residential, seed=1, scale=0.3, day=Weekday.TUE)
    before = {a.persona_id: a for a in arrivals}
    after = {a.persona_id: a for a in rushed_arrivals}
    assert len(after) > len(before)
    assert {i for i, a in before.items() if a.hour != 12} == {i for i, a in after.items() if a.hour != 12}
    assert set(before) <= set(after)  # a busier noon row keeps its first visitors
    # The same pool persona at the same hour. (Origins are drawn from the day's origin shares, which a busier
    # noon shifts a little, so an occasional visitor starts from another building.)
    assert all((after[i].source_persona_id, after[i].hour, after[i].segment, after[i].age_group)
               == (a.source_persona_id, a.hour, a.segment, a.age_group) for i, a in before.items())
    clones = {p.id: p for p in rushed}
    assert all(clones[p.id] == p for p in visitors)
    for arrival in arrivals:
        who = f"linked-{arrival.came_from_venue}" if arrival.is_linked_trip else arrival.segment
        assert re.fullmatch(
            rf"{re.escape(arrival.source_persona_id)}~t2-{arrival.hour:02d}h-{who}-{arrival.age_group.rstrip('+')}-\d+",
            arrival.persona_id,
        )
        # What the visitor adds to a pool id stays usable in run, journey and interview URLs.
        assert re.fullmatch(r"~t[A-Za-z0-9_-]{1,40}", arrival.persona_id.removeprefix(arrival.source_persona_id))
    monday, _ = plan_arrivals(pool, base, residential, seed=1, scale=0.3, day=Weekday.MON)
    assert not {p.id for p in monday} & set(before)  # unique across days


def test_visitors_have_the_age_group_of_the_persona_they_were_cloned_from(residential: Town):
    demand = estimate_demand(residential)
    assert any(r.age_group == "10s" and r.segment == "student" for r in demand.hourly_by_segment)
    adults = [_persona(f"{age}-{hour}", age, hour) for age in AGE_GROUPS[1:] for hour in (8, 12, 16, 19)]
    teen = _persona("teen", "10s", 16).model_copy(update={"day": Weekday.WED})
    visitors, arrivals = plan_arrivals([*adults, teen], demand, residential, seed=1, scale=0.3, day=Weekday.MON)
    teens = [(p, a) for p, a in zip(visitors, arrivals) if a.age_group == "10s"]
    # Monday has no teenager: Wednesday's stands in for the day's teenage visitors.
    assert teens and all(a.source_persona_id == "teen" and p.day == Weekday.MON for p, a in teens)
    assert all(p.age_group == a.age_group for p, a in zip(visitors, arrivals))

    # Nobody in the pool is a teenager: the visitor, the arrival and its origin take the cloned persona's age.
    visitors, arrivals = plan_arrivals(adults, demand, residential, seed=1, scale=0.3, day=Weekday.MON)
    by_id = {p.id: p for p in adults}
    for persona, arrival in zip(visitors, arrivals):
        assert persona.age_group == arrival.age_group == by_id[arrival.source_persona_id].age_group != "10s"
        building = residential.get_building(arrival.origin_building_id)
        assert not (arrival.segment == "student" and building is not None and building.kind == BuildingKind.SCHOOL)
        assert not re.search(r"from school\b", town_context_text(arrival, residential))


def test_store_hours_set_the_modeled_hours_and_our_venue_hours(residential: Town):
    store = Store(id="s", name="Corner", type="Convenience store", grid_size=(10, 10), weekly_schedule=[
        DaySchedule(day=Weekday.MON, open_hour=0, close_hour=24),
        DaySchedule(day=Weekday.TUE, open_hour=8, close_hour=20),
        DaySchedule(day=Weekday.SUN, is_open=False),
    ])
    before = residential.model_dump()
    town, hours = with_store_hours(residential, store, Weekday.TUE)
    assert hours == list(range(8, 20)) and (_focal(town).open_hour, _focal(town).close_hour) == (8, 20)
    assert residential.model_dump() == before
    tuesday = estimate_demand(town, hours=hours)
    assert all(v == 0 for h, v in enumerate(tuesday.hourly_totals) if not 8 <= h < 20)
    all_day = estimate_demand(residential)
    assert tuesday.total_daily_visitors == pytest.approx(sum(all_day.hourly_totals[8:20]), rel=1e-3)
    town, hours = with_store_hours(residential, store, Weekday.MON)
    assert hours == list(range(24)) and sum(estimate_demand(town, hours=hours).hourly_totals[:7]) > 0  # a 24-hour store
    assert with_store_hours(residential, store, Weekday.SUN)[1] == []  # closed
    assert with_store_hours(residential, store, Weekday.WED)[1] == []  # not on the schedule
    assert with_store_hours(residential, None, Weekday.MON) == (residential, list(range(7, 24)))
    legacy = store.model_copy(update={"weekly_schedule": []})
    assert with_store_hours(residential, legacy, Weekday.MON) == (residential, list(range(7, 24)))


def test_town_context_text(residential: Town):
    demand = estimate_demand(residential)
    pool = [_persona(f"p{age}", age, 12) for age in AGE_GROUPS]
    _, arrivals = plan_arrivals(pool, demand, residential, seed=3, scale=0.05)
    direct = next(a for a in arrivals if a.segment == "resident")
    text = town_context_text(direct, residential)
    assert text.startswith("Walked ") and " min) from " in text and "\n" not in text

    linked = TownArrival(
        persona_id="x~t0", source_persona_id="x", hour=9, segment="linked", age_group="30s", purpose="after cafe visit",
        origin_kind="cafe", origin_name="Corner Cafe", distance_m=26.0, walk_min=0.3, came_from_venue="cafe",
        came_from_venue_id="v-cafe-x1", is_linked_trip=True,
    )
    assert town_context_text(linked, residential) == "Came straight from the cafe next door (Corner Cafe), 30 m (1 min) away."


def test_osm_fixture_conversion():
    data: dict[str, object] = json.loads(FIXTURE.read_text())
    town = town_from_overpass(data, center_lat=37.0, center_lon=127.0, radius_m=300, focal_name="focal")
    assert town.source == "osm" and town.size_m == 600 and town.center_lat == 37.0
    focal = _focal(town)
    assert focal.name == "Synthetic Mart Focal" and focal.is_focal
    assert focal.x == pytest.approx(310, abs=1) and focal.y == pytest.approx(308, abs=1)  # 10 m east, 8 m north

    kinds = {b.name: b.kind for b in town.buildings if b.name}
    assert kinds["Synthetic Apt 101"] == BuildingKind.APARTMENT
    assert kinds["Synthetic Tower"] == BuildingKind.OFFICE
    assert kinds["Synthetic Middle School"] == BuildingKind.SCHOOL  # building=yes typed by its school grounds
    assert kinds["Synthetic Park"] == BuildingKind.PARK
    assert "Outside Apt" not in kinds
    assert sum(1 for b in town.buildings if b.name == "Synthetic Station") == 1  # railway + PT nodes merged
    apartment = next(b for b in town.buildings if b.name == "Synthetic Apt 101")
    assert apartment.floors == 15 and 200 < apartment.residents < 600
    assert next(b for b in town.buildings if b.name == "Synthetic Station").daily_passersby == 30_000

    categories = {v.category for v in town.venues}
    assert {VenueCategory.CONVENIENCE, VenueCategory.CAFE, VenueCategory.PHARMACY, VenueCategory.BAKERY,
            VenueCategory.RESTAURANT, VenueCategory.SUPERMARKET} <= categories
    assert all(v.name != "Far Away Mart" for v in town.venues)
    cafe = next(v for v in town.venues if v.category == VenueCategory.CAFE)
    assert (cafe.open_hour, cafe.close_hour) == (7, 22)
    assert {r.kind for r in town.roads} == {RoadKind.ARTERIAL, RoadKind.STREET, RoadKind.FOOTPATH}
    assert town.archetype == TownArchetype.STATION_AREA

    demand = estimate_demand(town)
    assert demand.total_daily_visitors > 0 and demand.segment_totals["commuter"] > 0


def test_osm_without_stores_gets_a_synthetic_focal_store():
    town = town_from_overpass({"elements": []}, center_lat=37.0, center_lon=127.0, radius_m=200)
    focal = _focal(town)
    assert focal.name == "Our Store" and (focal.x, focal.y) == (200, 200)
    assert estimate_demand(town).total_daily_visitors == 0
