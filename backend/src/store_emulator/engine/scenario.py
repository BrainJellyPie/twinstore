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
from pathlib import Path

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
    ScenarioPriors,
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
    # Not "frozen", "cream" or "bar": those put frozen pizza, cream cheese and candy bars in the ice
    # cream aisle (frozen pizza sold 1.9× in a simulated summer; real: 0.94×, research/validation).
    "ice_cream": frozenset({"ice", "icecream", "popsicle", "popsicles", "gelato", "sorbet", "sherbet", "sherbets", "cone",
                            "sherbts", "아이스", "아이스크림", "빙과"}),
    "snacks": frozenset({"snack", "chip", "chips", "crisps", "cookie", "cookies", "candy", "chocolate", "cracker",
                         "jerky", "nut", "nuts", "popcorn", "gum", "과자", "스낵", "초콜릿", "사탕", "젤리"}),
    "meals": frozenset({"sandwich", "lunch", "rice", "kimbap", "bento", "burger", "wrap", "salad", "pizza", "meal",
                        "dinner", "entree",
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
    """Words of a label, plus their singular ("Soft Drinks" must match "drink", "Snacks" "snack")."""
    words = {t for t in re.split(r"[^\w]+", text.lower()) if t}
    return words | {w[:-1] for w in words if len(w) > 3 and w.endswith("s") and not w.endswith("ss")}


def item_categories(rack: Rack, item: SlotItem) -> set[str]:
    words = _tokens(f"{rack.rack_name} {rack.rack_desc} {item.name}")
    return {cat for cat, vocab in CATEGORY_WORDS.items() if words & vocab}


def words_categories(text: str) -> set[str]:
    words = _tokens(text)
    return {cat for cat, vocab in CATEGORY_WORDS.items() if words & vocab}


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
    # Ratio of the share of trips that need each category (ScenarioPriors.need_ratio), 1 = unchanged.
    need: dict[str, float] = field(default_factory=dict[str, float])
    # Per part of the day ("morning", "evening"): demand multipliers and need ratios, applied per shopper
    # by arrival hour (ScenarioPriors.hour_demand, need_ratio "hour:…").
    hour_demand: dict[str, dict[str, float]] = field(default_factory=dict[str, dict[str, float]])
    hour_need: dict[str, dict[str, float]] = field(default_factory=dict[str, dict[str, float]])
    # Trip size multiplier of the situation, and per part of the day (ScenarioPriors.size_ratio).
    size: float = 1.0
    hour_size: dict[str, float] = field(default_factory=dict[str, float])

    def hour_for(self, hour: int, categories: set[str]) -> float:
        """Demand multiplier of the visit's part of the day, clipped to [0.2, 3]."""
        table = self.hour_demand.get(part_of_day(hour))
        if not table:
            return 1.0
        m = 1.0
        for cat in categories:
            m *= table.get(cat, 1.0)
        return min(3.0, max(0.2, m))

    def hour_need_for(self, hour: int, categories: set[str]) -> float:
        table = self.hour_need.get(part_of_day(hour))
        ratios = [table[c] for c in sorted(categories) if c in table] if table else []
        if 0.0 in ratios:
            return 0.0
        return max(ratios, key=lambda r: abs(math.log(r)) if r > 0 else 0.0) if ratios else 1.0

    def need_for(self, categories: set[str]) -> float:
        """Strongest need ratio; equal strengths use category order for reproducible draws."""
        ratios = [self.need[c] for c in sorted(categories) if c in self.need]
        if 0.0 in ratios:
            return 0.0
        return max(ratios, key=lambda r: abs(math.log(r)) if r > 0 else 0.0) if ratios else 1.0

    def traffic(self, hour: int) -> float:
        return self.base_traffic * self.traffic_by_hour.get(hour, 1.0)

    def demand_for(self, categories: set[str]) -> float:
        """Product of the multipliers of every category the item belongs to, clipped to [0.2, 3]."""
        m = 1.0
        for cat in categories:
            m *= self.demand.get(cat, 1.0)
        return min(3.0, max(0.2, m))


def _stochastic_round(x: float, rng: random.Random) -> int:
    return math.floor(x) + (1 if rng.random() < x - math.floor(x) else 0)


def scale_trip(p: Persona, fx: ScenarioEffects, hour: int, seed: int) -> Persona:
    """A trip sized from receipts (Persona.basket_size > 0), resized by the situation and the part of
    the day (ScenarioPriors.size_ratio); its number of categories moves with it. Identity otherwise."""
    size = fx.size * fx.hour_size.get(part_of_day(hour), 1.0)
    if p.basket_size <= 0 or size == 1.0:
        return p
    rng = random.Random(stable_seed(seed, "trip-size"))
    items = max(1, _stochastic_round(p.basket_size * size, rng))
    update: dict[str, int] = {"basket_size": items}
    if p.basket_kinds > 0:
        update["basket_kinds"] = min(items, max(1, _stochastic_round(p.basket_kinds * size, rng)))
    return p.model_copy(update=update)


def part_of_day(hour: int) -> str:
    return "morning" if hour < 12 else "evening" if hour >= 17 else "midday"


def hour_effects(p: ScenarioPriors, fx: ScenarioEffects | None = None) -> ScenarioEffects:
    """The part-of-day tables of a format's priors, on `fx` (a fresh ScenarioEffects without one)."""
    fx = fx or ScenarioEffects()
    fx.hour_demand = {k: dict(v) for k, v in p.hour_demand.items()}
    fx.hour_need = {k.removeprefix("hour:"): dict(v) for k, v in p.need_ratio.items() if k.startswith("hour:")}
    fx.hour_size = {k.removeprefix("hour:"): v for k, v in p.size_ratio.items() if k.startswith("hour:")}
    return fx


def _mul(target: dict[str, float], updates: dict[str, float], power: float = 1.0) -> None:
    for k, v in updates.items():
        target[k] = target.get(k, 1.0) * (v ** power)


def _clip(v: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, v))


def _temperature_demand(t: float, p: ScenarioPriors) -> dict[str, float]:
    """Continuous temperature response (°C), centered on a mild day (`ScenarioPriors.temperature_*`)."""
    out: dict[str, float] = {}
    for cat, slope in p.temperature_slope.items():
        lo, hi = p.temperature_clip.get(cat, (0.3, 3.0))
        out[cat] = _clip(1 + slope * (t - p.temperature_pivot.get(cat, 20.0)), lo, hi)
    return out


# Store types whose shoppers behave like the supermarket, drugstore and grocery data the grocery
# profile was fitted on (research/validation: The Complete Journey, Favorita, M5, Rossmann, Frat).
GROCERY_FORMATS: frozenset[str] = frozenset({"supermarket", "hypermarket", "grocery", "pharmacy", "drugstore",
                                             "mini_mart", "minimart"})
# Fitted to real data by research/validation/calibrate_situations.py (traffic: Rossmann weather, CJ and
# Favorita weekends and holidays, Rossmann/Favorita paydays; demand: The Complete Journey's
# per-trip category shares by season, weekend, holiday season and Super Bowl Sunday).
GROCERY_PRIORS = ScenarioPriors.model_validate_json((Path(__file__).with_name("grocery_priors.json")).read_text())


def priors_for(store_type: str, override: ScenarioPriors | None = None) -> ScenarioPriors:
    """The effect sizes for a store: an explicit override, else the grocery profile for grocery
    formats, else the convenience-store priors."""
    if override is not None:
        return override
    key = (store_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    return GROCERY_PRIORS if key in GROCERY_FORMATS else ScenarioPriors()


def compile_scenario(scenario: Scenario, priors: ScenarioPriors | None = None) -> ScenarioEffects:
    p = priors or ScenarioPriors()
    fx = ScenarioEffects()
    w = scenario.weather.value
    fx.base_traffic = scenario.traffic_multiplier * p.weather_traffic.get(w, 1.0) * p.day_traffic.get(scenario.day_type.value, 1.0)
    _mul(fx.demand, p.weather_demand.get(w, {}))
    if scenario.temperature_c is not None:
        # The temperature curve replaces the categorical heat/cold demand for the same categories.
        for cat, v in _temperature_demand(scenario.temperature_c, p).items():
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
    keys = [(f"weather:{w}", 1.0), (f"day:{scenario.day_type.value}", 1.0)]
    if scenario.season is not None:
        keys.append((f"season:{scenario.season.value}", 1.0))
    keys += [(f"event:{e.kind.value}", e.intensity) for e in scenario.events]
    for key, power in keys:
        _mul(fx.need, p.need_ratio.get(key, {}), power=power * p.need_power)
        fx.size *= p.size_ratio.get(key, 1.0) ** power
    return hour_effects(p, fx)


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


def apply_to_store(store: Store, scenario: Scenario) -> tuple[Store, dict[str, float]]:
    """Promotions change prices/labels, stock-outs empty the facings. Returns the new store and a
    sku → pick-probability lift for promoted items (used by the rule-based engine)."""
    lifts: dict[str, float] = {}
    priors = ScenarioPriors()
    catalog_skus = {item.sku.lower() for rack in store.racks for slot in rack.slots for item in slot.items}
    catalog_names = {item.name.lower() for rack in store.racks for slot in rack.slots for item in slot.items}
    rack_labels = {label.lower() for rack in store.racks for label in (rack.rack_name, rack.rack_desc)}

    def matches(target: str, rack: Rack, item: SlotItem) -> bool:
        t = target.strip().lower()
        if not t:
            return False
        if t in catalog_skus:
            return t == item.sku.lower()
        if t in catalog_names or t in rack_labels:
            return t == item.name.lower() or t in (rack.rack_name.lower(), rack.rack_desc.lower())
        if t in item.name.lower() or t in rack.rack_name.lower():
            return True
        return bool(_tokens(t) & _tokens(f"{rack.rack_name} {rack.rack_desc} {item.name}")) and len(t) >= 3

    racks: list[Rack] = []
    for rack in store.racks:
        slots: list[Slot] = []
        for slot in rack.slots:
            items: list[SlotItem] = []
            for item in slot.items:
                if any(matches(s, rack, item) for s in scenario.stockouts):
                    continue
                promo = next((pr for pr in scenario.promotions if matches(pr.target, rack, item)), None)
                if promo is not None:
                    price = item.price
                    if promo.kind == PromotionKind.DISCOUNT:
                        price = round(item.price * (1 - promo.discount_pct / 100))
                    label = promo.label or (f"{promo.discount_pct:.0f}% OFF" if promo.kind == PromotionKind.DISCOUNT
                                            else "SALE" if promo.kind == PromotionKind.FEATURED else promo.kind.value)
                    item = item.model_copy(update={"price": price, "promo": label})
                    lifts[item.sku] = priors.promo_lift.get(promo.kind.value, 1.2)
                items.append(item)
            slots.append(slot.model_copy(update={"items": items}))
        racks.append(rack.model_copy(update={"slots": slots}))
    return store.model_copy(update={"racks": racks}), lifts


def apply_to_personas(
    personas: list[Persona], scenario: Scenario, effects: ScenarioEffects, *, seed: int, scale_traffic: bool = True,
) -> list[Persona]:
    """Day filter, traffic scaling per hour (thinning / seeded clones) and budget scaling. (Trip size
    is scaled per customer by the simulator: `scale_trip`.)

    Original personas keep their ids, so a scenario run stays paired with a baseline run on the
    same seed; clones use the first available "<id>~s<k>" ids.
    """
    pool = [p for p in personas if not scenario.only_days or int(p.day) in scenario.only_days]
    used_ids = {p.id for p in personas}
    out: list[Persona] = []
    for p in pool:
        m = effects.traffic(p.arrival_hour) if scale_traffic else 1.0
        rng = random.Random(stable_seed(seed, "scenario-traffic", p.id))
        copies = math.floor(m) + (1 if rng.random() < m - math.floor(m) else 0)
        update: dict[str, int] = {}
        if effects.budget != 1.0:
            # Zero means unlimited, so a positive spending cap cannot round down to zero.
            cap = max(1, round(p.budget_max * effects.budget)) if p.budget_max > 0 else 0
            update = {"budget_min": round(p.budget_min * effects.budget), "budget_max": cap}
        suffix = 1
        for k in range(copies):
            identifier = p.id
            if k:
                identifier = f"{p.id}~s{suffix}"
                while identifier in used_ids:
                    suffix += 1
                    identifier = f"{p.id}~s{suffix}"
                used_ids.add(identifier)
                suffix += 1
            out.append(p.model_copy(update={**update, "id": identifier}))
    return out
