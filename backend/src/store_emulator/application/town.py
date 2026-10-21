"""Project neighborhoods: storage, generation / OSM import, what-if edits, demand, synergy, visitors."""

import logging
from pathlib import Path

from filelock import FileLock, Timeout

from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import Scenario
from store_emulator.domain.town import (
    DayType,
    SynergyRow,
    Town,
    TownArrival,
    TownDemand,
    TownSpec,
    VenueCategory,
)
from store_emulator.domain.types import Weekday, stable_seed
from store_emulator.engine.scenario import compile_scenario
from store_emulator.engine.town import (
    day_type_for,
    estimate_demand,
    fetch_overpass,
    generate_town,
    geocode,
    place_venue,
    plan_arrivals,
    remove_venue,
    synergy_analysis,
    town_context_text,
    town_from_overpass,
)

from .errors import AppError
from .storage.io import DATA_DIR, read_json, write_json

logger = logging.getLogger(__name__)


def _town_path(pid: str) -> Path:
    return Path(DATA_DIR) / pid / "town.json"


def get_town(pid: str) -> Town | None:
    path = _town_path(pid)
    if not path.exists():
        return None
    return Town.model_validate(read_json(path))


def require_town(pid: str) -> Town:
    town = get_town(pid)
    if town is None:
        raise AppError("this project has no neighborhood yet — generate one or import a real map first", 404)
    return town


def save_town(pid: str, town: Town, *, expected: Town | None = None) -> Town:
    path = _town_path(pid)
    if not path.parent.is_dir():
        raise AppError(f"project not found: {pid}", 404)
    if town.size_m <= 0:
        raise AppError("Neighborhood size must be positive", 422)
    for label, items in [("venue", town.venues), ("building", town.buildings), ("road", town.roads)]:
        ids = [item.id for item in items]
        if any(not identifier.strip() for identifier in ids) or len(set(ids)) != len(ids):
            raise AppError(f"Neighborhood {label} IDs must be nonempty and unique", 422)
    if town.get_venue(town.focal_venue_id) is None:
        raise AppError("The neighborhood must contain its focal venue", 422)
    try:
        with FileLock(path.with_suffix(".lock"), timeout=0):
            if expected is not None and get_town(pid) != expected:
                raise AppError("Neighborhood changed while this action was running; reload it and try again", 409)
            write_json(path, town.model_dump(mode="json"))
    except Timeout as exc:
        raise AppError("Another neighborhood update is in progress; try again", 409) from exc
    return town


def generate(pid: str, spec: TownSpec, *, store_name: str = "") -> Town:
    town = generate_town(spec if spec.name or not store_name else spec.model_copy(update={"name": f"{store_name} area"}))
    return save_town(pid, town)


def import_osm(
    pid: str, *, address: str | None, lat: float | None, lon: float | None, radius_m: float, focal_name: str | None,
) -> Town:
    if lat is None or lon is None:
        if not address:
            raise AppError("give an address or lat/lon", 400)
        point = geocode(address)
        if point is None:
            raise AppError(f"could not find '{address}' on OpenStreetMap (or the map service is unreachable)", 502)
        lat, lon = point
    try:
        data = fetch_overpass(lat, lon, radius_m)
    except RuntimeError as e:
        raise AppError(f"OpenStreetMap download failed: {e}", 502) from e
    town = town_from_overpass(data, center_lat=lat, center_lon=lon, radius_m=radius_m, focal_name=focal_name)
    return save_town(pid, town)


def add_venue(pid: str, category: VenueCategory, x: float, y: float, name: str = "") -> Town:
    town = require_town(pid)
    return save_town(pid, place_venue(town, category, x, y, name=name or None), expected=town)


def delete_venue(pid: str, venue_id: str) -> Town:
    town = require_town(pid)
    try:
        return save_town(pid, remove_venue(town, venue_id), expected=town)
    except ValueError as e:
        raise AppError(str(e), 400) from e


def _scenario_traffic(scenario: Scenario | None) -> tuple[float, dict[int, float] | None]:
    if scenario is None:
        return 1.0, None
    fx = compile_scenario(scenario)
    return fx.base_traffic, (fx.traffic_by_hour or None)


def demand(pid: str, day_type: DayType = "weekday", scenario: Scenario | None = None) -> TownDemand:
    traffic, hourly = _scenario_traffic(scenario)
    return estimate_demand(require_town(pid), day_type=day_type, traffic_multiplier=traffic, hourly_multiplier=hourly)


def synergy(pid: str, day_type: DayType = "weekday") -> list[SynergyRow]:
    return synergy_analysis(require_town(pid), day_type=day_type)


def town_visitors(
    town: Town, pool: list[Persona], *, seed: int, scale: float, scenario: Scenario | None,
) -> tuple[list[Persona], list[TownArrival]]:
    """Visitors for every simulated weekday of the pool, drawn from the neighborhood demand.

    Each visitor is a clone of a pool persona (matching age and hour) whose description gains
    one line about where they came from, so LLM/VLM shoppers know it ("walked 320 m from an
    apartment block; came straight from the café next door").
    """
    traffic, hourly = _scenario_traffic(scenario)
    visitors: list[Persona] = []
    arrivals: list[TownArrival] = []
    days = sorted({p.day for p in pool}) or [Weekday.MON]
    for day in days:
        day_demand = estimate_demand(town, day_type=day_type_for(day), traffic_multiplier=traffic, hourly_multiplier=hourly)
        people, notes = plan_arrivals(pool, day_demand, town, seed=stable_seed(seed, "town", int(day)), scale=scale, day=day)
        for person, note in zip(people, notes, strict=True):
            context = town_context_text(note, town)
            visitors.append(person.model_copy(update={"description": f"{person.description} {context}".strip()}))
            arrivals.append(note)
    logger.info(f"[town] {len(visitors)} visitors over {len(days)} day(s) from '{town.name}' (scale {scale})")
    return visitors, arrivals
