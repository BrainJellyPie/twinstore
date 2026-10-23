"""Turn a town demand estimate into one simulated day's visitor list.

Each (hour, segment, age group) row of the demand is rounded stochastically into a
visitor count, filled with personas cloned from an existing pool (matching age group and,
when possible, arrival hour) and annotated with where the visitor came from, sampled from
the demand's origin shares so annotations are consistent with the demand model.
"""

import bisect
import itertools
import math
import random

from store_emulator.domain.persona import AgeGroup, Persona
from store_emulator.domain.town import (
    BuildingKind,
    LinkedTrip,
    OriginShare,
    Town,
    TownArrival,
    TownDemand,
    TownSegment,
    VenueCategory,
)
from store_emulator.domain.types import Weekday, stable_seed
from store_emulator.engine.town.demand import purpose_label

_HOUR_TOLERANCE = 2  # hours a pool persona's own arrival hour may differ before falling back

_VENUE_PHRASES: dict[VenueCategory, str] = {
    VenueCategory.CONVENIENCE: "convenience store",
    VenueCategory.CAFE: "cafe",
    VenueCategory.BAKERY: "bakery",
    VenueCategory.PHARMACY: "pharmacy",
    VenueCategory.RESTAURANT: "restaurant",
    VenueCategory.FAST_FOOD: "fast-food place",
    VenueCategory.SUPERMARKET: "supermarket",
    VenueCategory.BAR: "bar",
    VenueCategory.GYM: "gym",
    VenueCategory.BOOKSTORE: "bookstore",
    VenueCategory.ACADEMY: "after-school academy (hagwon)",
    VenueCategory.LAUNDRY: "laundromat",
    VenueCategory.BANK: "bank",
    VenueCategory.PC_ROOM: "PC room",
}

_ORIGIN_PHRASES: dict[tuple[TownSegment, BuildingKind], str] = {
    ("resident", BuildingKind.APARTMENT): "home in an apartment block",
    ("resident", BuildingKind.HOUSE): "home in a low-rise house",
    ("resident", BuildingKind.STUDIO): "home in a studio building",
    ("resident", BuildingKind.DORMITORY): "the student dormitory",
    ("resident", BuildingKind.MIXED_USE): "home above the shops",
    ("worker", BuildingKind.OFFICE): "their office",
    ("worker", BuildingKind.SCHOOL): "the school where they work",
    ("worker", BuildingKind.HOSPITAL): "the hospital where they work",
    ("worker", BuildingKind.UNIVERSITY): "the campus where they work",
    ("student", BuildingKind.SCHOOL): "school",
    ("student", BuildingKind.UNIVERSITY): "a campus building",
    ("visitor", BuildingKind.HOSPITAL): "the hospital",
    ("visitor", BuildingKind.PARK): "the park",
    ("visitor", BuildingKind.HOTEL): "their hotel",
}
_SEGMENT_FALLBACK: dict[TownSegment, str] = {
    "resident": "home",
    "worker": "their workplace",
    "student": "class",
    "commuter": "the station",
    "visitor": "a nearby building",
    "linked": "a nearby venue",
}


def _stochastic_round(value: float, rng: random.Random) -> int:
    base = math.floor(value)
    return base + (1 if rng.random() < value - base else 0)


def _origin_weight(origin: OriginShare, hour: int, age: AgeGroup | None) -> float:
    if origin.hourly_by_age:
        ages = origin.hourly_by_age.get(hour, {})
        return sum(ages.values()) if age is None else ages.get(age, 0.0)
    return origin.expected_visitors if age is None else origin.by_age.get(age, 0.0)


def _candidates(same_age: list[Persona], same_age_any_day: list[Persona], pool: list[Persona], hour: int) -> list[Persona]:
    """Pool personas for a visitor: same age group at the same hour, then nearby hours, then any hour; the same age
    group on other days when the day has nobody of it; any age group only when no day has."""
    for group in (same_age, same_age_any_day, pool):
        for tolerance in (0, _HOUR_TOLERANCE):
            matches = [p for p in group if abs(p.arrival_hour - hour) <= tolerance]
            if matches:
                return matches
        if group:
            return group
    return pool


