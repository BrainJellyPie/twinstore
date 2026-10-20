"""Compile a Scenario into numeric effects, and apply them to the store and the visitor list.

Effect sizes are priors (documented inline) chosen to reproduce well-known convenience-store
patterns — heat sells cold drinks and ice cream, cold and rain sell hot food, events bring
traffic and snacks/alcohol, crowding shortens browsing and causes walk-outs. They are meant to be
calibrated: every number lives in `ScenarioPriors`.
"""

import math
import random
import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.scenario import (
    Crowding,
    DayType,
    EventKind,
    LocalEvent,
    Promotion,
    PromotionKind,
    Scenario,
    Season,
    Weather,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import stable_seed

# Demand categories the scenario layer reasons about, with the words that identify them on rack
# labels and product names (English + Korean). Generic on purpose: no brand names.
CATEGORY_WORDS: dict[str, frozenset[str]] = {
    "cold_drinks": frozenset({"drink", "beverage", "soda", "cola", "juice", "lemonade", "water", "sparkling", "energy",
                              "sport", "isotonic", "ade", "iced", "milk", "smoothie", "음료", "탄산", "주스", "생수",
                              "물", "이온", "에너지"}),
    "water": frozenset({"water", "생수", "물"}),
    "hot_food": frozenset({"ramen", "noodle", "noodles", "soup", "cup", "bowl", "instant", "hot", "coffee", "latte",
                           "tea", "dumpling", "oden", "라면", "컵라면", "국", "커피", "호빵", "어묵"}),
    "ice_cream": frozenset({"ice", "cream", "popsicle", "frozen", "gelato", "sorbet", "bar", "아이스", "아이스크림",
                            "빙과", "냉동"}),
    "snacks": frozenset({"snack", "chip", "chips", "crisps", "cookie", "cookies", "candy", "chocolate", "cracker",
                         "jerky", "nut", "nuts", "popcorn", "gum", "과자", "스낵", "초콜릿", "사탕", "젤리"}),
    "meals": frozenset({"sandwich", "lunch", "rice", "kimbap", "bento", "burger", "wrap", "salad", "pizza", "meal",
                        "도시락", "김밥", "샌드위치", "삼각김밥", "햄버거"}),
    "alcohol": frozenset({"beer", "soju", "wine", "makgeolli", "highball", "alcohol", "liquor", "맥주", "소주", "와인",
                          "막걸리", "주류"}),
    "health": frozenset({"mask", "medicine", "vitamin", "bandage", "sanitizer", "tissue", "umbrella", "raincoat",
                         "마스크", "의약", "비타민", "우산", "우비", "휴지"}),
    "caffeine": frozenset({"energy", "coffee", "espresso", "caffeine", "shot", "에너지", "커피"}),
    "desserts": frozenset({"cake", "dessert", "pudding", "donut", "pastry", "bread", "bun", "muffin", "케이크", "빵",
                           "디저트"}),
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^\w]+", text.lower()) if t}


def item_categories(rack: Rack, item: SlotItem) -> set[str]:
    words = _tokens(f"{rack.rack_name} {rack.rack_desc} {item.name}")
    return {cat for cat, vocab in CATEGORY_WORDS.items() if words & vocab}


def words_categories(text: str) -> set[str]:
    words = _tokens(text)
    return {cat for cat, vocab in CATEGORY_WORDS.items() if words & vocab}


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
    # Promotion lift on the promoted item's pick probability (before the price effect).
    promo_lift: dict[str, float] = {"discount": 1.3, "1+1": 1.9, "2+1": 1.6, "featured": 1.35}


@dataclass
class ScenarioEffects:
    traffic_by_hour: dict[int, float] = field(default_factory=dict[int, float])
    base_traffic: float = 1.0
    demand: dict[str, float] = field(default_factory=dict[str, float])
    impulse: float = 1.0
    dwell: float = 1.0
    walkout: float = 1.0
    budget: float = 1.0
    quantity: float = 1.0
    situation: str = ""

    def traffic(self, hour: int) -> float:
        return self.base_traffic * self.traffic_by_hour.get(hour, 1.0)

    def demand_for(self, categories: set[str]) -> float:
        """Product of the multipliers of every category the item belongs to, clipped to [0.2, 3]."""
        m = 1.0
        for cat in categories:
            m *= self.demand.get(cat, 1.0)
        return min(3.0, max(0.2, m))


def _mul(target: dict[str, float], updates: dict[str, float], power: float = 1.0) -> None:
    for k, v in updates.items():
        target[k] = target.get(k, 1.0) * (v ** power)


def _clip(v: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, v))


