"""Multi-store convenience demand for a town (Huff gravity model with an outside option).

Pipeline for one day:

1. Presence. Every building contributes origin groups per segment (residents, workers,
   students, transit commuters, visitors). A 24-hour exposure profile per segment and day
   type gives how much of the group is around in each hour: for residents / workers /
   students it is the fraction present (0–1); for commuters and visitors, whose counts are
   daily flows, it is the fraction of the daily flow passing in that hour.
2. Trip generation. need[g, h, a] = people × exposure[h] × trip_rate[segment] ×
   hour_propensity[h] × age_mix[a] × age_propensity[a] — the expected number of people who
   want a convenience-store run that hour (~1–4 % per present person-hour).
3. Destination choice (Huff). Among open convenience stores (plus weighted substitutes such
   as supermarkets), U_j = w_j · A_j^alpha · exp(-beta · d_ij), with d the walking distance
   (straight line × detour factor). An outside option U_0 = exp(-beta · outside_option_m)
   stands for "skip it / buy elsewhere", so a far-away store does not win trips it would
   never get: P(j | i) = U_j / (U_0 + Σ_k U_k).
4. Linked trips (synergy). Complementary venues (café, gym, academy, …) get their own
   visitors from the same population with a category Huff model. A visitor of venue v then
   chains to a convenience store with probability synergy[category] × min(1, Σ_j L_vj),
   L_vj = A_j^alpha · exp(-d_vj / link_decay_m), split among stores in proportion to L_vj —
   so a store at the café's door gets the full synergy rate and a competitor next to the
   café takes its share.

All priors live in `DemandParams` so they can be calibrated against POS / footfall data.
They are uncalibrated, literature- and intuition-based starting points:

- Korea has ~55k convenience stores averaging roughly 300–600 customers/day, i.e. ~0.4
  store visits per person per day; residents near home make ~0.2–0.3 of those.
- Walking catchments of convenience stores are short (most customers within 250–400 m) and
  a new store next door typically costs an existing one 20–30 % of its customers;
  beta = 7 /km (utility halves every ~100 m walked) reproduces both reasonably well.
- Huff shares have the IIA property: a new store draws from every store in proportion to
  its share at each origin, so spatial competition only comes through the distance decay.
- A detour factor of ~1.3 is the usual ratio of network to straight-line walking distance.
"""

import copy
import math
from collections.abc import Iterable

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field

from store_emulator.domain.persona import AGE_GROUPS, AgeGroup
from store_emulator.domain.scenario import DayType as ScenarioDayType
from store_emulator.domain.scenario import Scenario, ScenarioPriors
from store_emulator.domain.store import Store
from store_emulator.domain.town import (
    TOWN_SEGMENTS,
    BuildingKind,
    DayType,
    HourlySegmentDemand,
    LinkedTrip,
    OriginShare,
    StoreShare,
    SynergyRow,
    Town,
    TownDemand,
    TownSegment,
    Venue,
    VenueCategory,
)
from store_emulator.domain.types import Weekday
from store_emulator.engine.scenario import compile_scenario, priors_for

type FloatArray = npt.NDArray[np.float64]


def _hours(values: dict[int, float], default: float = 0.0, scale: float = 1.0) -> list[float]:
    return [round(values.get(h, default) * scale, 5) for h in range(24)]


def _span(start: int, end: int, value: float) -> dict[int, float]:
    return {h: value for h in range(start, end)}


# ---------------------------------------------------------------- default priors

