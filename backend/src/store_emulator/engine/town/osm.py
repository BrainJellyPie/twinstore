"""Real-map import: OpenStreetMap data (Overpass API JSON) → `Town`.

Coordinates are projected equirectangularly around the requested center into the town
frame (x east, y north, meters, origin at the south-west corner of a 2·radius square), which
is accurate to well under 1 % over a few kilometers. OSM has no population data, so people
are estimated from footprint area × levels with floor-area-per-person priors below.

Network helpers (`fetch_overpass`, `geocode`) use the public Overpass / Nominatim services;
respect their usage policies (identify with a User-Agent, keep request rates low).
"""

import json
import logging
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import cast

from store_emulator.domain.town import (
    Building,
    BuildingKind,
    Road,
    RoadKind,
    Town,
    TownArchetype,
    Venue,
    VenueCategory,
)
from store_emulator.domain.types import stable_seed
from store_emulator.engine.town.generator import DEFAULT_OPEN_HOURS

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "parastore/0.3"

_EARTH_RADIUS_M = 6_371_008.8

_BUILDING_TAGS: dict[str, BuildingKind] = {
    "apartments": BuildingKind.APARTMENT,
    "residential": BuildingKind.APARTMENT,  # low-rise "residential" is downgraded to HOUSE below
    "house": BuildingKind.HOUSE,
    "detached": BuildingKind.HOUSE,
    "semidetached_house": BuildingKind.HOUSE,
    "terrace": BuildingKind.HOUSE,
    "bungalow": BuildingKind.HOUSE,
    "dormitory": BuildingKind.DORMITORY,
    "office": BuildingKind.OFFICE,
    "commercial": BuildingKind.MIXED_USE,
    "retail": BuildingKind.MIXED_USE,
    "school": BuildingKind.SCHOOL,
    "kindergarten": BuildingKind.SCHOOL,
    "university": BuildingKind.UNIVERSITY,
    "college": BuildingKind.UNIVERSITY,
    "train_station": BuildingKind.STATION,
    "transportation": BuildingKind.STATION,
    "hospital": BuildingKind.HOSPITAL,
    "hotel": BuildingKind.HOTEL,
}
# Non-building areas (amenity / leisure polygons) that type the buildings inside them.
_AREA_TAGS: dict[tuple[str, str], BuildingKind] = {
    ("amenity", "school"): BuildingKind.SCHOOL,
    ("amenity", "kindergarten"): BuildingKind.SCHOOL,
    ("amenity", "university"): BuildingKind.UNIVERSITY,
    ("amenity", "college"): BuildingKind.UNIVERSITY,
    ("amenity", "hospital"): BuildingKind.HOSPITAL,
    ("tourism", "hotel"): BuildingKind.HOTEL,
}
_VENUE_TAGS: dict[tuple[str, str], VenueCategory] = {
    ("shop", "convenience"): VenueCategory.CONVENIENCE,
    ("shop", "bakery"): VenueCategory.BAKERY,
    ("shop", "pastry"): VenueCategory.BAKERY,
    ("shop", "supermarket"): VenueCategory.SUPERMARKET,
    ("shop", "chemist"): VenueCategory.PHARMACY,
    ("shop", "books"): VenueCategory.BOOKSTORE,
    ("shop", "laundry"): VenueCategory.LAUNDRY,
    ("shop", "dry_cleaning"): VenueCategory.LAUNDRY,
    ("amenity", "cafe"): VenueCategory.CAFE,
    ("amenity", "pharmacy"): VenueCategory.PHARMACY,
    ("amenity", "restaurant"): VenueCategory.RESTAURANT,
    ("amenity", "fast_food"): VenueCategory.FAST_FOOD,
    ("amenity", "bar"): VenueCategory.BAR,
    ("amenity", "pub"): VenueCategory.BAR,
    ("amenity", "bank"): VenueCategory.BANK,
    ("amenity", "internet_cafe"): VenueCategory.PC_ROOM,
    ("amenity", "prep_school"): VenueCategory.ACADEMY,
    ("amenity", "language_school"): VenueCategory.ACADEMY,
    ("amenity", "music_school"): VenueCategory.ACADEMY,
    ("office", "educational_institution"): VenueCategory.ACADEMY,
    ("leisure", "fitness_centre"): VenueCategory.GYM,
}
# Typical floor area of a venue (m²); a mapped footprint scales attractiveness relative to it.
_TYPICAL_VENUE_AREA: dict[VenueCategory, float] = {VenueCategory.CONVENIENCE: 80.0, VenueCategory.SUPERMARKET: 1000.0}