def plan_arrivals(
    personas: list[Persona],
    demand: TownDemand,
    town: Town,
    *,
    seed: int,
    scale: float = 1.0,
    day: Weekday | None = None,
    walk_m_per_min: float = 80.0,
) -> tuple[list[Persona], list[TownArrival]]:
    """Build the visitor list of one simulated day from a persona pool.

    `scale` multiplies the expected visitors (e.g. 0.1 to simulate a 10 % sample). Clones get
    `arrival_hour` set to the demand hour and ids "<pool id>~t<day>-<hour>h-<segment>-<age>-<k>"
    (k-th visitor of that demand row; linked rows name the venue category after "linked"), so a
    visitor keeps their id when other rows' counts change and runs on the same seed stay paired.
    With `day` set, pool personas of that weekday are preferred and clones get that day. A
    visitor is cloned from a persona of the row's age group (from another day if the day has
    none); only when the pool has nobody of that age does the visitor, their arrival and its
    origin take the age group of the persona they were cloned from. Returns (visitors,
    annotations) in the same order.
    """
    if not personas:
        raise ValueError("persona pool is empty")
    pool = [p for p in personas if p.day == day] if day is not None else list(personas)
    pool = pool or list(personas)
    by_age: dict[AgeGroup, list[Persona]] = {}
    for persona in pool:
        by_age.setdefault(persona.age_group, []).append(persona)
    by_age_any_day: dict[AgeGroup, list[Persona]] = {}
    for persona in personas:
        by_age_any_day.setdefault(persona.age_group, []).append(persona)

    origin_cache: dict[tuple[TownSegment | None, AgeGroup | None, int], tuple[list[OriginShare], list[float]]] = {}

    def origins_for(segment: TownSegment | None, age: AgeGroup | None, hour: int) -> tuple[list[OriginShare], list[float]]:
        """Direct origins of `segment` (None: every segment) weighted by their visitors of `age` (None: all)."""
        key = (segment, age, hour)
        if key not in origin_cache:
            # Demand reports sort by volume. A small volume change must not reorder the
            # same origins under a seeded draw and silently change otherwise paired trips.
            options = sorted((o for o in demand.origin_shares if segment is None or o.segment == segment),
                             key=lambda o: (o.building_id, o.segment))
            weights = [_origin_weight(o, hour, age) for o in options]
            origin_cache[key] = (options, list(itertools.accumulate(weights)))
        return origin_cache[key]

    linked_cache: dict[tuple[str, int, AgeGroup], tuple[list[LinkedTrip], list[float]]] = {}
    venues = {v.id: v for v in town.venues}

    def linked_for(category: str, hour: int, age: AgeGroup) -> tuple[list[LinkedTrip], list[float]]:
        key = (category, hour, age)
        if key not in linked_cache:
            options = sorted((t for t in demand.linked_trips if t.from_category.value == category
                              and (venue := venues.get(t.from_venue_id)) is not None and venue.is_open(hour)),
                             key=lambda t: t.from_venue_id)
            weights = [t.hourly_by_age.get(hour, {}).get(age, 0.0) if t.hourly_by_age else t.expected_visitors
                       for t in options]
            if not any(weights):
                # The pool may have no persona of the demand row's age. Keep the hour's source mix.
                weights = [sum(t.hourly_by_age.get(hour, {}).values()) if t.hourly_by_age else t.expected_visitors
                           for t in options]
            linked_cache[key] = (options, list(itertools.accumulate(weights)))
        return linked_cache[key]

    def pick[T](options: list[T], cumulative: list[float], rng: random.Random) -> T | None:
        if not options or cumulative[-1] <= 0:
            return None
        return options[min(bisect.bisect_right(cumulative, rng.random() * cumulative[-1]), len(options) - 1)]

    visitors: list[Persona] = []
    arrivals: list[TownArrival] = []
    day_key = f"{int(day)}-" if day is not None else ""
    for row in demand.hourly_by_segment:
        rng = random.Random(stable_seed(
            seed, "town-arrivals", demand.focal_venue_id, row.hour, row.segment, row.source_category, row.age_group,
        ))
        count = _stochastic_round(row.expected_visitors * scale, rng)
        if count == 0:
            continue
        order = list(_candidates(by_age.get(row.age_group, []), by_age_any_day.get(row.age_group, []), pool, row.hour))
        rng.shuffle(order)
        who = f"linked-{row.source_category}" if row.segment == "linked" else row.segment
        row_key = f"{day_key}{row.hour:02d}h-{who}-{row.age_group.removesuffix('+')}"
        for i in range(count):
            source = order[i % len(order)]
            clone_id = f"{source.id}~t{row_key}-{i}"
            age = source.age_group  # the row's, unless nobody in the pool is of the row's age group
            update: dict[str, object] = {"id": clone_id, "arrival_hour": row.hour}
            if day is not None:
                update["day"] = day
            visitors.append(source.model_copy(update=update))
            if row.segment == "linked":
                trip = pick(*linked_for(row.source_category, row.hour, age), rng)
                distance = trip.distance_m if trip else 0.0
                arrivals.append(TownArrival(
                    persona_id=clone_id, source_persona_id=source.id, hour=row.hour, segment=row.segment,
                    age_group=age, purpose=row.purpose, origin_kind=row.source_category,
                    origin_name=trip.from_name if trip else "", distance_m=distance,
                    walk_min=round(distance / walk_m_per_min, 1), came_from_venue=row.source_category,
                    came_from_venue_id=trip.from_venue_id if trip else "", is_linked_trip=True,
                ))
            else:
                origin = pick(*origins_for(row.segment, age, row.hour), rng)
                if origin is None and age != row.age_group:
                    # Nobody of the visitor's age comes from this segment's buildings (a 40s visitor "from school"):
                    # draw from where people of their age come.
                    origin = pick(*origins_for(None, age, row.hour), rng)
                if origin is None:
                    origin = pick(*origins_for(row.segment, None, row.hour), rng)
                segment = origin.segment if origin is not None else row.segment
                distance = origin.distance_m if origin else 0.0
                arrivals.append(TownArrival(
                    persona_id=clone_id, source_persona_id=source.id, hour=row.hour, segment=segment,
                    age_group=age, purpose=row.purpose if segment == row.segment else purpose_label(segment, row.hour),
                    origin_building_id=origin.building_id if origin else "",
                    origin_kind=origin.kind.value if origin else "", origin_name=origin.name if origin else "",
                    distance_m=distance, walk_min=round(distance / walk_m_per_min, 1),
                ))
    return visitors, arrivals