# Exposure profiles (index = hour). Keys are "segment" or "segment:building_kind".
_RESIDENT_WEEKDAY = {
    0: 0.25, 1: 0.12, 2: 0.06, 3: 0.04, 4: 0.04, 5: 0.08, 6: 0.35, 7: 0.6, 8: 0.55, 9: 0.45, 10: 0.42, 11: 0.42,
    12: 0.45, 13: 0.42, 14: 0.4, 15: 0.42, 16: 0.45, 17: 0.55, 18: 0.68, 19: 0.75, 20: 0.78, 21: 0.75, 22: 0.6,
    23: 0.4,
}
_RESIDENT_WEEKEND = {
    0: 0.35, 1: 0.2, 2: 0.1, 3: 0.05, 4: 0.04, 5: 0.05, 6: 0.15, 7: 0.3, 8: 0.5, 9: 0.65, 10: 0.72, 11: 0.72,
    12: 0.7, 13: 0.65, 14: 0.6, 15: 0.6, 16: 0.62, 17: 0.65, 18: 0.7, 19: 0.75, 20: 0.78, 21: 0.75, 22: 0.62,
    23: 0.45,
}
_WORKER_WEEKDAY = {
    **_span(0, 7, 0.02), 7: 0.15, 8: 0.55, 9: 0.9, **_span(10, 16, 0.95), 16: 0.92, 17: 0.8, 18: 0.5, 19: 0.3,
    20: 0.18, 21: 0.1, 22: 0.06, 23: 0.03,
}
_SCHOOL_WEEKDAY = {7: 0.3, 8: 0.95, **_span(9, 15, 1.0), 15: 0.85, 16: 0.5, 17: 0.25, 18: 0.12, 19: 0.06}
_UNIVERSITY_WEEKDAY = {
    8: 0.15, 9: 0.55, 10: 0.8, **_span(11, 15, 0.85), 15: 0.8, 16: 0.7, 17: 0.55, 18: 0.4, 19: 0.3, 20: 0.25,
    21: 0.2, 22: 0.12, 23: 0.06,
}
# Share of a station's daily passersby per hour (weekday sums to 1, weekend to ~0.7).
_COMMUTER_WEEKDAY = {
    0: 0.01, 5: 0.01, 6: 0.03, 7: 0.085, 8: 0.125, 9: 0.065, 10: 0.04, 11: 0.04, 12: 0.045, 13: 0.045, 14: 0.04,
    15: 0.04, 16: 0.045, 17: 0.065, 18: 0.105, 19: 0.075, 20: 0.05, 21: 0.04, 22: 0.035, 23: 0.025,
}
_COMMUTER_WEEKEND = {
    0: 0.015, 6: 0.01, 7: 0.02, 8: 0.03, 9: 0.04, 10: 0.05, 11: 0.055, 12: 0.055, 13: 0.055, 14: 0.055, 15: 0.055,
    16: 0.055, 17: 0.055, 18: 0.05, 19: 0.045, 20: 0.04, 21: 0.035, 22: 0.03, 23: 0.02,
}
# Hotel guests: fraction around the hotel (out sightseeing during the day).
_HOTEL_WEEKDAY = {
    0: 0.3, 7: 0.6, 8: 0.6, 9: 0.4, **_span(10, 18, 0.25), 18: 0.35, 19: 0.45, 20: 0.55, 21: 0.65, 22: 0.6,
    23: 0.5,
}
# Hospital outpatients / visitors: hourly share of the daily flow × ~1.4 h stay.
_HOSPITAL_WEEKDAY = {
    8: 0.06, 9: 0.14, 10: 0.16, 11: 0.15, 12: 0.08, 13: 0.12, 14: 0.14, 15: 0.13, 16: 0.11, 17: 0.07, 18: 0.05,
    19: 0.06, 20: 0.05, 21: 0.03,
}
# Park visitors: hourly share of the daily flow × ~1.6 h stay.
_PARK_WEEKDAY = {
    6: 0.04, 7: 0.06, 8: 0.05, 9: 0.06, 10: 0.08, 11: 0.09, 12: 0.09, 13: 0.1, 14: 0.11, **_span(15, 20, 0.12),
    20: 0.1, 21: 0.07, 22: 0.03,
}

_EXPOSURE: dict[str, dict[str, list[float]]] = {
    "resident": {"weekday": _hours(_RESIDENT_WEEKDAY), "weekend": _hours(_RESIDENT_WEEKEND)},
    "worker": {"weekday": _hours(_WORKER_WEEKDAY), "weekend": _hours(_WORKER_WEEKDAY, scale=0.12)},
    "student": {"weekday": _hours(_SCHOOL_WEEKDAY), "weekend": _hours(_SCHOOL_WEEKDAY, scale=0.05)},
    "student:university": {"weekday": _hours(_UNIVERSITY_WEEKDAY), "weekend": _hours(_UNIVERSITY_WEEKDAY, scale=0.2)},
    "commuter": {"weekday": _hours(_COMMUTER_WEEKDAY), "weekend": _hours(_COMMUTER_WEEKEND)},
    "visitor": {"weekday": _hours(_HOSPITAL_WEEKDAY), "weekend": _hours(_HOSPITAL_WEEKDAY, scale=0.4)},
    "visitor:hotel": {"weekday": _hours(_HOTEL_WEEKDAY), "weekend": _hours(_HOTEL_WEEKDAY, scale=1.1)},
    "visitor:park": {"weekday": _hours(_PARK_WEEKDAY), "weekend": _hours(_PARK_WEEKDAY, scale=1.7)},
}

# Convenience-store trips per present person-hour (per passing commuter / visitor-hour).
_TRIP_RATE: dict[str, float] = {
    "resident": 0.03,  # ~0.3 wanted runs/day at home; ~0.2 realized after the outside option
    "worker": 0.028,  # coffee, lunch, afternoon snack near the office
    "student": 0.03,  # before / after school, between classes
    "commuter": 0.035,  # share of passersby who pop in on the way
    "visitor": 0.03,  # drinks / snacks for patients, park-goers, hotel guests
}

# Hour-of-day multipliers on the trip rate (missing hours = 1).
_PROPENSITY: dict[str, list[float]] = {
    "resident": _hours({0: 1.3, 1: 1.2, 7: 1.2, 8: 1.15, 12: 1.1, 18: 1.2, 19: 1.25, 20: 1.3, 21: 1.4, 22: 1.5,
                        23: 1.5}, default=1.0),
    "worker": _hours({7: 1.3, 8: 1.6, 9: 1.2, 12: 1.8, 13: 1.5, 15: 1.25, 18: 1.3, 19: 1.1}, default=1.0),
    # Korean schools serve lunch and keep pupils in class, so the peaks are before / after school.
    "student": _hours({7: 1.2, 8: 1.3, 9: 0.25, 10: 0.25, 11: 0.25, 12: 0.6, 13: 0.6, 14: 0.3, 15: 1.8, 16: 2.0,
                       17: 1.7, 18: 1.4}, default=1.0),
    "student:university": _hours({9: 1.1, 12: 1.4, 13: 1.4, 18: 1.2, 21: 1.3, 22: 1.4, 23: 1.4}, default=1.0),
    "commuter": _hours({}, default=1.0),
    "visitor": _hours({}, default=1.0),
}

