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


def _candidates(same_age: list[Persona], pool: list[Persona], hour: int) -> list[Persona]:
    """Pool personas for a visitor: same age group at the same hour, then nearby hours, then any hour."""
    for group in (same_age, pool):
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
    ids "<pool id>~t<k>" and `arrival_hour` set to the demand hour; with `day` set, pool
    personas of that weekday are preferred and clones get that day. Returns (visitors,
    annotations) in the same order.
    """
    if not personas:
        raise ValueError("persona pool is empty")
    pool = [p for p in personas if p.day == day] if day is not None else list(personas)
    pool = pool or list(personas)
    by_age: dict[AgeGroup, list[Persona]] = {}
    for persona in pool:
        by_age.setdefault(persona.age_group, []).append(persona)

    origin_cache: dict[tuple[TownSegment, AgeGroup], tuple[list[OriginShare], list[float]]] = {}

    def origins_for(segment: TownSegment, age: AgeGroup) -> tuple[list[OriginShare], list[float]]:
        key = (segment, age)
        if key not in origin_cache:
            options = [o for o in demand.origin_shares if o.segment == segment]
            weights = [o.by_age.get(age, 0.0) for o in options]
            if sum(weights) <= 0:
                weights = [o.expected_visitors for o in options]
            origin_cache[key] = (options, list(itertools.accumulate(weights)))
        return origin_cache[key]

    linked_cache: dict[str, tuple[list[LinkedTrip], list[float]]] = {}

    def linked_for(category: str) -> tuple[list[LinkedTrip], list[float]]:
        if category not in linked_cache:
            options = [t for t in demand.linked_trips if t.from_category.value == category]
            linked_cache[category] = (options, list(itertools.accumulate(t.expected_visitors for t in options)))
        return linked_cache[category]

    def pick[T](options: list[T], cumulative: list[float], rng: random.Random) -> T | None:
        if not options or cumulative[-1] <= 0:
            return None
        return options[min(bisect.bisect_right(cumulative, rng.random() * cumulative[-1]), len(options) - 1)]

    visitors: list[Persona] = []
    arrivals: list[TownArrival] = []
    counter = 0
    for row in demand.hourly_by_segment:
        rng = random.Random(stable_seed(
            seed, "town-arrivals", demand.focal_venue_id, row.hour, row.segment, row.source_category, row.age_group,
        ))
        count = _stochastic_round(row.expected_visitors * scale, rng)
        if count == 0:
            continue
        order = list(_candidates(by_age.get(row.age_group, []), pool, row.hour))
        rng.shuffle(order)
        for i in range(count):
            source = order[i % len(order)]
            clone_id = f"{source.id}~t{counter}"
            counter += 1
            update: dict[str, object] = {"id": clone_id, "arrival_hour": row.hour}
            if day is not None:
                update["day"] = day
            visitors.append(source.model_copy(update=update))
            if row.segment == "linked":
                trip = pick(*linked_for(row.source_category), rng)
                distance = trip.distance_m if trip else 0.0
                arrivals.append(TownArrival(
                    persona_id=clone_id, source_persona_id=source.id, hour=row.hour, segment=row.segment,
                    age_group=row.age_group, purpose=row.purpose, origin_kind=row.source_category,
                    origin_name=trip.from_name if trip else "", distance_m=distance,
                    walk_min=round(distance / walk_m_per_min, 1), came_from_venue=row.source_category,
                    came_from_venue_id=trip.from_venue_id if trip else "", is_linked_trip=True,
                ))
            else:
                origin = pick(*origins_for(row.segment, row.age_group), rng)
                distance = origin.distance_m if origin else 0.0
                arrivals.append(TownArrival(
                    persona_id=clone_id, source_persona_id=source.id, hour=row.hour, segment=row.segment,
                    age_group=row.age_group, purpose=row.purpose,
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
