"""Situations a store operates in: weather, calendar, local events, promotions, stock-outs, crowding.

A `Scenario` is declarative; `engine/scenario.py` compiles it into numeric effects (traffic per
hour, demand multipliers per product category, dwell / impulse / walk-out / budget multipliers)
and a short situation text for LLM/VLM prompts. All effect sizes are documented priors meant to
be calibrated against POS data (see `ScenarioPriors`).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Weather(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    SNOW = "snow"
    HEATWAVE = "heatwave"
    COLD_SNAP = "cold_snap"
    FINE_DUST = "fine_dust"
    TYPHOON = "typhoon"


class Season(StrEnum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class DayType(StrEnum):
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    PUBLIC_HOLIDAY = "public_holiday"
    HOLIDAY_SEASON = "holiday_season"      # Chuseok, Lunar New Year, Christmas week
    SCHOOL_VACATION = "school_vacation"


class EventKind(StrEnum):
    FESTIVAL = "festival"
    SPORTS_MATCH = "sports_match"
    CONCERT = "concert"
    EXAM_PERIOD = "exam_period"
    PAYDAY = "payday"
    COMPETITOR_OPENING = "competitor_opening"
    COMPETITOR_CLOSED = "competitor_closed"
    ROAD_CONSTRUCTION = "road_construction"
    MARATHON = "marathon"
    CONFERENCE = "conference"
    NIGHT_MARKET = "night_market"


class LocalEvent(BaseModel):
    kind: EventKind
    intensity: float = Field(default=0.6, ge=0.0, le=1.0)
    start_hour: int = Field(default=0, ge=0, le=24)
    end_hour: int = Field(default=24, ge=0, le=24)
    note: str = ""


class PromotionKind(StrEnum):
    DISCOUNT = "discount"
    ONE_PLUS_ONE = "1+1"
    TWO_PLUS_ONE = "2+1"
    FEATURED = "featured"        # end-cap / display, no price change


class Promotion(BaseModel):
    # Matched case-insensitively against SKU, product name and rack name/description, so it can
    # target one product ("Pepsi 20oz"), a word ("energy"), or a whole rack ("Drink 1").
    target: str = Field(min_length=1)
    kind: PromotionKind = PromotionKind.DISCOUNT
    discount_pct: float = Field(default=20.0, ge=0.0, le=90.0)
    label: str = ""


class Crowding(StrEnum):
    QUIET = "quiet"
    NORMAL = "normal"
    BUSY = "busy"
    PACKED = "packed"


class Scenario(BaseModel):
    id: str = "custom"
    name: str = "Custom situation"
    description: str = ""
    weather: Weather = Weather.CLEAR
    temperature_c: float | None = Field(default=None, ge=-30.0, le=45.0)
    season: Season | None = None
    day_type: DayType = DayType.WEEKDAY
    # Restrict the run to these weekdays (1 = Monday … 7 = Sunday); empty = every simulated day.
    only_days: list[int] = []
    traffic_multiplier: float = Field(default=1.0, ge=0.0, le=5.0)
    hourly_traffic: dict[int, float] = {}
    crowding: Crowding = Crowding.NORMAL
    events: list[LocalEvent] = []
    promotions: list[Promotion] = []
    # SKUs, product names or words; matching products are removed from the shelves.
    stockouts: list[str] = []
    budget_multiplier: float = Field(default=1.0, ge=0.2, le=3.0)
    music: Literal["none", "calm", "upbeat"] = "none"
    lighting: Literal["dim", "normal", "bright"] = "normal"
    notes: str = Field(default="", max_length=400)   # free text added to LLM/VLM prompts
