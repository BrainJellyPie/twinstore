"""Situations a store operates in: weather, calendar, local events, promotions, stock-outs, crowding.

A `Scenario` is declarative; `engine/scenario.py` compiles it into numeric effects (traffic per
hour, demand multipliers per product category, dwell / impulse / walk-out / budget multipliers)
and a short situation text for LLM/VLM prompts. All effect sizes are documented priors meant to
be calibrated against POS data (see `ScenarioPriors`).
"""

from enum import StrEnum
from typing import Annotated, Literal

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
    only_days: list[Annotated[int, Field(ge=1, le=7)]] = []
    traffic_multiplier: float = Field(default=1.0, ge=0.0, le=5.0)
    hourly_traffic: dict[
        Annotated[int, Field(ge=0, le=23)],
        Annotated[float, Field(ge=0, allow_inf_nan=False)],
    ] = {}
    crowding: Crowding = Crowding.NORMAL
    events: list[LocalEvent] = []
    promotions: list[Promotion] = []
    # SKUs, product names or words; matching products are removed from the shelves.
    stockouts: list[str] = []
    budget_multiplier: float = Field(default=1.0, ge=0.2, le=3.0)
    music: Literal["none", "calm", "upbeat"] = "none"
    lighting: Literal["dim", "normal", "bright"] = "normal"
    notes: str = Field(default="", max_length=400)   # free text added to LLM/VLM prompts


class ScenarioPriors(BaseModel):
    """Every effect size used below, so calibration can override any of them."""
    weather_traffic: dict[str, float] = {
        "clear": 1.0, "cloudy": 0.97, "rain": 0.85, "heavy_rain": 0.65, "snow": 0.7, "heatwave": 0.92,
        "cold_snap": 0.82, "fine_dust": 0.87, "typhoon": 0.4,
    }
    weather_demand: dict[str, dict[str, float]] = {
        "rain": {"hot_food": 1.2, "cold_drinks": 0.9, "health": 1.8},
        "heavy_rain": {"hot_food": 1.3, "cold_drinks": 0.85, "health": 2.5},
        "snow": {"hot_food": 1.4, "ice_cream": 0.5, "cold_drinks": 0.8},
        "heatwave": {"cold_drinks": 1.6, "water": 1.8, "ice_cream": 2.0, "hot_food": 0.7},
        "cold_snap": {"hot_food": 1.5, "ice_cream": 0.4, "cold_drinks": 0.75},
        "fine_dust": {"health": 2.0, "water": 1.2},
        "typhoon": {"hot_food": 1.8, "water": 1.7, "snacks": 1.3, "meals": 1.3},
    }
    weather_dwell: dict[str, float] = {"rain": 1.1, "heavy_rain": 1.15, "snow": 1.1, "heatwave": 1.1, "typhoon": 0.9}
    # Typhoon / snow: people stock up.
    weather_quantity: dict[str, float] = {"typhoon": 1.6, "snow": 1.2}
    season_demand: dict[str, dict[str, float]] = {
        "summer": {"cold_drinks": 1.15, "ice_cream": 1.3, "hot_food": 0.85},
        "winter": {"hot_food": 1.2, "ice_cream": 0.7},
        "spring": {}, "autumn": {},
    }
    day_traffic: dict[str, float] = {
        "weekday": 1.0, "weekend": 0.95, "public_holiday": 0.9, "holiday_season": 0.8, "school_vacation": 0.92,
    }
    day_demand: dict[str, dict[str, float]] = {
        "weekend": {"snacks": 1.2, "alcohol": 1.25, "meals": 0.9},
        "public_holiday": {"snacks": 1.2, "alcohol": 1.3},
        "holiday_season": {"alcohol": 1.4, "desserts": 1.3, "snacks": 1.15},
        "school_vacation": {"ice_cream": 1.15, "snacks": 1.1, "meals": 0.9},
    }
    day_budget: dict[str, float] = {"holiday_season": 1.2, "weekend": 1.05}
    # Per unit intensity: traffic multiplier = 1 + intensity × value (inside the event hours).
    event_traffic: dict[str, float] = {
        "festival": 0.9, "sports_match": 0.5, "concert": 0.6, "exam_period": 0.15, "payday": 0.1,
        "competitor_opening": -0.3, "competitor_closed": 0.25, "road_construction": -0.2, "marathon": 0.4,
        "conference": 0.3, "night_market": 0.7,
    }
    event_demand: dict[str, dict[str, float]] = {
        "festival": {"cold_drinks": 1.4, "snacks": 1.3, "alcohol": 1.4},
        "sports_match": {"alcohol": 1.8, "snacks": 1.6},
        "concert": {"cold_drinks": 1.4, "snacks": 1.2, "water": 1.4},
        "exam_period": {"caffeine": 1.7, "snacks": 1.25, "desserts": 1.15},
        "payday": {"alcohol": 1.25, "desserts": 1.2, "meals": 1.1},
        "marathon": {"water": 2.0, "cold_drinks": 1.5},
        "conference": {"caffeine": 1.4, "meals": 1.2},
        "night_market": {"alcohol": 1.3, "cold_drinks": 1.2},
    }
    event_budget: dict[str, float] = {"payday": 1.3}
    event_impulse: dict[str, float] = {"festival": 1.2, "payday": 1.15, "night_market": 1.15, "sports_match": 1.1}
    crowding_dwell: dict[str, float] = {"quiet": 1.1, "normal": 1.0, "busy": 0.88, "packed": 0.75}
    crowding_impulse: dict[str, float] = {"quiet": 1.05, "normal": 1.0, "busy": 0.92, "packed": 0.8}
    crowding_walkout: dict[str, float] = {"quiet": 0.8, "normal": 1.0, "busy": 1.4, "packed": 2.5}
    music_dwell: dict[str, float] = {"none": 1.0, "calm": 1.08, "upbeat": 0.95}
    music_impulse: dict[str, float] = {"none": 1.0, "calm": 1.03, "upbeat": 1.02}
    lighting_impulse: dict[str, float] = {"dim": 0.95, "normal": 1.0, "bright": 1.04}
    # Continuous temperature response (°C): 1 + slope × (t − pivot), clipped; replaces the categorical
    # heat / cold demand for the same categories when a temperature is given.
    temperature_slope: dict[str, float] = {"cold_drinks": 0.03, "water": 0.035, "ice_cream": 0.06, "hot_food": -0.02}
    temperature_pivot: dict[str, float] = {"cold_drinks": 20.0, "water": 20.0, "ice_cream": 20.0, "hot_food": 15.0}
    # How a situation changes the share of trips that include a kind of product, for shoppers whose
    # needs are drawn from their purchase history (Persona.category_rates): keyed "season:summer",
    # "day:weekend", "event:sports_match" (scaled by intensity), "weather:rain". Measured directly as
    # per-trip ratios on real receipts; empty for the convenience priors (no data yet).
    need_ratio: dict[str, dict[str, float]] = {}
    temperature_clip: dict[str, tuple[float, float]] = {"cold_drinks": (0.6, 1.8), "water": (0.7, 1.9),
                                                         "ice_cream": (0.3, 2.4), "hot_food": (0.6, 1.6)}
    # Promotion lift on the promoted item's pick probability (before the price effect).
    promo_lift: dict[str, float] = {"discount": 1.3, "1+1": 1.9, "2+1": 1.6, "featured": 1.35}