def _temperature_demand(t: float) -> dict[str, float]:
    """Continuous temperature response (°C), centered on a mild 18–20 °C day."""
    clip = _clip
    return {
        "cold_drinks": clip(1 + 0.03 * (t - 20), 0.6, 1.8),
        "water": clip(1 + 0.035 * (t - 20), 0.7, 1.9),
        "ice_cream": clip(1 + 0.06 * (t - 20), 0.3, 2.4),
        "hot_food": clip(1 - 0.02 * (t - 15), 0.6, 1.6),
    }


def compile_scenario(scenario: Scenario, priors: ScenarioPriors | None = None) -> ScenarioEffects:
    p = priors or ScenarioPriors()
    fx = ScenarioEffects()
    w = scenario.weather.value
    fx.base_traffic = scenario.traffic_multiplier * p.weather_traffic.get(w, 1.0) * p.day_traffic.get(scenario.day_type.value, 1.0)
    _mul(fx.demand, p.weather_demand.get(w, {}))
    if scenario.temperature_c is not None:
        # The temperature curve replaces the categorical heat/cold demand for the same categories.
        for cat, v in _temperature_demand(scenario.temperature_c).items():
            fx.demand[cat] = v * (p.weather_demand.get(w, {}).get(cat, 1.0) ** 0.3)
    if scenario.season is not None:
        _mul(fx.demand, p.season_demand.get(scenario.season.value, {}))
    _mul(fx.demand, p.day_demand.get(scenario.day_type.value, {}))
    fx.dwell = p.weather_dwell.get(w, 1.0) * p.crowding_dwell[scenario.crowding.value] * p.music_dwell[scenario.music]
    fx.impulse = p.crowding_impulse[scenario.crowding.value] * p.music_impulse[scenario.music] * p.lighting_impulse[scenario.lighting]
    fx.walkout = p.crowding_walkout[scenario.crowding.value]
    fx.quantity = p.weather_quantity.get(w, 1.0)
    fx.budget = scenario.budget_multiplier * p.day_budget.get(scenario.day_type.value, 1.0)
    for event in scenario.events:
        _apply_event(fx, event, p)
    for hour, m in scenario.hourly_traffic.items():
        fx.traffic_by_hour[hour] = fx.traffic_by_hour.get(hour, 1.0) * m
    fx.situation = situation_text(scenario)
    return fx


def _apply_event(fx: ScenarioEffects, event: LocalEvent, p: ScenarioPriors) -> None:
    k, i = event.kind.value, event.intensity
    lift = max(0.05, 1.0 + i * p.event_traffic.get(k, 0.0))
    whole_day = event.start_hour <= 0 and event.end_hour >= 24
    if whole_day:
        fx.base_traffic *= lift
    else:
        for h in range(event.start_hour, event.end_hour):
            fx.traffic_by_hour[h] = fx.traffic_by_hour.get(h, 1.0) * lift
    # Demand / budget / impulse effects scale with intensity (power i keeps 0 → no effect).
    _mul(fx.demand, p.event_demand.get(k, {}), power=i)
    fx.budget *= p.event_budget.get(k, 1.0) ** i
    fx.impulse *= p.event_impulse.get(k, 1.0) ** i


_WEATHER_TEXT: dict[Weather, str] = {
    Weather.CLEAR: "clear skies", Weather.CLOUDY: "overcast", Weather.RAIN: "it is raining",
    Weather.HEAVY_RAIN: "heavy rain outside", Weather.SNOW: "it is snowing", Weather.HEATWAVE: "a heatwave",
    Weather.COLD_SNAP: "a cold snap", Weather.FINE_DUST: "a fine-dust (air pollution) alert",
    Weather.TYPHOON: "a typhoon warning — people are stocking up",
}
_EVENT_TEXT: dict[EventKind, str] = {
    EventKind.FESTIVAL: "a local festival nearby", EventKind.SPORTS_MATCH: "a big sports match tonight",
    EventKind.CONCERT: "a concert nearby", EventKind.EXAM_PERIOD: "exam period for students",
    EventKind.PAYDAY: "it is payday", EventKind.COMPETITOR_OPENING: "a competing store just opened nearby",
    EventKind.COMPETITOR_CLOSED: "the nearby competitor is closed", EventKind.ROAD_CONSTRUCTION: "road construction outside",
    EventKind.MARATHON: "a marathon passes by", EventKind.CONFERENCE: "a conference in the office district",
    EventKind.NIGHT_MARKET: "a night market on the street",
}
_DAY_TEXT: dict[DayType, str] = {
    DayType.WEEKDAY: "", DayType.WEEKEND: "weekend", DayType.PUBLIC_HOLIDAY: "public holiday",
    DayType.HOLIDAY_SEASON: "holiday season (family visits, gift shopping)", DayType.SCHOOL_VACATION: "school vacation",
}


