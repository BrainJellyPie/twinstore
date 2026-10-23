"""Project neighborhoods: storage, generation / OSM import, what-if edits, demand, synergy, visitors."""

import logging
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import DayType as ScenarioDayType
from store_emulator.domain.scenario import Scenario, ScenarioPriors
from store_emulator.domain.store import Store
from store_emulator.domain.town import (
    DayType,
    SynergyRow,
    Town,
    TownArrival,
    TownDemand,
    TownSpec,
    VenueCategory,
)
from store_emulator.domain.types import RESOURCE_ID_PATTERN, Weekday, stable_seed
from store_emulator.engine.town import (
    TYPICAL_DAY,
    day_type_for,
    estimate_demand,
    fetch_overpass,
    generate_town,
    geocode,
    place_venue,
    plan_arrivals,
    remove_venue,
    scenario_traffic,
    synergy_analysis,
    town_context_writer,
    town_from_overpass,
    with_store_hours,
)

from .errors import AppError
from .setups import setup_tree_transaction
from .storage.io import DATA_DIR, read_json, write_json
from .storage.setups import read_setup, read_state

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


def town_for_run(pid: str) -> Town:
    """The neighborhood a run with neighborhood visitors draws them from (409 without one)."""
    town = get_town(pid)
    if town is None:
        raise AppError("This project has no neighborhood yet — generate one or import a map on the Area page, or "
                       "turn off neighborhood visitors.", 409)
    return town


def save_town(pid: str, town: Town, *, expected: Town | None = None) -> Town:
    with town_write_transaction(pid, expected=expected) as commit:
        return commit(town)


@contextmanager
def town_write_transaction(pid: str, *, expected: Town | None = None) -> Iterator[Callable[[Town], Town]]:
    """Yield a validated town writer while holding project and neighborhood locks.

    Related adjustment baselines can be read and written inside the same boundary.
    """
    path = _town_path(pid)

    def commit(town: Town) -> Town:
        if town.size_m <= 0:
            raise AppError("Neighborhood size must be positive", 422)
        for label, coordinate, limit in [("latitude", town.center_lat, 90), ("longitude", town.center_lon, 180)]:
            if coordinate is not None and not -limit <= coordinate <= limit:
                raise AppError(f"Neighborhood center {label} must be between {-limit} and {limit}", 422)
        for label, items in [("venue", town.venues), ("building", town.buildings), ("road", town.roads)]:
            ids = [item.id for item in items]
            if any(not identifier.strip() for identifier in ids) or len(set(ids)) != len(ids):
                raise AppError(f"Neighborhood {label} IDs must be nonempty and unique", 422)
        if town.get_venue(town.focal_venue_id) is None:
            raise AppError("The neighborhood must contain its focal venue", 422)
        write_json(path, town.model_dump(mode="json"))
        return town

    try:
        with setup_tree_transaction(pid):
            with FileLock(path.with_suffix(".lock"), timeout=0):
                if expected is not None and get_town(pid) != expected:
                    raise AppError("Neighborhood changed while this action was running; reload it and try again", 409)
                yield commit
    except Timeout as exc:
        raise AppError("Another neighborhood update is in progress; try again", 409) from exc


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


def _layout_store(pid: str, town: Town) -> Store | None:
    """The layout the neighborhood panel describes: the project's active layout, else the one our venue maps to
    (None without a usable one)."""
    setup_id = read_state(pid).get("activeSetupId")
    if not isinstance(setup_id, str) or not setup_id:
        focal = town.get_venue(town.focal_venue_id)
        setup_id = focal.setup_id if focal is not None else None
    if not setup_id or not re.fullmatch(RESOURCE_ID_PATTERN, setup_id):
        return None
    try:
        data = read_setup(pid, setup_id).get("store")
        return Store.model_validate(data) if data else None
    except (FileNotFoundError, ValueError):
        return None


def demand(
    pid: str, day_type: DayType = "weekday", scenario: Scenario | None = None, *,
    scenario_priors: ScenarioPriors | None = None,
) -> TownDemand:
    """Our store's visitors on a day of `day_type`, in the hours the active layout opens on such a day."""
    town = require_town(pid)
    store = _layout_store(pid, town)
    traffic, hourly = scenario_traffic(scenario, store, scenario_priors, profile=day_type)
    town, hours = with_store_hours(town, store, TYPICAL_DAY[day_type])
    return estimate_demand(town, day_type=day_type, hours=hours, traffic_multiplier=traffic, hourly_multiplier=hourly)