_ROAD_TAGS: dict[str, RoadKind] = {
    **dict.fromkeys(("motorway", "trunk", "primary", "secondary"), RoadKind.ARTERIAL),
    **dict.fromkeys(("tertiary", "residential", "unclassified", "living_street", "road"), RoadKind.STREET),
    **dict.fromkeys(("service", "track"), RoadKind.ALLEY),
    **dict.fromkeys(("footway", "pedestrian", "path", "steps", "cycleway"), RoadKind.FOOTPATH),
}

# Levels assumed when `building:levels` is missing.
_DEFAULT_LEVELS: dict[BuildingKind, int] = {
    BuildingKind.APARTMENT: 12, BuildingKind.HOUSE: 2, BuildingKind.STUDIO: 8, BuildingKind.DORMITORY: 6,
    BuildingKind.OFFICE: 8, BuildingKind.SCHOOL: 4, BuildingKind.UNIVERSITY: 5, BuildingKind.STATION: 1,
    BuildingKind.HOSPITAL: 7, BuildingKind.HOTEL: 10, BuildingKind.PARK: 0, BuildingKind.MIXED_USE: 3,
}

# Daily passersby by station type (weekday boardings + alightings, Seoul-like orders of magnitude).
_STATION_PASSERSBY: dict[str, int] = {"subway": 30_000, "train": 20_000, "light_rail": 10_000, "halt": 3_000}
_BUS_STOP_PASSERSBY = 600
_NODE_FOOTPRINT_M2 = 1_500.0


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value)
        return float(match.group(1)) if match else None
    return None


def _tags(element: dict[str, object]) -> dict[str, str]:
    return {k: v for k, v in _as_dict(element.get("tags")).items() if isinstance(v, str)}


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    twice = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))
    return abs(twice) / 2