def situation_text(scenario: Scenario) -> str:
    """One or two English sentences for LLM/VLM prompts ("" for a plain day)."""
    parts: list[str] = []
    weather = _WEATHER_TEXT[scenario.weather] if scenario.weather != Weather.CLEAR else ""
    if scenario.temperature_c is not None:
        weather = f"{weather + ', ' if weather else ''}{scenario.temperature_c:.0f}°C outside"
    if weather:
        parts.append(weather)
    if scenario.season is not None and scenario.season != Season.SPRING:
        parts.append(scenario.season.value)
    if _DAY_TEXT[scenario.day_type]:
        parts.append(_DAY_TEXT[scenario.day_type])
    parts.extend(_EVENT_TEXT[e.kind] for e in scenario.events if e.intensity > 0)
    if scenario.crowding in (Crowding.BUSY, Crowding.PACKED):
        parts.append("the store is crowded with a checkout queue" if scenario.crowding == Crowding.PACKED else "the store is busy")
    if scenario.promotions:
        promos = ", ".join(_promo_label(pr) for pr in scenario.promotions[:4])
        parts.append(f"promotions: {promos}")
    if scenario.stockouts:
        parts.append(f"sold out: {', '.join(scenario.stockouts[:4])}")
    text = "; ".join(parts)
    if scenario.notes:
        text = f"{text}. {scenario.notes}" if text else scenario.notes
    return text[:400]


def _promo_label(promo: Promotion) -> str:
    if promo.label:
        return f"{promo.target} {promo.label}"
    if promo.kind == PromotionKind.DISCOUNT:
        return f"{promo.target} {promo.discount_pct:.0f}% off"
    if promo.kind == PromotionKind.FEATURED:
        return f"{promo.target} on display"
    return f"{promo.target} {promo.kind.value}"


def _matches(target: str, rack: Rack, item: SlotItem) -> bool:
    t = target.strip().lower()
    if not t:
        return False
    if t == item.sku.lower() or t in item.name.lower():
        return True
    if t in rack.rack_name.lower():
        return True
    return bool(_tokens(t) & _tokens(f"{rack.rack_name} {rack.rack_desc} {item.name}")) and len(t) >= 3


def apply_to_store(store: Store, scenario: Scenario) -> tuple[Store, dict[str, float]]:
    """Promotions change prices/labels, stock-outs empty the facings. Returns the new store and a
    sku → pick-probability lift for promoted items (used by the rule-based engine)."""
    lifts: dict[str, float] = {}
    priors = ScenarioPriors()
    racks: list[Rack] = []
    for rack in store.racks:
        slots: list[Slot] = []
        for slot in rack.slots:
            items: list[SlotItem] = []
            for item in slot.items:
                if any(_matches(s, rack, item) for s in scenario.stockouts):
                    continue
                promo = next((pr for pr in scenario.promotions if _matches(pr.target, rack, item)), None)
                if promo is not None:
                    price = item.price
                    if promo.kind == PromotionKind.DISCOUNT:
                        price = int(round(item.price * (1 - promo.discount_pct / 100)))
                    label = promo.label or (f"{promo.discount_pct:.0f}% OFF" if promo.kind == PromotionKind.DISCOUNT
                                            else "SALE" if promo.kind == PromotionKind.FEATURED else promo.kind.value)
                    item = item.model_copy(update={"price": price, "promo": label})
                    lifts[item.sku] = priors.promo_lift.get(promo.kind.value, 1.2)
                items.append(item)
            slots.append(slot.model_copy(update={"items": items}))
        racks.append(rack.model_copy(update={"slots": slots}))
    return store.model_copy(update={"racks": racks}), lifts


def apply_to_personas(personas: list[Persona], scenario: Scenario, effects: ScenarioEffects, *, seed: int) -> list[Persona]:
    """Day filter, traffic scaling per hour (thinning / seeded clones) and budget scaling.

    Original personas keep their ids, so a scenario run stays paired with a baseline run on the
    same seed; clones get ids "<id>~s<k>".
    """
    pool = [p for p in personas if not scenario.only_days or int(p.day) in scenario.only_days]
    out: list[Persona] = []
    for p in pool:
        m = effects.traffic(p.arrival_hour)
        rng = random.Random(stable_seed(seed, "scenario-traffic", p.id))
        copies = math.floor(m) + (1 if rng.random() < m - math.floor(m) else 0)
        budget = {}
        if effects.budget != 1.0:
            budget = {"budget_min": int(round(p.budget_min * effects.budget)), "budget_max": int(round(p.budget_max * effects.budget))}
        for k in range(copies):
            out.append(p.model_copy(update={**budget, **({"id": f"{p.id}~s{k}"} if k else {})}))
    return out
