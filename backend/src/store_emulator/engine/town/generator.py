"""Procedural town generation and what-if venue editing.

A town is a jittered street grid. Each block between streets gets a zone that depends
on the archetype and on how far the block is from the center (commercial core in the
middle, homes / campus / offices around it), and the zone decides which buildings are
packed into it. Building populations come from per-floor priors (below), scaled by
`TownSpec.density`. Everything is deterministic given `TownSpec.seed`.
"""

import math
import random
from typing import Literal

from store_emulator.domain.town import (
    Building,
    BuildingKind,
    Road,
    RoadKind,
    Town,
    TownArchetype,
    TownSpec,
    Venue,
    VenueCategory,
)
from store_emulator.domain.types import stable_seed

type _Zone = Literal[
    "commercial", "apartments", "houses", "studios", "offices", "campus", "school", "park", "hospital", "hotels",
]
type _Rect = tuple[float, float, float, float]  # x0, y0, x1, y1

# Typical opening hours (open, close); close < open wraps past midnight.
DEFAULT_OPEN_HOURS: dict[VenueCategory, tuple[int, int]] = {
    VenueCategory.CONVENIENCE: (0, 24),
    VenueCategory.CAFE: (7, 22),
    VenueCategory.BAKERY: (7, 22),
    VenueCategory.PHARMACY: (9, 21),
    VenueCategory.RESTAURANT: (11, 22),
    VenueCategory.FAST_FOOD: (9, 24),
    VenueCategory.SUPERMARKET: (9, 23),
    VenueCategory.BAR: (17, 2),
    VenueCategory.GYM: (6, 23),
    VenueCategory.BOOKSTORE: (10, 22),
    VenueCategory.ACADEMY: (14, 22),
    VenueCategory.LAUNDRY: (0, 24),
    VenueCategory.BANK: (9, 16),
    VenueCategory.PC_ROOM: (0, 24),
}

_CATEGORY_LABELS: dict[VenueCategory, str] = {
    VenueCategory.CONVENIENCE: "Mart",
    VenueCategory.CAFE: "Cafe",
    VenueCategory.BAKERY: "Bakery",
    VenueCategory.PHARMACY: "Pharmacy",
    VenueCategory.RESTAURANT: "Restaurant",
    VenueCategory.FAST_FOOD: "Burger & Fries",
    VenueCategory.SUPERMARKET: "Supermarket",
    VenueCategory.BAR: "Pub",
    VenueCategory.GYM: "Fitness",
    VenueCategory.BOOKSTORE: "Books",
    VenueCategory.ACADEMY: "Academy",
    VenueCategory.LAUNDRY: "Laundromat",
    VenueCategory.BANK: "Bank",
    VenueCategory.PC_ROOM: "PC Room",
}

_COMPETITOR_NAMES: list[str] = [
    "Corner Mart", "Daily Mart", "Quick Stop", "Night Owl Mart", "Easy Mart", "Fresh 24", "Neighbor Mart", "Metro Mart",
]
_PLACE_NAMES: list[str] = [
    "Greenview", "Riverside", "Sunrise", "Maple", "Cedar", "Hillside", "Lakeview", "Parkside", "Starlight", "Bluebell",
]

# Street spacing (m). Apartment-heavy and suburban towns use large superblocks.
_BLOCK_M: dict[TownArchetype, float] = {
    TownArchetype.RESIDENTIAL: 140.0,
    TownArchetype.UNIVERSITY: 125.0,
    TownArchetype.BUSINESS_DISTRICT: 110.0,
    TownArchetype.SUBURBAN: 170.0,
    TownArchetype.STATION_AREA: 100.0,
    TownArchetype.TOURIST: 95.0,
    TownArchetype.MIXED: 120.0,
}

# Weekday passersby at the central station at density 0.5 (0 = no station).
# Seoul subway stations range from ~10k (outer) to 100k+ (hubs) boardings + alightings per day.
_STATION_PASSERSBY: dict[TownArchetype, int] = {
    TownArchetype.RESIDENTIAL: 20_000,
    TownArchetype.UNIVERSITY: 35_000,
    TownArchetype.BUSINESS_DISTRICT: 60_000,
    TownArchetype.SUBURBAN: 0,
    TownArchetype.STATION_AREA: 80_000,
    TownArchetype.TOURIST: 45_000,
    TownArchetype.MIXED: 30_000,
}