def synergy(pid: str, day_type: DayType = "weekday") -> list[SynergyRow]:
    town = require_town(pid)
    town, hours = with_store_hours(town, _layout_store(pid, town), TYPICAL_DAY[day_type])
    return synergy_analysis(town, day_type=day_type, hours=hours)


def _day_type(day: Weekday, scenario: Scenario | None) -> DayType:
    """The neighborhood's day type for a simulated day: the scenario's holiday or weekend, else the weekday's."""
    kind = scenario.day_type if scenario is not None else ScenarioDayType.WEEKDAY
    if kind == ScenarioDayType.WEEKEND:
        return "weekend"
    return day_type_for(day, holiday=kind in (ScenarioDayType.PUBLIC_HOLIDAY, ScenarioDayType.HOLIDAY_SEASON))


def town_visitors(
    town: Town, pool: list[Persona], *, seed: int, scale: float, scenario: Scenario | None, store: Store | None,
    scenario_priors: ScenarioPriors | None = None,
) -> tuple[list[Persona], list[TownArrival]]:
    """Visitors for every simulated weekday of the pool, drawn from the neighborhood demand in the hours the
    store's layout opens that day, under the scenario's traffic (with the store format's effect sizes, or the
    calibrated `scenario_priors`) and day type.

    Each visitor is a clone of a pool persona (matching age and hour) whose description gains
    one line about where they came from, so LLM/VLM shoppers know it ("walked 320 m from an
    apartment block; came straight from the café next door").
    """
    visitors: list[Persona] = []
    arrivals: list[TownArrival] = []
    describe = town_context_writer(town)
    days = sorted({p.day for p in pool}) or [Weekday.MON]
    for day in days:
        town_day, hours = with_store_hours(town, store, day)
        profile = _day_type(day, scenario)
        traffic, hourly = scenario_traffic(scenario, store, scenario_priors, profile=profile)
        day_demand = estimate_demand(town_day, day_type=profile, hours=hours,
                                     traffic_multiplier=traffic, hourly_multiplier=hourly)
        people, notes = plan_arrivals(pool, day_demand, town_day, seed=stable_seed(seed, "town", int(day)), scale=scale,
                                      day=day)
        for person, note in zip(people, notes, strict=True):
            context = describe(note)
            visitors.append(person.model_copy(update={"description": f"{person.description} {context}".strip()}))
            arrivals.append(note)
    logger.info(f"[town] {len(visitors)} visitors over {len(days)} day(s) from '{town.name}' (scale {scale})")
    return visitors, arrivals


_SEGMENT_WORDS = {"resident": "residents", "worker": "office workers", "student": "students", "commuter": "commuters",
                  "visitor": "visitors from outside", "linked": "people coming from a nearby venue"}


def neighborhood_text(pid: str) -> str:
    """The neighborhood model in a few sentences for the persona prompt ("" without a town): who comes on a weekday
    and at the weekend, when, and from how far."""
    town = get_town(pid)
    if town is None:
        return ""
    parts: list[str] = []
    days: tuple[tuple[DayType, str], ...] = (("weekday", "a weekday"), ("weekend", "a weekend day"))
    for day_type, label in days:
        d = estimate_demand(town, day_type=day_type)
        total = sum(d.segment_totals.values()) or 1.0
        mix = ", ".join(f"{_SEGMENT_WORDS.get(k, k)} {v / total:.0%}"
                        for k, v in sorted(d.segment_totals.items(), key=lambda kv: -kv[1]) if v / total >= 0.03)
        peaks = sorted(range(24), key=lambda h: -d.hourly_totals[h])[:3]
        parts.append(f"On {label} about {d.total_daily_visitors:.0f} visitors: {mix}; busiest hours "
                     f"{', '.join(f'{h:02d}h' for h in sorted(peaks))}.")
    walk = estimate_demand(town, day_type="weekday")
    return (f"Neighborhood model ({town.archetype.value.replace('_', ' ')} area, {town.name}): " + " ".join(parts)
            + f" Half of the visitors walk less than {walk.catchment_radius_50_m:.0f} m. "
            "Make the personas' identities, ages, purposes and visit hours match this mix.")