_HOLIDAY_SCALE: dict[str, float] = {"resident": 1.0, "worker": 0.6, "student": 0.4, "commuter": 0.85, "visitor": 1.1}

_AGE_MIX: dict[str, dict[AgeGroup, float]] = {
    "resident": {"10s": 0.12, "20s": 0.15, "30s": 0.17, "40s": 0.18, "50s": 0.18, "60s+": 0.2},
    "resident:apartment": {"10s": 0.14, "20s": 0.12, "30s": 0.17, "40s": 0.19, "50s": 0.18, "60s+": 0.2},
    "resident:house": {"10s": 0.1, "20s": 0.14, "30s": 0.13, "40s": 0.15, "50s": 0.18, "60s+": 0.3},
    "resident:studio": {"10s": 0.02, "20s": 0.48, "30s": 0.3, "40s": 0.1, "50s": 0.06, "60s+": 0.04},
    "resident:dormitory": {"10s": 0.06, "20s": 0.92, "30s": 0.02},
    "resident:mixed_use": {"10s": 0.05, "20s": 0.25, "30s": 0.22, "40s": 0.18, "50s": 0.15, "60s+": 0.15},
    "worker": {"20s": 0.22, "30s": 0.32, "40s": 0.26, "50s": 0.16, "60s+": 0.04},
    "student": {"10s": 1.0},
    "student:university": {"10s": 0.05, "20s": 0.93, "30s": 0.02},
    "commuter": {"10s": 0.08, "20s": 0.27, "30s": 0.25, "40s": 0.2, "50s": 0.13, "60s+": 0.07},
    "visitor": {"10s": 0.05, "20s": 0.08, "30s": 0.12, "40s": 0.15, "50s": 0.22, "60s+": 0.38},
    "visitor:park": {"10s": 0.15, "20s": 0.2, "30s": 0.22, "40s": 0.18, "50s": 0.12, "60s+": 0.13},
    "visitor:hotel": {"10s": 0.03, "20s": 0.32, "30s": 0.3, "40s": 0.18, "50s": 0.12, "60s+": 0.05},
}

# Relative convenience-store use by age (20s–30s are the heaviest users in Korea).
_AGE_PROPENSITY: dict[AgeGroup, float] = {"10s": 1.1, "20s": 1.45, "30s": 1.2, "40s": 0.95, "50s": 0.8, "60s+": 0.55}


class CategoryPrior(BaseModel):
    """Demand for one complementary venue category and its chaining to convenience stores."""
    trip_rate: float = Field(ge=0)  # visits per present person-hour before the weights below
    synergy: float = Field(default=0.0, ge=0, le=1)  # P(chain to a store | visit, store at the door)
    decay_scale: float = Field(default=1.0, gt=0)  # people walk this many times farther than for a store run
    segment_weight: dict[str, float] = {}  # TownSegment → multiplier (missing = 1)
    age_weight: dict[AgeGroup, float] = {}  # missing = 1
    hour_weight: dict[int, float] = {}  # missing = 1 (closed hours come from the venue)