# Special blocks per 800 m × 800 m: (schools, parks, hospitals).
_SPECIAL_BLOCKS: dict[TownArchetype, tuple[int, int, int]] = {
    TownArchetype.RESIDENTIAL: (2, 1, 0),
    TownArchetype.UNIVERSITY: (0, 0, 0),
    TownArchetype.BUSINESS_DISTRICT: (0, 1, 1),
    TownArchetype.SUBURBAN: (1, 2, 0),
    TownArchetype.STATION_AREA: (1, 0, 1),
    TownArchetype.TOURIST: (0, 2, 0),
    TownArchetype.MIXED: (1, 1, 1),
}

# Background venues per 800 m × 800 m at venue_density = 1.
_VENUE_COUNTS: dict[TownArchetype, dict[VenueCategory, int]] = {
    TownArchetype.RESIDENTIAL: {
        VenueCategory.CAFE: 6, VenueCategory.BAKERY: 2, VenueCategory.PHARMACY: 2, VenueCategory.RESTAURANT: 8,
        VenueCategory.FAST_FOOD: 2, VenueCategory.SUPERMARKET: 1, VenueCategory.BAR: 2, VenueCategory.GYM: 1,
        VenueCategory.ACADEMY: 5, VenueCategory.LAUNDRY: 2, VenueCategory.BANK: 1, VenueCategory.PC_ROOM: 1,
    },
    TownArchetype.UNIVERSITY: {
        VenueCategory.CAFE: 10, VenueCategory.BAKERY: 2, VenueCategory.PHARMACY: 1, VenueCategory.RESTAURANT: 14,
        VenueCategory.FAST_FOOD: 4, VenueCategory.SUPERMARKET: 1, VenueCategory.BAR: 6, VenueCategory.GYM: 2,
        VenueCategory.ACADEMY: 1, VenueCategory.LAUNDRY: 3, VenueCategory.BANK: 1, VenueCategory.BOOKSTORE: 1,
        VenueCategory.PC_ROOM: 3,
    },
    TownArchetype.BUSINESS_DISTRICT: {
        VenueCategory.CAFE: 14, VenueCategory.BAKERY: 2, VenueCategory.PHARMACY: 2, VenueCategory.RESTAURANT: 16,
        VenueCategory.FAST_FOOD: 4, VenueCategory.BAR: 5, VenueCategory.GYM: 3, VenueCategory.ACADEMY: 1,
        VenueCategory.LAUNDRY: 1, VenueCategory.BANK: 4, VenueCategory.BOOKSTORE: 1, VenueCategory.PC_ROOM: 1,
    },
    TownArchetype.SUBURBAN: {
        VenueCategory.CAFE: 3, VenueCategory.BAKERY: 1, VenueCategory.PHARMACY: 1, VenueCategory.RESTAURANT: 4,
        VenueCategory.FAST_FOOD: 1, VenueCategory.SUPERMARKET: 2, VenueCategory.BAR: 1, VenueCategory.GYM: 1,
        VenueCategory.ACADEMY: 2, VenueCategory.LAUNDRY: 1, VenueCategory.BANK: 1,
    },
    TownArchetype.STATION_AREA: {
        VenueCategory.CAFE: 12, VenueCategory.BAKERY: 3, VenueCategory.PHARMACY: 3, VenueCategory.RESTAURANT: 14,
        VenueCategory.FAST_FOOD: 5, VenueCategory.SUPERMARKET: 1, VenueCategory.BAR: 6, VenueCategory.GYM: 2,
        VenueCategory.ACADEMY: 3, VenueCategory.LAUNDRY: 1, VenueCategory.BANK: 3, VenueCategory.BOOKSTORE: 1,
        VenueCategory.PC_ROOM: 2,
    },
    TownArchetype.TOURIST: {
        VenueCategory.CAFE: 12, VenueCategory.BAKERY: 4, VenueCategory.PHARMACY: 2, VenueCategory.RESTAURANT: 16,
        VenueCategory.FAST_FOOD: 4, VenueCategory.SUPERMARKET: 1, VenueCategory.BAR: 6, VenueCategory.LAUNDRY: 1,
        VenueCategory.BANK: 1, VenueCategory.BOOKSTORE: 1, VenueCategory.PC_ROOM: 1,
    },
    TownArchetype.MIXED: {
        VenueCategory.CAFE: 8, VenueCategory.BAKERY: 2, VenueCategory.PHARMACY: 2, VenueCategory.RESTAURANT: 10,
        VenueCategory.FAST_FOOD: 3, VenueCategory.SUPERMARKET: 1, VenueCategory.BAR: 3, VenueCategory.GYM: 2,
        VenueCategory.ACADEMY: 3, VenueCategory.LAUNDRY: 2, VenueCategory.BANK: 2, VenueCategory.BOOKSTORE: 1,
        VenueCategory.PC_ROOM: 1,
    },
}