def _meters(distance: float) -> str:
    return f"{max(10, round(distance / 10) * 10)} m"


def _minutes(walk_min: float) -> str:
    return f"{max(1, round(walk_min))} min"


def town_context_text(arrival: TownArrival, town: Town, *, detour_factor: float = 1.3) -> str:
    """One-line English description of how the visitor got to the store, for LLM prompts."""
    trip = f"{_meters(arrival.distance_m)} ({_minutes(arrival.walk_min)})"
    if arrival.is_linked_trip:
        try:
            phrase = _VENUE_PHRASES[VenueCategory(arrival.came_from_venue)]
        except ValueError:
            phrase = arrival.came_from_venue.replace("_", " ") or "venue"
        where = "next door" if arrival.distance_m <= 60 else ("nearby" if arrival.distance_m <= 200 else "down the street")
        name = f" ({arrival.origin_name})" if arrival.origin_name else ""
        return f"Came straight from the {phrase} {where}{name}, {trip} away."

    building = town.get_building(arrival.origin_building_id) if arrival.origin_building_id else None
    if arrival.segment == "commuter":
        text = f"Passing through from the station, {trip} away."
    else:
        origin = _SEGMENT_FALLBACK[arrival.segment]
        if building is not None:
            origin = _ORIGIN_PHRASES.get((arrival.segment, building.kind), origin)
        text = f"Walked {trip} from {origin}."
    if building is not None:
        # Mention a closer convenience store the visitor walked past (signals store preference).
        closer = [
            math.hypot(v.x - building.x, v.y - building.y) * detour_factor
            for v in town.venues
            if v.category == VenueCategory.CONVENIENCE and v.id != town.focal_venue_id
        ]
        nearest = min(closer, default=math.inf)
        if nearest + 20 < arrival.distance_m:
            text = f"{text[:-1]}, passing up a closer convenience store ({_meters(nearest)} from where they started)."
    return text


def counterfactual_arrival(
    arrival: TownArrival,
    removed_venue_id: str,
    demand_without: TownDemand,
    *,
    seed: int,
    walk_m_per_min: float = 80.0,
) -> TownArrival:
    """How a visitor would have arrived had `removed_venue_id` not existed.

    Visitors chained from that venue are re-annotated as direct visitors from an origin drawn
    (seeded by visitor) from the counterfactual demand's origin shares of their age group; every
    other visitor keeps their trip (their text may still change, e.g. a closer competitor gone).
    """
    if not (arrival.is_linked_trip and arrival.came_from_venue_id == removed_venue_id):
        return arrival
    options = sorted((o for o in demand_without.origin_shares if _origin_weight(o, arrival.hour, None) > 0),
                     key=lambda o: (o.building_id, o.segment))
    if not options:
        return arrival.model_copy(update={"is_linked_trip": False, "came_from_venue": "", "came_from_venue_id": "",
                                          "segment": "resident", "origin_kind": "", "origin_name": ""})
    weights = [_origin_weight(o, arrival.hour, arrival.age_group) for o in options]
    if sum(weights) <= 0:
        weights = [_origin_weight(o, arrival.hour, None) for o in options]
    origin = random.Random(stable_seed(seed, "town-counterfactual", arrival.persona_id)).choices(options, weights)[0]
    return TownArrival(
        persona_id=arrival.persona_id, source_persona_id=arrival.source_persona_id, hour=arrival.hour,
        segment=origin.segment, age_group=arrival.age_group, purpose=purpose_label(origin.segment, arrival.hour),
        origin_building_id=origin.building_id, origin_kind=origin.kind.value, origin_name=origin.name,
        distance_m=origin.distance_m, walk_min=round(origin.distance_m / walk_m_per_min, 1),
    )