_CATEGORIES: dict[VenueCategory, CategoryPrior] = {
    # Take-out coffee then a snack / cigarettes; office workers are the core café users.
    VenueCategory.CAFE: CategoryPrior(
        trip_rate=0.012, synergy=0.06, decay_scale=1.2, segment_weight={"worker": 1.8, "student": 0.4},
        hour_weight={8: 1.6, 9: 1.3, 12: 1.3, 13: 1.8, 14: 1.3, 19: 0.7, 20: 0.6, 21: 0.5},
    ),
    VenueCategory.BAKERY: CategoryPrior(
        trip_rate=0.005, synergy=0.05, hour_weight={7: 1.4, 8: 1.4, 17: 1.4, 18: 1.5, 19: 1.4},
    ),
    # Buying a drink to take medicine with.
    VenueCategory.PHARMACY: CategoryPrior(
        trip_rate=0.003, synergy=0.08, age_weight={"10s": 0.6, "50s": 1.3, "60s+": 1.6},
    ),
    # Dessert, drinks, cigarettes after a meal.
    VenueCategory.RESTAURANT: CategoryPrior(
        trip_rate=0.01, synergy=0.04, decay_scale=1.5,
        hour_weight={**_span(0, 24, 0.3), 12: 3.0, 13: 2.0, 18: 2.0, 19: 2.5, 20: 1.5},
    ),
    VenueCategory.FAST_FOOD: CategoryPrior(
        trip_rate=0.004, synergy=0.03, age_weight={"10s": 1.6, "20s": 1.6, "50s": 0.6, "60s+": 0.4},
    ),
    # Hangover drinks, ice cream, cigarettes on the way out.
    VenueCategory.BAR: CategoryPrior(
        trip_rate=0.004, synergy=0.1, age_weight={"10s": 0.0, "20s": 1.6, "30s": 1.3, "60s+": 0.5},
        hour_weight={19: 2.0, 20: 2.0, 21: 2.0, 22: 2.0, 23: 2.0},
    ),
    # Water / protein drinks before or after a workout.
    VenueCategory.GYM: CategoryPrior(
        trip_rate=0.004, synergy=0.12, decay_scale=1.8, segment_weight={"student": 0.3},
        age_weight={"10s": 0.5, "20s": 1.5, "30s": 1.5, "50s": 0.7, "60s+": 0.5},
        hour_weight={6: 2.0, 7: 2.0, 8: 1.5, 18: 1.8, 19: 2.0, 20: 2.0, 21: 1.5},
    ),
    # Hagwon pupils grab snacks / dinner between classes.
    VenueCategory.ACADEMY: CategoryPrior(
        trip_rate=0.02, synergy=0.15, decay_scale=2.5, segment_weight={"worker": 0.1, "commuter": 0.1},
        age_weight={"10s": 6.0, "20s": 0.5, "30s": 0.05, "40s": 0.05, "50s": 0.05, "60s+": 0.0},
        hour_weight={**_span(0, 24, 0.2), **_span(15, 22, 2.0)},
    ),
    VenueCategory.BOOKSTORE: CategoryPrior(trip_rate=0.002, synergy=0.03, decay_scale=1.5),
    # Waiting for the machine to finish.
    VenueCategory.LAUNDRY: CategoryPrior(
        trip_rate=0.002, synergy=0.1, segment_weight={"worker": 0.2, "student": 0.2},
        age_weight={"20s": 2.0, "30s": 1.4},
    ),
    VenueCategory.BANK: CategoryPrior(trip_rate=0.002, synergy=0.04, decay_scale=1.5),
    VenueCategory.PC_ROOM: CategoryPrior(
        trip_rate=0.003, synergy=0.12, age_weight={"10s": 2.0, "20s": 2.0, "40s": 0.4, "50s": 0.2, "60s+": 0.1},
        hour_weight={**_span(14, 24, 1.5)},
    ),
}

# Other venue categories that also capture convenience-type trips, as a fraction of a store's pull.
_SUBSTITUTES: dict[VenueCategory, float] = {VenueCategory.SUPERMARKET: 0.3}


class DemandParams(BaseModel):
    """All priors of the town demand model (uncalibrated defaults, see module docstring)."""
    alpha: float = 1.0  # attractiveness exponent
    beta_per_km: float = 7.0  # distance decay: U ∝ exp(-beta · d_km)
    outside_option_m: float = 300.0  # "skip / buy elsewhere" = a typical store this far away
    detour_factor: float = 1.3  # walking network distance / straight line
    min_distance_m: float = 10.0
    walk_m_per_min: float = 80.0  # 4.8 km/h
    link_decay_m: float = 120.0  # chained trips fade quickly with distance from the venue
    trip_rate: dict[str, float] = Field(default_factory=lambda: dict(_TRIP_RATE))
    exposure: dict[str, dict[str, list[float]]] = Field(default_factory=lambda: copy.deepcopy(_EXPOSURE))
    hour_propensity: dict[str, list[float]] = Field(default_factory=lambda: copy.deepcopy(_PROPENSITY))
    holiday_scale: dict[str, float] = Field(default_factory=lambda: dict(_HOLIDAY_SCALE))
    age_mix: dict[str, dict[AgeGroup, float]] = Field(default_factory=lambda: copy.deepcopy(_AGE_MIX))
    age_propensity: dict[AgeGroup, float] = Field(default_factory=lambda: dict(_AGE_PROPENSITY))
    categories: dict[VenueCategory, CategoryPrior] = Field(default_factory=lambda: copy.deepcopy(_CATEGORIES))
    substitutes: dict[VenueCategory, float] = Field(default_factory=lambda: dict(_SUBSTITUTES))


def day_type_for(day: Weekday, *, holiday: bool = False) -> DayType:
    if holiday:
        return "holiday"
    return "weekend" if day in (Weekday.SAT, Weekday.SUN) else "weekday"


# Day types whose traffic is already represented by the neighborhood's own profile.
_TOWN_DAY_TYPES: dict[ScenarioDayType, DayType] = {
    ScenarioDayType.WEEKEND: "weekend", ScenarioDayType.PUBLIC_HOLIDAY: "holiday", ScenarioDayType.HOLIDAY_SEASON: "holiday",
}


def scenario_traffic(
    scenario: Scenario | None, store: Store | None, scenario_priors: ScenarioPriors | None, *,
    profile: DayType | None = None,
) -> tuple[float, dict[int, float] | None]:
    """Scenario traffic with the store format's priors, excluding a day-type effect already in `profile`."""
    if scenario is None:
        return 1.0, None
    if profile is not None and _TOWN_DAY_TYPES.get(scenario.day_type) == profile:
        scenario = scenario.model_copy(update={"day_type": ScenarioDayType.WEEKDAY})
    fx = compile_scenario(scenario, priors_for(store.type if store is not None else "", scenario_priors))
    return fx.base_traffic, (fx.traffic_by_hour or None)