# How likely a building kind is to host a street-level shop.
_SHOP_HOST_WEIGHT: dict[BuildingKind, float] = {
    BuildingKind.MIXED_USE: 4.0,
    BuildingKind.STUDIO: 2.0,
    BuildingKind.OFFICE: 2.0,
    BuildingKind.HOTEL: 1.5,
    BuildingKind.STATION: 1.0,
    BuildingKind.APARTMENT: 0.6,
    BuildingKind.DORMITORY: 0.5,
    BuildingKind.HOSPITAL: 0.5,
    BuildingKind.UNIVERSITY: 0.4,
    BuildingKind.HOUSE: 0.3,
}

_ARTERIAL_HALF_WIDTH = 12.0
_STREET_HALF_WIDTH = 5.0
_SIDEWALK = 2.0


def _zone_weights(archetype: TownArchetype, r: float) -> dict[_Zone, float]:
    """Zone mix for an ordinary block at normalized distance r (0 = center, 1 = edge midpoint)."""
    match archetype:
        case TownArchetype.RESIDENTIAL:
            if r < 0.3:
                return {"commercial": 0.7, "studios": 0.3}
            return {"apartments": 0.55, "houses": 0.33, "studios": 0.08, "commercial": 0.04}
        case TownArchetype.UNIVERSITY:
            if r < 0.45:
                return {"commercial": 0.45, "studios": 0.55}
            return {"studios": 0.4, "houses": 0.35, "apartments": 0.15, "commercial": 0.1}
        case TownArchetype.BUSINESS_DISTRICT:
            if r < 0.55:
                return {"offices": 0.75, "commercial": 0.15, "studios": 0.1}
            return {"offices": 0.35, "studios": 0.25, "apartments": 0.2, "commercial": 0.15, "hotels": 0.05}
        case TownArchetype.SUBURBAN:
            if r < 0.25:
                return {"commercial": 0.8, "apartments": 0.2}
            return {"houses": 0.7, "apartments": 0.25, "commercial": 0.05}
        case TownArchetype.STATION_AREA:
            if r < 0.3:
                return {"commercial": 0.55, "offices": 0.25, "studios": 0.1, "hotels": 0.1}
            if r < 0.65:
                return {"studios": 0.35, "commercial": 0.2, "offices": 0.15, "apartments": 0.3}
            return {"apartments": 0.5, "houses": 0.4, "studios": 0.1}
        case TownArchetype.TOURIST:
            if r < 0.4:
                return {"commercial": 0.65, "hotels": 0.3, "studios": 0.05}
            return {"houses": 0.4, "hotels": 0.2, "commercial": 0.3, "studios": 0.1}
        case TownArchetype.MIXED:
            if r < 0.3:
                return {"commercial": 0.4, "offices": 0.3, "studios": 0.3}
            return {"apartments": 0.35, "houses": 0.25, "studios": 0.15, "offices": 0.15, "commercial": 0.1}