def _inside(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _opening_hours(value: str | None, category: VenueCategory) -> tuple[int, int]:
    """Very small `opening_hours` parser: "24/7" or the first "HH:MM-HH:MM" range."""
    if value:
        if "24/7" in value:
            return (0, 24)
        match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", value)
        if match:
            start = int(match.group(1)) % 24
            end = int(match.group(3)) + (1 if match.group(4) != "00" else 0)
            end = end if end <= 24 else end - 24
            return (start, end)
    return DEFAULT_OPEN_HOURS[category]


def _people(kind: BuildingKind, area: float, levels: int) -> dict[str, int]:
    """Population priors from gross floor area (m² per person)."""
    gross = area * max(levels, 1)
    upper = area * max(levels - 1, 0)
    match kind:
        case BuildingKind.APARTMENT:
            return {"residents": min(2000, round(gross / 35))}  # ~85 m² unit for 2.4 persons + common areas
        case BuildingKind.HOUSE:
            return {"residents": min(60, round(gross / 40))}
        case BuildingKind.STUDIO:
            return {"residents": min(1500, round(gross / 22)), "workers": round(gross / 300)}
        case BuildingKind.DORMITORY:
            return {"residents": min(2000, round(gross / 15))}
        case BuildingKind.OFFICE:
            return {"workers": min(3000, round(gross / 25))}
        case BuildingKind.MIXED_USE:
            # Shops on the ground floor, half of the upper floors homes and half offices / clinics.
            return {"workers": min(1500, round(area / 40 + upper * 0.5 / 30)), "residents": round(upper * 0.5 / 40)}
        case BuildingKind.SCHOOL:
            students = min(1500, round(gross / 10))
            return {"students": students, "workers": max(5, students // 14)}
        case BuildingKind.UNIVERSITY:
            return {"students": min(5000, round(gross / 15)), "workers": round(gross / 150)}
        case BuildingKind.STATION:
            return {"daily_passersby": 5_000}
        case BuildingKind.HOSPITAL:
            return {"workers": min(3000, round(gross / 60)), "visitors": min(8000, round(gross / 25))}
        case BuildingKind.HOTEL:
            return {"visitors": min(2000, round(gross / 45)), "workers": round(gross / 300)}
        case BuildingKind.PARK:
            return {"visitors": min(20_000, round(area / 30))}


def _building_kind(tags: dict[str, str], area: float, levels: float | None) -> tuple[BuildingKind, bool]:
    """Kind of a `building=*` way and whether it was a generic guess (may be refined by areas)."""
    value = tags.get("building", "yes")
    for key in ("amenity", "tourism"):
        kind = _AREA_TAGS.get((key, tags.get(key, "")))
        if kind is not None:
            return kind, False
    if value in _BUILDING_TAGS:
        kind = _BUILDING_TAGS[value]
        if value == "residential" and (levels or 0) < 5:
            kind = BuildingKind.HOUSE
        return kind, False
    if "office" in tags:
        return BuildingKind.OFFICE, False
    if area < 250 and (levels or 2) <= 3:
        return BuildingKind.HOUSE, True
    return BuildingKind.MIXED_USE, True


def town_from_overpass(
    data: dict[str, object],
    *,
    center_lat: float,
    center_lon: float,
    radius_m: float,
    focal_name: str | None = None,
) -> Town:
    """Convert Overpass JSON (`out geom` or `out body` + referenced nodes) into a Town.

    The focal store is the convenience store whose name contains `focal_name` (case-insensitive;
    any venue category as a fallback), else the convenience store nearest the center, else a
    synthetic "Our Store" placed at the center.
    """
    cos_lat = math.cos(math.radians(center_lat))

    def project(lat: float, lon: float) -> tuple[float, float]:
        x = radius_m + math.radians(lon - center_lon) * _EARTH_RADIUS_M * cos_lat
        y = radius_m + math.radians(lat - center_lat) * _EARTH_RADIUS_M
        return (round(x, 2), round(y, 2))

    def within(x: float, y: float) -> bool:
        return math.hypot(x - radius_m, y - radius_m) <= radius_m

    elements = [_as_dict(e) for e in _as_list(data.get("elements"))]
    node_coords: dict[int, tuple[float, float]] = {}
    for e in elements:
        lat, lon, ident = _as_float(e.get("lat")), _as_float(e.get("lon")), _as_float(e.get("id"))
        if e.get("type") == "node" and lat is not None and lon is not None and ident is not None:
            node_coords[int(ident)] = project(lat, lon)

    def way_points(e: dict[str, object]) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for g in _as_list(e.get("geometry")):
            lat, lon = _as_float(_as_dict(g).get("lat")), _as_float(_as_dict(g).get("lon"))
            if lat is not None and lon is not None:
                points.append(project(lat, lon))
        if not points:
            for ref in _as_list(e.get("nodes")):
                ident = _as_float(ref)
                if ident is not None and int(ident) in node_coords:
                    points.append(node_coords[int(ident)])
        if not points:
            center = _as_dict(e.get("center"))
            lat, lon = _as_float(center.get("lat")), _as_float(center.get("lon"))
            if lat is not None and lon is not None:
                points.append(project(lat, lon))
        if len(points) > 1 and points[0] == points[-1]:
            points = points[:-1]  # closed ring
        return points

    def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
        return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))

    buildings: list[Building] = []
    generic: set[str] = set()  # building ids whose kind was guessed
    areas: list[tuple[BuildingKind, list[tuple[float, float]], str]] = []
    venues: list[Venue] = []
    roads: list[Road] = []
    stations: list[tuple[str, float, float]] = []

    def add_building(
        kind: BuildingKind, points: list[tuple[float, float]], levels: int, name: str, people: dict[str, int],
    ) -> Building:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        cx, cy = centroid(points)
        building = Building(
            id=f"b{len(buildings):04d}", kind=kind, name=name, x=round(cx, 1), y=round(cy, 1),
            width=round(max(max(xs) - min(xs), 4.0), 1), depth=round(max(max(ys) - min(ys), 4.0), 1),
            floors=levels, residents=people.get("residents", 0), workers=people.get("workers", 0),
            students=people.get("students", 0), daily_passersby=people.get("daily_passersby", 0),
            visitors=people.get("visitors", 0),
        )
        buildings.append(building)
        return building

    def add_venue(category: VenueCategory, tags: dict[str, str], x: float, y: float, area: float) -> None:
        open_hour, close_hour = _opening_hours(tags.get("opening_hours"), category)
        typical = _TYPICAL_VENUE_AREA.get(category)
        attractiveness = min(3.0, max(0.5, math.sqrt(area / typical))) if typical and area > 0 else 1.0
        n = sum(1 for v in venues if v.category == category) + 1
        name = tags.get("name:en") or tags.get("name") or tags.get("brand") or f"{category.value.replace('_', ' ')} {n}"
        venues.append(Venue(
            id=f"v-{category.value}-{n}", name=name, category=category, x=round(x, 1), y=round(y, 1),
            attractiveness=round(attractiveness, 2), open_hour=open_hour, close_hour=close_hour,
        ))

    for e in elements:
        tags = _tags(e)
        if not tags:
            continue
        kind_of_element = e.get("type")
        if kind_of_element == "node":
            ident = _as_float(e.get("id"))
            point = node_coords.get(int(ident)) if ident is not None else None
            points = [point] if point is not None else []
        elif kind_of_element == "way":
            points = way_points(e)
        else:
            continue
        if not points:
            continue
        cx, cy = centroid(points)
        area = _polygon_area(points) if kind_of_element == "way" else 0.0

        highway = tags.get("highway", "")
        if kind_of_element == "way" and highway in _ROAD_TAGS and "building" not in tags:
            if any(within(x, y) for x, y in points):
                roads.append(Road(
                    id=f"r{len(roads):04d}", kind=_ROAD_TAGS[highway], points=points, name=tags.get("name", ""),
                ))
            continue
        if not within(cx, cy):
            continue

        category = next((c for (k, v), c in _VENUE_TAGS.items() if tags.get(k) == v), None)
        if category is not None:
            add_venue(category, tags, cx, cy, area)
            if "building" not in tags:
                continue

        if "building" in tags and kind_of_element == "way" and area > 0:
            levels_tag = _as_float(tags.get("building:levels"))
            kind, guessed = _building_kind(tags, area, levels_tag)
            levels = round(levels_tag) if levels_tag is not None else _DEFAULT_LEVELS[kind]
            people = _people(kind, area, levels)
            if kind == BuildingKind.STATION:
                people = {"daily_passersby": _STATION_PASSERSBY.get(tags.get("station", ""), 5_000)}
            building = add_building(kind, points, levels, tags.get("name", ""), people)
            if guessed:
                generic.add(building.id)
            continue

        if kind_of_element == "way" and tags.get("leisure") == "park" and area > 0:
            add_building(BuildingKind.PARK, points, 0, tags.get("name", ""), _people(BuildingKind.PARK, area, 0))
            continue
        area_kind = next((k for (key, value), k in _AREA_TAGS.items() if tags.get(key) == value), None)
        if kind_of_element == "way" and area_kind is not None and area > 0:
            areas.append((area_kind, points, tags.get("name", "")))
            continue
        if kind_of_element == "node" and area_kind is not None:
            # A school / hospital mapped as a single point: assume a 1,500 m² footprint.
            side = math.sqrt(_NODE_FOOTPRINT_M2)
            levels = _DEFAULT_LEVELS[area_kind]
            add_building(area_kind, [(cx - side / 2, cy - side / 2), (cx + side / 2, cy + side / 2)], levels,
                         tags.get("name", ""), _people(area_kind, _NODE_FOOTPRINT_M2, levels))
            continue

        railway, transport = tags.get("railway", ""), tags.get("public_transport", "")
        if railway in ("station", "halt") or transport == "station":
            station_type = "halt" if railway == "halt" else tags.get("station", "subway" if "subway" in tags else "train")
            name = tags.get("name", "Station")
            if any(math.hypot(x - cx, y - cy) < (300 if n == name else 60) for n, x, y in stations):
                continue  # the same station mapped twice (railway + public_transport nodes)
            stations.append((name, cx, cy))
            add_building(BuildingKind.STATION, [(cx, cy)], 1, tags.get("name", "Station"),
                         {"daily_passersby": _STATION_PASSERSBY.get(station_type, _STATION_PASSERSBY["train"])})
        elif highway == "bus_stop":
            add_building(BuildingKind.STATION, [(cx, cy)], 0, tags.get("name", "Bus stop"),
                         {"daily_passersby": _BUS_STOP_PASSERSBY})

    # Typed areas (school grounds, campuses, hospital sites) refine guessed buildings inside them.
    for area_kind, polygon, name in areas:
        inside = [i for i, b in enumerate(buildings) if _inside(b.x, b.y, polygon)]
        for i in inside:
            b = buildings[i]
            if b.id in generic:
                levels = b.floors or _DEFAULT_LEVELS[area_kind]
                people = _people(area_kind, b.width * b.depth * 0.8, levels)
                buildings[i] = b.model_copy(update={
                    "kind": area_kind, "name": b.name or name, "residents": people.get("residents", 0),
                    "workers": people.get("workers", 0), "students": people.get("students", 0),
                    "visitors": people.get("visitors", 0),
                })
        if not inside:
            footprint = _polygon_area(polygon) * 0.25  # unmapped buildings cover ~a quarter of the site
            side = math.sqrt(footprint)
            cx, cy = centroid(polygon)
            levels = _DEFAULT_LEVELS[area_kind]
            add_building(area_kind, [(cx - side / 2, cy - side / 2), (cx + side / 2, cy + side / 2)], levels, name,
                         _people(area_kind, footprint, levels))

    focal = _pick_focal(venues, focal_name, radius_m)
    if focal is None:
        open_hour, close_hour = DEFAULT_OPEN_HOURS[VenueCategory.CONVENIENCE]
        focal = Venue(
            id="v-focal", name="Our Store", category=VenueCategory.CONVENIENCE, x=radius_m, y=radius_m,
            open_hour=open_hour, close_hour=close_hour,
        )
        venues.insert(0, focal)
    focal_id = focal.id
    venues = [v.model_copy(update={"is_focal": v.id == focal_id}) for v in venues]
    venues = [_attach_building(v, buildings) for v in venues]

    town_id = f"osm-{stable_seed('osm', f'{center_lat:.5f}', f'{center_lon:.5f}', round(radius_m)) % 16**10:010x}"
    return Town(
        id=town_id,
        name=f"Around {focal.name}" if focal.name != "Our Store" else f"OSM {center_lat:.4f}, {center_lon:.4f}",
        archetype=_infer_archetype(buildings, radius_m),
        size_m=2 * radius_m,
        buildings=buildings,
        venues=venues,
        roads=roads,
        source="osm",
        center_lat=center_lat,
        center_lon=center_lon,
        focal_venue_id=focal_id,
    )


def _pick_focal(venues: list[Venue], focal_name: str | None, radius_m: float) -> Venue | None:
    stores = [v for v in venues if v.category == VenueCategory.CONVENIENCE]
    if focal_name:
        needle = focal_name.casefold()
        for group in (stores, venues):
            match = next((v for v in group if needle in v.name.casefold()), None)
            if match is not None:
                return match
        logger.warning(f"[town] no venue named like {focal_name!r}; using the store nearest the center")
    return min(stores, key=lambda v: math.hypot(v.x - radius_m, v.y - radius_m), default=None)


def _attach_building(venue: Venue, buildings: list[Building]) -> Venue:
    host = min(buildings, key=lambda b: math.hypot(b.x - venue.x, b.y - venue.y), default=None)
    if host is None or math.hypot(host.x - venue.x, host.y - venue.y) > max(host.width, host.depth) / 2 + 10:
        return venue
    return venue.model_copy(update={"building_id": host.id})


def _infer_archetype(buildings: list[Building], radius_m: float) -> TownArchetype:
    residents = sum(b.residents for b in buildings)
    workers = sum(b.workers for b in buildings)
    students = sum(b.students for b in buildings)
    passersby = sum(b.daily_passersby for b in buildings)
    hotel_guests = sum(b.visitors for b in buildings if b.kind == BuildingKind.HOTEL)
    area_km2 = math.pi * (radius_m / 1000) ** 2
    if any(b.kind == BuildingKind.UNIVERSITY for b in buildings) and students > 0.6 * max(residents, 1):
        return TownArchetype.UNIVERSITY
    if workers > 1.5 * max(residents, 1):
        return TownArchetype.BUSINESS_DISTRICT
    if hotel_guests > 0.3 * max(residents, 1):
        return TownArchetype.TOURIST
    if passersby > 1.5 * (residents + workers):
        return TownArchetype.STATION_AREA
    if residents / area_km2 < 5_000:
        return TownArchetype.SUBURBAN
    if workers > 0.6 * residents:
        return TownArchetype.MIXED
    return TownArchetype.RESIDENTIAL


def build_overpass_query(lat: float, lon: float, radius_m: float, timeout: int = 60) -> str:
    around = f"(around:{round(radius_m)},{lat:.6f},{lon:.6f})"
    selectors = [
        'way["building"]', 'way["highway"]', 'way["leisure"="park"]',
        'way["amenity"~"^(school|kindergarten|university|college|hospital)$"]', 'way["tourism"="hotel"]',
        'node["shop"]', 'way["shop"]', 'node["amenity"]',
        'way["amenity"~"^(cafe|restaurant|fast_food|pharmacy|bank|bar|pub|prep_school)$"]',
        'node["leisure"="fitness_centre"]', 'way["leisure"="fitness_centre"]',
        'node["office"="educational_institution"]', 'node["railway"~"^(station|halt)$"]',
        'node["public_transport"="station"]', 'node["highway"="bus_stop"]',
    ]
    body = "\n".join(f"  {s}{around};" for s in selectors)
    return f"[out:json][timeout:{timeout}];\n(\n{body}\n);\nout geom;"


def fetch_overpass(lat: float, lon: float, radius_m: float, timeout: int = 60) -> dict[str, object]:
    """Download buildings, roads, shops and stations around a point from the Overpass API.

    Raises RuntimeError when the service cannot be reached or answers with something other
    than a JSON object.
    """
    payload = urllib.parse.urlencode({"data": build_overpass_query(lat, lon, radius_m, timeout)}).encode()
    request = urllib.request.Request(OVERPASS_URL, data=payload, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout + 10) as response:
            body: bytes = response.read()
        parsed: object = json.loads(body.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise RuntimeError(f"Overpass request failed: {e}") from e
    result = _as_dict(parsed)
    if not result:
        raise RuntimeError("Overpass returned an empty or non-object JSON payload")
    return result


def geocode(address: str, timeout: int = 20) -> tuple[float, float] | None:
    """(lat, lon) of an address via Nominatim, or None when not found / unreachable."""
    query = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    request = urllib.request.Request(f"{NOMINATIM_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body: bytes = response.read()
        parsed: object = json.loads(body.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        logger.warning(f"[town] geocoding failed for {address!r}: {e}")
        return None
    results = _as_list(parsed)
    if not results:
        return None
    first = _as_dict(results[0])
    lat, lon = _as_float(first.get("lat")), _as_float(first.get("lon"))
    return (lat, lon) if lat is not None and lon is not None else None