# Hours modeled when the store's opening hours are unknown (no layout, or a layout without a weekly schedule).
DEFAULT_HOURS = range(7, 24)
# The weekday whose opening hours stand for a day type.
TYPICAL_DAY: dict[DayType, Weekday] = {"weekday": Weekday.WED, "weekend": Weekday.SAT, "holiday": Weekday.SUN}


def with_store_hours(town: Town, store: Store | None, day: Weekday) -> tuple[Town, list[int]]:
    """The town with the focal store open when the layout's weekly schedule opens it on `day`, and those hours (the
    hours to model; none on a closed day). Without a schedule: the town as it is and `DEFAULT_HOURS`."""
    if store is None or not store.weekly_schedule:
        return town, list(DEFAULT_HOURS)
    schedule = store.schedule_for(day)
    if schedule is None or not schedule.is_open:
        return town, []
    venues = [
        v.model_copy(update={"open_hour": schedule.open_hour, "close_hour": schedule.close_hour})
        if v.id == town.focal_venue_id else v
        for v in town.venues
    ]
    return town.model_copy(update={"venues": venues}), list(range(schedule.open_hour, schedule.close_hour))


def purpose_label(segment: TownSegment, hour: int, source_category: str = "") -> str:
    """Short trip-purpose label used in demand rows and persona annotations."""
    if segment == "linked":
        return f"after {source_category.replace('_', ' ')} visit"
    if segment == "commuter":
        if hour < 11:
            return "commute grab-and-go"
        return "commute home" if 16 <= hour < 21 else "transit stop"
    if 5 <= hour < 11:
        return {"worker": "morning coffee & breakfast", "student": "before-class snack"}.get(segment, "morning essentials")
    if 11 <= hour < 14:
        return "lunch"
    if 14 <= hour < 17:
        return {"worker": "afternoon break", "student": "after-school snack"}.get(segment, "afternoon snack")
    if 17 <= hour < 21:
        return {"worker": "after-work errand", "student": "after-school snack", "visitor": "evening errand"}.get(
            segment, "evening groceries",
        )
    return "late-night snack"


def _keyed[T](table: dict[str, T], segment: str, kind: BuildingKind) -> T:
    return table.get(f"{segment}:{kind.value}", table[segment])


def _distance(ax: FloatArray, ay: FloatArray, bx: FloatArray, by: FloatArray, p: DemandParams) -> FloatArray:
    d: FloatArray = np.hypot(ax[:, None] - bx[None, :], ay[:, None] - by[None, :]) * p.detour_factor
    return np.maximum(d, p.min_distance_m)


def _xy(venues: list[Venue]) -> tuple[FloatArray, FloatArray]:
    return np.array([v.x for v in venues], dtype=np.float64), np.array([v.y for v in venues], dtype=np.float64)


def _open_matrix(venues: list[Venue]) -> npt.NDArray[np.bool_]:
    return np.array([[v.is_open(h) for h in range(24)] for v in venues], dtype=np.bool_).reshape(len(venues), 24)


def _huff_flows(
    need: FloatArray, pull: FloatArray, open_: npt.NDArray[np.bool_], outside: float, hours: list[int],
    *, focal: int | None = None,
) -> tuple[FloatArray, FloatArray | None]:
    """Route need[g, h, a] to venues with Huff shares (hour-specific open sets).

    Returns flows[j, h, a] and, only when requested, the focal venue's shares[g, h].
    The full group × venue × hour cube can exceed a gigabyte for a supported large neighborhood;
    downstream calculations only use one venue's shares, or none for complementary categories.
    """
    n_groups, n_venues = pull.shape
    flows: FloatArray = np.zeros((n_venues, 24, need.shape[2]), dtype=np.float64)
    shares: FloatArray | None = np.zeros((n_groups, 24), dtype=np.float64) if focal is not None else None
    patterns: dict[bytes, list[int]] = {}
    for h in hours:
        patterns.setdefault(open_[:, h].tobytes(), []).append(h)
    for hs in patterns.values():
        mask = open_[:, hs[0]].astype(np.float64)
        utility: FloatArray = pull * mask[None, :]
        share: FloatArray = utility / (outside + utility.sum(axis=1, keepdims=True))
        block: FloatArray = need[:, hs, :].reshape(n_groups, len(hs) * need.shape[2])
        flows[:, hs, :] = (share.T @ block).reshape(n_venues, len(hs), need.shape[2])
        if focal is not None and shares is not None:
            shares[:, hs] = share[:, focal, None]
    return flows, shares