def _grid_lines(size: float, block: float, rng: random.Random) -> tuple[list[float], int]:
    """Street positions along one axis (both edges included) and the index of the central arterial."""
    n = max(2, round(size / block))
    spacing = size / n
    lines = [0.0] + [i * spacing + rng.uniform(-0.12, 0.12) * spacing for i in range(1, n)] + [size]
    center = min(range(1, n), key=lambda i: abs(lines[i] - size / 2))
    return lines, center


def _is_arterial(index: int, center: int, size: float) -> bool:
    # Large towns get an extra arterial every fourth street.
    return index == center or (size > 1200 and (index - center) % 4 == 0 and index != 0)


def _pack(
    rect: _Rect, width: float, depth: float, gap: float, fill: float, rng: random.Random,
) -> list[tuple[float, float, float, float]]:
    """Grid-pack footprints into a rectangle; returns (cx, cy, w, d) for the kept lots."""
    x0, y0, x1, y1 = rect
    span_w, span_d = x1 - x0, y1 - y0
    if span_w < 6 or span_d < 6:
        return []
    w, d = min(width, span_w), min(depth, span_d)
    cols = max(1, int((span_w + gap) // (w + gap)))
    rows = max(1, int((span_d + gap) // (d + gap)))
    pad_x = (span_w - (cols * w + (cols - 1) * gap)) / 2
    pad_y = (span_d - (rows * d + (rows - 1) * gap)) / 2
    lots: list[tuple[float, float, float, float]] = []
    for c in range(cols):
        for r in range(rows):
            if rng.random() >= fill:
                continue
            jw, jd = w * rng.uniform(0.85, 1.0), d * rng.uniform(0.85, 1.0)
            cx = x0 + pad_x + w / 2 + c * (w + gap)
            cy = y0 + pad_y + d / 2 + r * (d + gap)
            lots.append((cx, cy, jw, jd))
    return lots


def _floors(lo: int, hi: int, density: float, rng: random.Random) -> int:
    return max(1, round(rng.uniform(lo, hi) * (0.6 + 0.8 * density)))


def _populate(
    kind: BuildingKind, floors: int, w: float, d: float, archetype: TownArchetype, density: float, rng: random.Random,
) -> dict[str, int]:
    """People priors per building (see module docstring of the demand model for sources)."""
    jitter = rng.uniform(0.9, 1.1)
    match kind:
        case BuildingKind.APARTMENT:
            # Korean towers: 2–4 units per floor per tower, 2.4 persons per household.
            units = 4 if w * d >= 700 else 2
            return {"residents": round(floors * units * 2.4 * jitter)}
        case BuildingKind.HOUSE:
            # Multi-household houses / villas: 1–2 households per floor, 2.3 persons each.
            return {"residents": round(floors * rng.choice([1, 1, 2]) * 2.3 * jitter)}
        case BuildingKind.STUDIO:
            units = max(4, int(w * d / 40))  # ~25 m² studios plus corridors
            return {"residents": round(floors * units * 1.1 * jitter), "workers": floors * 2}
        case BuildingKind.DORMITORY:
            return {"residents": round(floors * 36 * jitter)}
        case BuildingKind.OFFICE:
            # ~25 m² gross floor area per worker, capped for very tall towers.
            return {"workers": min(900, round(floors * w * d / 25 * jitter))}
        case BuildingKind.MIXED_USE:
            upper = max(0, floors - 1)
            return {
                "workers": round((4 + upper * rng.uniform(2, 6)) * jitter),
                "residents": round(upper * rng.uniform(0, 2.5) * 1.8),
            }
        case BuildingKind.SCHOOL:
            students = round(rng.uniform(450, 1100) * (0.7 + 0.6 * density))
            return {"students": students, "workers": max(20, students // 14)}
        case BuildingKind.UNIVERSITY:
            return {"students": round(floors * 110 * jitter), "workers": floors * 9}
        case BuildingKind.STATION:
            base = _STATION_PASSERSBY[archetype] or 8_000
            return {"daily_passersby": round(base * (0.6 + 0.8 * density) * jitter)}
        case BuildingKind.HOSPITAL:
            return {"workers": round(floors * 45 * jitter), "visitors": round(floors * 110 * jitter)}
        case BuildingKind.HOTEL:
            # 16 rooms per floor, 1.6 guests per room, 75 % occupancy.
            return {"visitors": round(floors * 16 * 1.6 * 0.75 * jitter), "workers": floors * 3}
        case BuildingKind.PARK:
            landmark = 3.0 if archetype == TownArchetype.TOURIST else 1.0
            return {"visitors": round(w * d / 30 * landmark * jitter)}


def _choose(weights: dict[_Zone, float], rng: random.Random) -> _Zone:
    zones = list(weights)
    return rng.choices(zones, weights=[weights[z] for z in zones])[0]


def _frontage(cx: float, cy: float, w: float, d: float, xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Point on the building edge facing the nearest street (where a shop door would be)."""
    nx = min(xs, key=lambda x: abs(x - cx))
    ny = min(ys, key=lambda y: abs(y - cy))
    if abs(nx - cx) - w / 2 <= abs(ny - cy) - d / 2:
        return (cx + math.copysign(w / 2, nx - cx), cy)
    return (cx, cy + math.copysign(d / 2, ny - cy))


def generate_town(spec: TownSpec) -> Town:
    """Build a procedural town for `spec`; identical specs give identical towns."""
    rng = random.Random(stable_seed("town", spec.archetype.value, spec.seed))
    size = spec.size_m
    archetype = spec.archetype
    area_scale = (size / 800.0) ** 2

    xs, cx_index = _grid_lines(size, _BLOCK_M[archetype], rng)
    ys, cy_index = _grid_lines(size, _BLOCK_M[archetype], rng)

    roads: list[Road] = []
    for i, x in enumerate(xs):
        kind = RoadKind.ARTERIAL if _is_arterial(i, cx_index, size) else RoadKind.STREET
        roads.append(Road(id=f"r-x{i}", kind=kind, points=[(x, 0.0), (x, size)], name=f"{i + 1}-gil"))
    for j, y in enumerate(ys):
        kind = RoadKind.ARTERIAL if _is_arterial(j, cy_index, size) else RoadKind.STREET
        roads.append(Road(id=f"r-y{j}", kind=kind, points=[(0.0, y), (size, y)], name=f"Avenue {j + 1}"))

    def half_width(index: int, center: int) -> float:
        return (_ARTERIAL_HALF_WIDTH if _is_arterial(index, center, size) else _STREET_HALF_WIDTH) + _SIDEWALK

    blocks: list[_Rect] = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            blocks.append((
                xs[i] + half_width(i, cx_index), ys[j] + half_width(j, cy_index),
                xs[i + 1] - half_width(i + 1, cx_index), ys[j + 1] - half_width(j + 1, cy_index),
            ))

    half = size / 2

    def radius(rect: _Rect) -> float:
        return math.hypot((rect[0] + rect[2]) / 2 - half, (rect[1] + rect[3]) / 2 - half) / half

    # Assign zones: campus first, then the special single-use blocks, then the archetype mix.
    zones: list[_Zone | None] = [None] * len(blocks)
    if archetype == TownArchetype.UNIVERSITY:
        for k, rect in enumerate(blocks):
            u, v = (rect[0] + rect[2]) / 2 / size, (rect[1] + rect[3]) / 2 / size
            if u > 0.55 and v > 0.45:
                zones[k] = "campus"
    n_schools, n_parks, n_hospitals = _SPECIAL_BLOCKS[archetype]
    specials: list[tuple[_Zone, int, tuple[float, float]]] = [
        ("school", n_schools, (0.3, 1.0)), ("park", n_parks, (0.2, 1.1)), ("hospital", n_hospitals, (0.2, 0.9)),
    ]
    for zone, count, (r_lo, r_hi) in specials:
        wanted = max(1, round(count * area_scale)) if count else 0
        free = [k for k, rect in enumerate(blocks) if zones[k] is None and r_lo <= radius(rect) <= r_hi]
        for k in rng.sample(free, min(wanted, len(free))):
            zones[k] = zone
    for k, rect in enumerate(blocks):
        if zones[k] is None:
            zones[k] = _choose(_zone_weights(archetype, radius(rect)), rng)

    buildings: list[Building] = []
    density = spec.density
    fill = 0.5 + 0.45 * density

    def add(kind: BuildingKind, cx: float, cy: float, w: float, d: float, floors: int, name: str) -> None:
        people = _populate(kind, floors, w, d, archetype, density, rng)
        buildings.append(Building(
            id=f"b{len(buildings):04d}", kind=kind, name=name, x=round(cx, 1), y=round(cy, 1),
            width=round(w, 1), depth=round(d, 1), floors=floors,
            residents=people.get("residents", 0), workers=people.get("workers", 0),
            students=people.get("students", 0), daily_passersby=people.get("daily_passersby", 0),
            visitors=people.get("visitors", 0),
        ))

    for k, rect in enumerate(blocks):
        zone = zones[k]
        place = _PLACE_NAMES[k % len(_PLACE_NAMES)]
        x0, y0, x1, y1 = rect
        match zone:
            case "commercial":
                for lot in _pack(rect, 14, 18, 2, 0.6 + 0.35 * density, rng):
                    add(BuildingKind.MIXED_USE, *lot, _floors(2, 6, density, rng), f"{place} Plaza")
            case "apartments":
                lo, hi = (5, 12) if archetype == TownArchetype.SUBURBAN else (12, 24)
                for n, lot in enumerate(_pack(rect, 18, 45, 22, fill + 0.1, rng)):
                    add(BuildingKind.APARTMENT, *lot, _floors(lo, hi, density, rng), f"{place} Apt {101 + n}")
            case "houses":
                # Split the block with an alley along its long axis and pack houses on both sides.
                if x1 - x0 >= y1 - y0:
                    mid = (y0 + y1) / 2
                    halves: list[_Rect] = [(x0, y0, x1, mid - 2), (x0, mid + 2, x1, y1)]
                    roads.append(Road(id=f"r-alley{k}", kind=RoadKind.ALLEY, points=[(x0, mid), (x1, mid)]))
                else:
                    mid = (x0 + x1) / 2
                    halves = [(x0, y0, mid - 2, y1), (mid + 2, y0, x1, y1)]
                    roads.append(Road(id=f"r-alley{k}", kind=RoadKind.ALLEY, points=[(mid, y0), (mid, y1)]))
                for sub in halves:
                    for lot in _pack(sub, 11, 13, 3, fill, rng):
                        add(BuildingKind.HOUSE, *lot, _floors(2, 4, density, rng), f"{place} House")
            case "studios":
                for lot in _pack(rect, 16, 22, 4, fill, rng):
                    kind = BuildingKind.MIXED_USE if rng.random() < 0.3 else BuildingKind.STUDIO
                    add(kind, *lot, _floors(5, 14, density, rng), f"{place} Studio")
            case "offices":
                lo, hi = (8, 25) if archetype == TownArchetype.BUSINESS_DISTRICT else (4, 12)
                for lot in _pack(rect, 30, 36, 10, fill + 0.1, rng):
                    add(BuildingKind.OFFICE, *lot, _floors(lo, hi, density, rng), f"{place} Tower")
            case "campus":
                lots = _pack(rect, 40, 22, 18, 0.75, rng)
                for n, lot in enumerate(lots):
                    if n == len(lots) - 1 and rng.random() < 0.4:
                        add(BuildingKind.DORMITORY, *lot, _floors(6, 10, density, rng), "Student Dormitory")
                    else:
                        add(BuildingKind.UNIVERSITY, *lot, _floors(3, 8, density, rng), f"Campus Hall {k}-{n + 1}")
                roads.append(Road(id=f"r-path{k}", kind=RoadKind.FOOTPATH, points=[(x0, y0), (x1, y1)]))
            case "school":
                level = rng.choice(["Elementary", "Middle", "High"])
                add(BuildingKind.SCHOOL, (x0 + x1) / 2, y1 - 15, min(60.0, x1 - x0), min(20.0, y1 - y0), 4,
                    f"{place} {level} School")
            case "park":
                add(BuildingKind.PARK, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, 0, f"{place} Park")
                roads.append(Road(id=f"r-path{k}", kind=RoadKind.FOOTPATH, points=[(x0, y1), (x1, y0)]))
            case "hospital":
                add(BuildingKind.HOSPITAL, (x0 + x1) / 2, (y0 + y1) / 2, min(50.0, x1 - x0), min(40.0, y1 - y0),
                    _floors(6, 12, density, rng), f"{place} Medical Center")
            case "hotels":
                for lot in _pack(rect, 25, 35, 10, fill, rng):
                    kind = BuildingKind.HOTEL if rng.random() < 0.6 else BuildingKind.MIXED_USE
                    add(kind, *lot, _floors(6, 18, density, rng), f"{place} Hotel")
            case None:
                pass

    if _STATION_PASSERSBY[archetype] > 0:
        # Subway entrance at the central arterial crossing.
        add(BuildingKind.STATION, xs[cx_index] + 8, ys[cy_index] + 8, 16, 16, 1, "Central Station")

    venues = _place_venues(spec, buildings, xs, ys, rng, area_scale)
    focal = next(v for v in venues if v.is_focal)
    town_id = f"town-{stable_seed('town-id', spec.model_dump_json()) % 16**10:010x}"
    name = spec.name or f"{archetype.value.replace('_', ' ').title()} Town #{spec.seed}"
    return Town(
        id=town_id, name=name, archetype=archetype, size_m=size, buildings=buildings, venues=venues,
        roads=roads, source="procedural", focal_venue_id=focal.id, spec=spec,
    )


def auto_competitor_count(buildings: list[Building]) -> int:
    """Other convenience stores a town of this population would plausibly have.

    Korea has ~1 store per 950 residents; counting day-time population (workers, students and a
    small share of transit passersby as well) that is roughly one store per 2,000 people.
    """
    people = sum(
        b.residents + 0.7 * b.workers + 0.5 * b.students + 0.03 * b.daily_passersby + 0.2 * b.visitors
        for b in buildings
    )
    return max(2, min(30, round(people / 2000) - 1))


def _place_venues(
    spec: TownSpec,
    buildings: list[Building],
    xs: list[float],
    ys: list[float],
    rng: random.Random,
    area_scale: float,
) -> list[Venue]:
    half = spec.size_m / 2
    hosts = [b for b in buildings if b.kind in _SHOP_HOST_WEIGHT]
    if not hosts:  # degenerate tiny town: put a kiosk at the center
        hosts = [Building(id="b-kiosk", kind=BuildingKind.MIXED_USE, x=half, y=half, width=8, depth=8)]
        buildings.append(hosts[0])

    def door(b: Building) -> tuple[float, float]:
        x, y = _frontage(b.x, b.y, b.width, b.depth, xs, ys)
        return (round(x, 1), round(y, 1))

    def venue(category: VenueCategory, vid: str, name: str, host: Building, attractiveness: float) -> Venue:
        open_hour, close_hour = DEFAULT_OPEN_HOURS[category]
        x, y = door(host)
        return Venue(
            id=vid, name=name, category=category, x=x, y=y, attractiveness=round(attractiveness, 2),
            open_hour=open_hour, close_hour=close_hour, building_id=host.id,
        )

    # Focal store: the shop-capable building closest to the center, preferring street-level retail.
    shop_first = [b for b in hosts if b.kind in (BuildingKind.MIXED_USE, BuildingKind.STUDIO, BuildingKind.OFFICE)]
    focal_host = min(shop_first or hosts, key=lambda b: math.hypot(b.x - half, b.y - half))
    focal = venue(VenueCategory.CONVENIENCE, "v-focal", "Our Store", focal_host, 1.0).model_copy(
        update={"is_focal": True},
    )
    venues: list[Venue] = [focal]

    def dist(a: tuple[float, float], b: Building) -> float:
        return math.hypot(a[0] - b.x, a[1] - b.y)

    # Competitors: weighted by shop-host likelihood, kept apart from each other and from the focal store.
    n_competitors = spec.n_competitors
    if n_competitors is None:
        n_competitors = auto_competitor_count(buildings)
    min_sep = max(60.0, min(250.0, spec.size_m / (2.2 * math.sqrt(n_competitors + 1))))
    stores: list[tuple[float, float]] = [(focal.x, focal.y)]
    weights = [_SHOP_HOST_WEIGHT[b.kind] for b in hosts]
    for n in range(n_competitors):
        sep = min_sep
        host = None
        for attempt in range(300):
            candidate = rng.choices(hosts, weights=weights)[0]
            if all(dist(s, candidate) >= sep for s in stores):
                host = candidate
                break
            if attempt % 50 == 49:
                sep *= 0.75
        host = host or rng.choices(hosts, weights=weights)[0]
        name = _COMPETITOR_NAMES[n % len(_COMPETITOR_NAMES)]
        if n >= len(_COMPETITOR_NAMES):
            name = f"{name} {n // len(_COMPETITOR_NAMES) + 1}"
        v = venue(VenueCategory.CONVENIENCE, f"v-convenience-{n + 1}", name, host, rng.uniform(0.8, 1.25))
        venues.append(v)
        stores.append((v.x, v.y))

    counters: dict[VenueCategory, int] = {}

    def next_id(category: VenueCategory) -> tuple[str, int]:
        counters[category] = counters.get(category, 0) + 1
        return f"v-{category.value}-{counters[category]}", counters[category]

    # Requested neighbors: the closest other shop hosts around the focal store ("next door").
    near = sorted((b for b in hosts if b.id != focal_host.id), key=lambda b: dist((focal.x, focal.y), b))
    for k, category in enumerate(spec.neighbor_categories):
        vid, n = next_id(category)
        host = near[k] if k < len(near) else focal_host
        v = venue(category, vid, f"{_CATEGORY_LABELS[category]} {n}", host, rng.uniform(0.9, 1.2))
        if host.id == focal_host.id:  # same building: next unit along the frontage
            v = v.model_copy(update={"x": round(v.x + 12.0 * (k + 1), 1)})
        venues.append(v)

    # Background venues across town.
    for category, base in _VENUE_COUNTS[spec.archetype].items():
        count = round(base * spec.venue_density * area_scale)
        for _ in range(count):
            vid, n = next_id(category)
            host = rng.choices(hosts, weights=weights)[0]
            venues.append(venue(category, vid, f"{_CATEGORY_LABELS[category]} {n}", host, rng.uniform(0.7, 1.4)))
    return venues


def place_venue(
    town: Town,
    category: VenueCategory,
    x: float,
    y: float,
    *,
    name: str | None = None,
    attractiveness: float = 1.0,
    open_hour: int | None = None,
    close_hour: int | None = None,
    venue_id: str | None = None,
    setup_id: str | None = None,
) -> Town:
    """Return a copy of `town` with a new venue (what-if: "a café opens next door")."""
    existing = {v.id for v in town.venues}
    if venue_id is None:
        n = 1
        while f"v-{category.value}-x{n}" in existing:
            n += 1
        venue_id = f"v-{category.value}-x{n}"
    elif venue_id in existing:
        raise ValueError(f"venue id already exists: {venue_id}")
    default_open, default_close = DEFAULT_OPEN_HOURS[category]
    host = min(town.buildings, key=lambda b: math.hypot(b.x - x, b.y - y), default=None)
    building_id = host.id if host is not None and math.hypot(host.x - x, host.y - y) <= 30 else None
    new = Venue(
        id=venue_id,
        name=name or f"New {_CATEGORY_LABELS[category]}",
        category=category,
        x=x,
        y=y,
        attractiveness=attractiveness,
        open_hour=default_open if open_hour is None else open_hour,
        close_hour=default_close if close_hour is None else close_hour,
        setup_id=setup_id,
        building_id=building_id,
    )
    return town.model_copy(update={"venues": [*town.venues, new]})


def remove_venue(town: Town, venue_id: str) -> Town:
    """Return a copy of `town` without the venue (what-if: "the competitor closes")."""
    if venue_id == town.focal_venue_id:
        raise ValueError("cannot remove the focal venue")
    if town.get_venue(venue_id) is None:
        raise ValueError(f"unknown venue: {venue_id}")
    return town.model_copy(update={"venues": [v for v in town.venues if v.id != venue_id]})
