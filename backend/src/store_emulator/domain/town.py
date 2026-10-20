"""Town / neighborhood models for the multi-store demand model.

Coordinates are town-local meters: x grows east, y grows north, and the origin is
the south-west corner of a `size_m` × `size_m` square (the town center is at
(size_m / 2, size_m / 2)). Procedural towns and OSM imports share this frame.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .persona import AgeGroup


class BuildingKind(StrEnum):
    APARTMENT = "apartment"
    HOUSE = "house"
    STUDIO = "studio"  # officetel / one-room studio block
    DORMITORY = "dormitory"
    OFFICE = "office"
    SCHOOL = "school"
    UNIVERSITY = "university"
    STATION = "station"  # transit entrance (subway / rail / bus stop)
    HOSPITAL = "hospital"
    HOTEL = "hotel"
    PARK = "park"
    MIXED_USE = "mixed_use"  # shops on the ground floor, homes / offices above


class VenueCategory(StrEnum):
    CONVENIENCE = "convenience"
    CAFE = "cafe"
    BAKERY = "bakery"
    PHARMACY = "pharmacy"
    RESTAURANT = "restaurant"
    FAST_FOOD = "fast_food"
    SUPERMARKET = "supermarket"
    BAR = "bar"
    GYM = "gym"
    BOOKSTORE = "bookstore"
    ACADEMY = "academy"  # hagwon / cram school
    LAUNDRY = "laundry"
    BANK = "bank"
    PC_ROOM = "pc_room"


class RoadKind(StrEnum):
    ARTERIAL = "arterial"
    STREET = "street"
    ALLEY = "alley"
    FOOTPATH = "footpath"


class TownArchetype(StrEnum):
    RESIDENTIAL = "residential"
    UNIVERSITY = "university"
    BUSINESS_DISTRICT = "business_district"
    SUBURBAN = "suburban"
    STATION_AREA = "station_area"
    TOURIST = "tourist"
    MIXED = "mixed"


type TownSource = Literal["procedural", "osm"]
type DayType = Literal["weekday", "weekend", "holiday"]
# Who makes the trip. "linked" = chained from a visit to another venue (café → store).
type TownSegment = Literal["resident", "worker", "student", "commuter", "visitor", "linked"]

TOWN_SEGMENTS: list[TownSegment] = ["resident", "worker", "student", "commuter", "visitor", "linked"]


class Building(BaseModel):
    id: str
    kind: BuildingKind
    name: str = ""
    x: float  # footprint center, meters
    y: float
    width: float = Field(default=20.0, gt=0)  # east–west extent, meters
    depth: float = Field(default=20.0, gt=0)  # north–south extent, meters
    floors: int = Field(default=1, ge=0)
    residents: int = Field(default=0, ge=0)  # people living here
    workers: int = Field(default=0, ge=0)  # people working here on a weekday
    students: int = Field(default=0, ge=0)  # pupils / students based here on a school day
    daily_passersby: int = Field(default=0, ge=0)  # transit users per weekday (stations)
    visitors: int = Field(default=0, ge=0)  # daily visitors: patients, park-goers, hotel guests


class Venue(BaseModel):
    id: str
    name: str
    category: VenueCategory
    x: float
    y: float
    attractiveness: float = Field(default=1.0, gt=0)  # floor area / brand pull, 1.0 = typical
    open_hour: int = Field(default=0, ge=0, le=23)
    close_hour: int = Field(default=24, ge=0, le=24)  # < open_hour means it closes after midnight
    is_focal: bool = False  # the store being simulated
    setup_id: str | None = None  # store setup this venue maps to, if any
    building_id: str | None = None

    def is_open(self, hour: int) -> bool:
        start, end = self.open_hour, self.close_hour
        if end % 24 == start:
            return True
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end


class Road(BaseModel):
    id: str
    kind: RoadKind
    points: list[tuple[float, float]]
    name: str = ""


class TownSpec(BaseModel):
    archetype: TownArchetype = TownArchetype.RESIDENTIAL
    size_m: float = Field(default=800.0, ge=200.0, le=3000.0)
    density: float = Field(default=0.5, ge=0.0, le=1.0)
    n_competitors: int | None = Field(default=None, ge=0, le=60)  # other convenience stores; None = from population
    neighbor_categories: list[VenueCategory] = []  # venues placed right next to the focal store
    venue_density: float = Field(default=1.0, ge=0.0, le=4.0)  # scales background venues (0 = none)
    seed: int = 0
    name: str = ""


class Town(BaseModel):
    id: str
    name: str
    archetype: TownArchetype
    size_m: float
    buildings: list[Building] = []
    venues: list[Venue] = []
    roads: list[Road] = []
    source: TownSource = "procedural"
    center_lat: float | None = None
    center_lon: float | None = None
    focal_venue_id: str
    spec: TownSpec | None = None  # generation spec for procedural towns

    def get_venue(self, venue_id: str) -> Venue | None:
        return next((v for v in self.venues if v.id == venue_id), None)

    def get_building(self, building_id: str) -> Building | None:
        return next((b for b in self.buildings if b.id == building_id), None)


# ---------------------------------------------------------------- demand results


class HourlySegmentDemand(BaseModel):
    hour: int
    segment: TownSegment
    age_group: AgeGroup
    purpose: str  # short label, e.g. "lunch", "commute grab-and-go", "after cafe visit"
    expected_visitors: float
    source_category: str = ""  # VenueCategory value for linked trips, "" otherwise


class OriginShare(BaseModel):
    """Direct (non-linked) focal visitors from one building and segment over the day."""
    building_id: str
    kind: BuildingKind
    name: str = ""
    segment: TownSegment
    distance_m: float  # walking distance to the focal store (detour applied)
    expected_visitors: float
    share: float  # of the focal store's daily visitors (direct + linked)
    by_age: dict[AgeGroup, float] = {}


class LinkedTrip(BaseModel):
    from_venue_id: str
    from_name: str = ""
    from_category: VenueCategory
    distance_m: float
    expected_visitors: float


class StoreShare(BaseModel):
    venue_id: str
    name: str
    category: VenueCategory
    is_focal: bool
    distance_m: float  # from the focal store
    expected_visitors: float  # convenience-type trips captured per day (direct + linked)
    share: float  # of all convenience-type trips made in the town


class SynergyRow(BaseModel):
    """What one venue does to the focal store's daily visitors.

    `effect_on_focal_visitors` = focal visitors with the venue − without it, so a positive
    value means the venue brings customers (complement) and a negative value means it takes
    them away (competitor). Removing the venue changes focal visitors by −effect.
    """
    venue_id: str
    name: str
    category: VenueCategory
    distance_m: float
    effect_on_focal_visitors: float
    effect_on_focal_pct: float
    role: Literal["competitor", "complement", "neutral"]


class TownDemand(BaseModel):
    focal_venue_id: str
    day_type: DayType
    total_daily_visitors: float
    direct_visitors: float
    linked_visitors: float
    hourly_totals: list[float]  # 24 entries, index = hour; zero outside the modeled hours
    hourly_by_segment: list[HourlySegmentDemand]
    segment_totals: dict[str, float]  # TownSegment → visitors per day
    origin_shares: list[OriginShare]
    linked_trips: list[LinkedTrip]
    store_shares: list[StoreShare]
    market_share: float  # focal share of convenience-store trips (substitutes excluded)
    catchment_radius_50_m: float  # walking distance covering 50 % of focal visitors
    catchment_radius_80_m: float
    avg_walk_distance_m: float


class TownArrival(BaseModel):
    """Town-side annotation of one synthetic visitor produced for a simulated day."""
    persona_id: str  # id of the cloned persona in the visitor list
    source_persona_id: str  # pool persona it was cloned from
    hour: int
    segment: TownSegment
    age_group: AgeGroup
    purpose: str
    origin_building_id: str = ""  # "" for linked trips (they come from a venue)
    origin_kind: str = ""  # BuildingKind value, or the VenueCategory value for linked trips
    origin_name: str = ""
    distance_m: float
    walk_min: float
    came_from_venue: str = ""  # VenueCategory value of the venue visited just before, "" if none
    came_from_venue_id: str = ""
    is_linked_trip: bool = False