def estimate_demand(
    town: Town,
    *,
    day_type: DayType = "weekday",
    hours: Iterable[int] = DEFAULT_HOURS,
    traffic_multiplier: float = 1.0,
    hourly_multiplier: dict[int, float] | None = None,
    beta: float | None = None,
    params: DemandParams | None = None,
) -> TownDemand:
    """Expected visitors of the town's focal convenience store for one day.

    `traffic_multiplier` scales all trips (weather, season); `hourly_multiplier` scales
    single hours (events). `beta` overrides `params.beta_per_km`.
    """
    p = params or DemandParams()
    if beta is not None:
        p = p.model_copy(update={"beta_per_km": beta})
    focal = town.get_venue(town.focal_venue_id)
    if focal is None:
        raise ValueError(f"focal venue {town.focal_venue_id!r} not found in town {town.id!r}")
    hour_list = sorted({h for h in hours if 0 <= h < 24})
    mult: FloatArray = np.zeros(24, dtype=np.float64)
    for h in hour_list:
        mult[h] = traffic_multiplier * (hourly_multiplier or {}).get(h, 1.0)
    decay = p.beta_per_km / 1000.0
    ages = np.array([p.age_propensity.get(a, 1.0) for a in AGE_GROUPS], dtype=np.float64)

    # --- origin groups (building × segment)
    g_building: list[int] = []
    g_segment: list[TownSegment] = []
    people: list[float] = []
    exposure_rows: list[list[float]] = []
    propensity_rows: list[list[float]] = []
    mix_rows: list[list[float]] = []
    profile_day = "weekday" if day_type == "weekday" else "weekend"
    for bi, b in enumerate(town.buildings):
        counts: tuple[tuple[TownSegment, int], ...] = (
            ("resident", b.residents), ("worker", b.workers), ("student", b.students),
            ("commuter", b.daily_passersby), ("visitor", b.visitors),
        )
        for segment, count in counts:
            if count <= 0:
                continue
            scale = p.holiday_scale.get(segment, 1.0) if day_type == "holiday" else 1.0
            exposure = _keyed(p.exposure, segment, b.kind)[profile_day]
            mix = _keyed(p.age_mix, segment, b.kind)
            total_mix = sum(mix.values()) or 1.0
            g_building.append(bi)
            g_segment.append(segment)
            people.append(float(count))
            exposure_rows.append([e * scale for e in exposure])
            propensity_rows.append(_keyed(p.hour_propensity, segment, b.kind))
            mix_rows.append([mix.get(a, 0.0) / total_mix for a in AGE_GROUPS])
    n_groups = len(g_building)
    n_ages = len(AGE_GROUPS)
    persons: FloatArray = np.array(people, dtype=np.float64)
    exposure_arr: FloatArray = np.array(exposure_rows, dtype=np.float64).reshape(n_groups, 24)
    propensity_arr: FloatArray = np.array(propensity_rows, dtype=np.float64).reshape(n_groups, 24)
    mix_arr: FloatArray = np.array(mix_rows, dtype=np.float64).reshape(n_groups, n_ages)
    rate: FloatArray = np.array([p.trip_rate.get(s, 0.0) for s in g_segment], dtype=np.float64)
    gx: FloatArray = np.array([town.buildings[i].x for i in g_building], dtype=np.float64)
    gy: FloatArray = np.array([town.buildings[i].y for i in g_building], dtype=np.float64)

    presence: FloatArray = persons[:, None] * exposure_arr * mult[None, :]  # (G, 24)
    need: FloatArray = (presence * propensity_arr * rate[:, None])[:, :, None] * (mix_arr * ages[None, :])[:, None, :]

    # --- direct trips: Huff among stores and substitutes
    def is_store(v: Venue) -> bool:
        return v.category == VenueCategory.CONVENIENCE or v.id == focal.id

    choice = [v for v in town.venues if is_store(v) or p.substitutes.get(v.category, 0) > 0]
    focal_j = next(j for j, v in enumerate(choice) if v.id == focal.id)
    cx, cy = _xy(choice)
    weight: FloatArray = np.array(
        [(1.0 if is_store(v) else p.substitutes[v.category]) * v.attractiveness ** p.alpha for v in choice],
        dtype=np.float64,
    )
    dist_gc = _distance(gx, gy, cx, cy, p)
    pull: FloatArray = weight[None, :] * np.exp(-decay * dist_gc)
    direct, shares = _huff_flows(need, pull, _open_matrix(choice), math.exp(-decay * p.outside_option_m), hour_list,
                               focal=focal_j)
    assert shares is not None  # requested above for the focal store's origin breakdown
    focal_by_group: FloatArray = shares[:, :, None] * need  # (G, 24, A)

    # --- linked trips from complementary venues
    stores = [j for j, v in enumerate(choice) if is_store(v)]
    store_open = _open_matrix([choice[j] for j in stores])
    store_pull: FloatArray = np.array([choice[j].attractiveness ** p.alpha for j in stores], dtype=np.float64)
    seg_index = {s: i for i, s in enumerate(TOWN_SEGMENTS)}
    linked_to_store: FloatArray = np.zeros((len(choice), 24, n_ages), dtype=np.float64)
    linked_focal_by_cat: dict[VenueCategory, FloatArray] = {}
    linked_focal_by_venue: list[tuple[Venue, FloatArray]] = []
    for category, prior in p.categories.items():
        venues = [v for v in town.venues if v.category == category and not is_store(v)]
        if prior.synergy <= 0 or not venues:
            continue
        cat_decay = decay / prior.decay_scale
        vx, vy = _xy(venues)
        cat_pull: FloatArray = np.array([v.attractiveness ** p.alpha for v in venues], dtype=np.float64)[None, :] * (
            np.exp(-cat_decay * _distance(gx, gy, vx, vy, p))
        )
        seg_w: FloatArray = np.array([prior.segment_weight.get(s, 1.0) for s in g_segment], dtype=np.float64)
        hour_w: FloatArray = np.array([prior.hour_weight.get(h, 1.0) for h in range(24)], dtype=np.float64)
        age_w: FloatArray = np.array([prior.age_weight.get(a, 1.0) for a in AGE_GROUPS], dtype=np.float64)
        cat_need: FloatArray = (presence * hour_w[None, :] * (seg_w * prior.trip_rate)[:, None])[:, :, None] * (
            mix_arr * age_w[None, :]
        )[:, None, :]
        visits, _ = _huff_flows(
            cat_need, cat_pull, _open_matrix(venues), math.exp(-cat_decay * p.outside_option_m), hour_list,
        )  # (V, 24, A)
        link: FloatArray = store_pull[None, :] * np.exp(-_distance(vx, vy, cx[stores], cy[stores], p) / p.link_decay_m)
        focal_cat: FloatArray = np.zeros((24, n_ages), dtype=np.float64)
        focal_venue = np.zeros((len(venues), 24, n_ages), dtype=np.float64)
        for h in hour_list:
            open_link: FloatArray = link * store_open[:, h][None, :]
            reach: FloatArray = open_link.sum(axis=1)
            chain: FloatArray = prior.synergy * np.minimum(reach, 1.0) / np.where(reach > 0, reach, 1.0)
            to_store: FloatArray = open_link * chain[:, None]  # (V, S)
            linked_to_store[stores, h, :] += to_store.T @ visits[:, h, :]
            to_focal = np.asarray(to_store[:, stores.index(focal_j)], dtype=np.float64)
            focal_cat[h] += to_focal @ visits[:, h, :]
            focal_venue[:, h, :] = to_focal[:, None] * visits[:, h, :]
        linked_focal_by_cat[category] = focal_cat
        linked_focal_by_venue.extend((v, focal_venue[k]) for k, v in enumerate(venues))

    # --- aggregate
    focal_direct_hourly: FloatArray = focal_by_group.sum(axis=(0, 2))
    focal_linked_hourly: FloatArray = np.zeros(24, dtype=np.float64)
    for arr in linked_focal_by_cat.values():
        focal_linked_hourly += arr.sum(axis=1)
    hourly: FloatArray = focal_direct_hourly + focal_linked_hourly
    direct_total = float(focal_direct_hourly.sum())
    linked_total = float(focal_linked_hourly.sum())
    total = direct_total + linked_total

    rows: list[HourlySegmentDemand] = []
    seg_codes = np.array([seg_index[s] for s in g_segment], dtype=np.int64)
    segment_totals: dict[str, float] = {s: 0.0 for s in TOWN_SEGMENTS}
    for segment in TOWN_SEGMENTS[:-1]:
        mask = seg_codes == seg_index[segment]
        if not mask.any():
            continue
        by_hour_age: FloatArray = focal_by_group[mask].sum(axis=0)
        segment_totals[segment] = round(float(by_hour_age.sum()), 3)
        for h in hour_list:
            for a, age in enumerate(AGE_GROUPS):
                value = float(by_hour_age[h, a])
                if value > 1e-4:
                    rows.append(HourlySegmentDemand(
                        hour=h, segment=segment, age_group=age, purpose=purpose_label(segment, h),
                        expected_visitors=round(value, 4),
                    ))
    for category, arr in linked_focal_by_cat.items():
        segment_totals["linked"] += float(arr.sum())
        for h in hour_list:
            for a, age in enumerate(AGE_GROUPS):
                value = float(arr[h, a])
                if value > 1e-4:
                    rows.append(HourlySegmentDemand(
                        hour=h, segment="linked", age_group=age, purpose=purpose_label("linked", h, category.value),
                        expected_visitors=round(value, 4), source_category=category.value,
                    ))
    segment_totals["linked"] = round(segment_totals["linked"], 3)
    rows.sort(key=lambda r: (r.hour, TOWN_SEGMENTS.index(r.segment), r.source_category, AGE_GROUPS.index(r.age_group)))

    group_daily: FloatArray = focal_by_group.sum(axis=1)  # (G, A)
    origins: list[OriginShare] = []
    walk_pairs: list[tuple[float, float]] = []
    for g in range(n_groups):
        value = float(group_daily[g].sum())
        if value <= 1e-3:
            continue
        b = town.buildings[g_building[g]]
        distance = float(dist_gc[g, focal_j])
        walk_pairs.append((distance, value))
        origins.append(OriginShare(
            building_id=b.id, kind=b.kind, name=b.name, segment=g_segment[g], distance_m=round(distance, 1),
            expected_visitors=round(value, 4), share=round(value / total, 6) if total > 0 else 0.0,
            by_age={age: round(float(group_daily[g, a]), 4) for a, age in enumerate(AGE_GROUPS)},
            hourly_by_age={
                h: {age: float(focal_by_group[g, h, a]) for a, age in enumerate(AGE_GROUPS)
                    if focal_by_group[g, h, a] > 0}
                for h in hour_list if focal_by_group[g, h].sum() > 0
            },
        ))
    origins.sort(key=lambda o: -o.expected_visitors)

    linked_rows: list[LinkedTrip] = []
    for v, by_hour in linked_focal_by_venue:
        value = float(by_hour.sum())
        if value <= 1e-3:
            continue
        distance = max(math.hypot(v.x - focal.x, v.y - focal.y) * p.detour_factor, p.min_distance_m)
        walk_pairs.append((distance, value))
        linked_rows.append(LinkedTrip(
            from_venue_id=v.id, from_name=v.name, from_category=v.category, distance_m=round(distance, 1),
            expected_visitors=round(value, 4),
            hourly_by_age={
                h: {age: float(by_hour[h, a]) for a, age in enumerate(AGE_GROUPS) if by_hour[h, a] > 0}
                for h in hour_list if by_hour[h].sum() > 0
            },
        ))
    linked_rows.sort(key=lambda t: -t.expected_visitors)

    captured: FloatArray = direct.sum(axis=(1, 2)) + linked_to_store.sum(axis=(1, 2))
    all_trips = float(captured.sum())
    convenience_trips = float(captured[stores].sum())
    store_rows = [
        StoreShare(
            venue_id=v.id, name=v.name, category=v.category, is_focal=v.id == focal.id,
            distance_m=round(math.hypot(v.x - focal.x, v.y - focal.y) * p.detour_factor, 1),
            expected_visitors=round(float(captured[j]), 3),
            share=round(float(captured[j]) / all_trips, 6) if all_trips > 0 else 0.0,
        )
        for j, v in enumerate(choice)
    ]
    store_rows.sort(key=lambda s: -s.expected_visitors)

    walk_pairs.sort()
    walked = sum(w for _, w in walk_pairs)

    def radius(fraction: float) -> float:
        cumulative = 0.0
        for distance, value in walk_pairs:
            cumulative += value
            if cumulative >= fraction * walked:
                return round(distance, 1)
        return 0.0

    return TownDemand(
        focal_venue_id=focal.id,
        day_type=day_type,
        total_daily_visitors=round(total, 3),
        direct_visitors=round(direct_total, 3),
        linked_visitors=round(linked_total, 3),
        hourly_totals=[round(float(x), 4) for x in hourly],
        hourly_by_segment=rows,
        segment_totals=segment_totals,
        origin_shares=origins,
        linked_trips=linked_rows,
        store_shares=store_rows,
        market_share=round(float(captured[focal_j]) / convenience_trips, 6) if convenience_trips > 0 else 0.0,
        catchment_radius_50_m=radius(0.5),
        catchment_radius_80_m=radius(0.8),
        avg_walk_distance_m=round(sum(d * w for d, w in walk_pairs) / walked, 1) if walked > 0 else 0.0,
    )


def synergy_analysis(
    town: Town,
    *,
    day_type: DayType = "weekday",
    hours: Iterable[int] = DEFAULT_HOURS,
    traffic_multiplier: float = 1.0,
    hourly_multiplier: dict[int, float] | None = None,
    beta: float | None = None,
    params: DemandParams | None = None,
    min_effect: float = 0.5,
) -> list[SynergyRow]:
    """Leave-one-out effect of every non-focal venue on the focal store's daily visitors.

    Rows are sorted by absolute effect. |effect| below `min_effect` visitors/day is "neutral".
    A far-away café or academy can come out as a (small) competitor: it draws customers away
    from the same-category venues next to the focal store, and with them their linked trips.
    Cost: one `estimate_demand` call per venue (~50 ms each for an 800 m town).
    """
    hour_list = list(hours)

    def visitors(t: Town) -> float:
        return estimate_demand(
            t, day_type=day_type, hours=hour_list, traffic_multiplier=traffic_multiplier,
            hourly_multiplier=hourly_multiplier, beta=beta, params=params,
        ).total_daily_visitors

    base = visitors(town)
    focal = town.get_venue(town.focal_venue_id)
    if focal is None:
        raise ValueError(f"focal venue {town.focal_venue_id!r} not found in town {town.id!r}")
    detour = (params or DemandParams()).detour_factor
    rows: list[SynergyRow] = []
    for v in town.venues:
        if v.id == focal.id:
            continue
        without = town.model_copy(update={"venues": [o for o in town.venues if o.id != v.id]})
        effect = base - visitors(without)
        role = "neutral" if abs(effect) < min_effect else ("complement" if effect > 0 else "competitor")
        rows.append(SynergyRow(
            venue_id=v.id, name=v.name, category=v.category,
            distance_m=round(math.hypot(v.x - focal.x, v.y - focal.y) * detour, 1),
            effect_on_focal_visitors=round(effect, 3),
            effect_on_focal_pct=round(100.0 * effect / base, 3) if base > 0 else 0.0,
            role=role,
        ))
    rows.sort(key=lambda r: -abs(r.effect_on_focal_visitors))
    return rows
