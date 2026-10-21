"""A situation described in plain words, turned into the simulator's `Scenario` by a language model.

"Rainy Friday evening, a baseball game at the stadium next door, 1+1 on Pepsi, and we ran out of ice" becomes
rain, Friday only, a sports match in the evening, a 1+1 promotion on Pepsi and a stock-out of ice. Promotions and
stock-outs are checked against the store's own products; targets that match nothing are dropped and reported, so
the run never silently ignores part of the description.
"""

from collections import Counter
from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, Field

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
from store_emulator.engine.scenario import apply_to_store

MAX_LISTED_PRODUCTS = 150


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Event(BaseModel):
    kind: EventKind
    intensity: float = Field(default=0.6, ge=0.0, le=1.0, description="0.3 small, 0.6 typical, 1.0 huge")
    start_hour: int = Field(default=0, ge=0, le=23)
    end_hour: int = Field(default=24, ge=1, le=24)
    note: str = Field(default="", max_length=120)


class _Promotion(BaseModel):
    target: str = Field(min_length=1, max_length=80,
                        description="a product name, a word from product names, or a shelf name, as listed")
    kind: PromotionKind = PromotionKind.DISCOUNT
    discount_pct: float = Field(default=20.0, ge=0.0, le=90.0)
    label: str = Field(default="", max_length=24, description="shelf tag text, e.g. '1+1' or '20% OFF'")


class ScenarioDraft(BaseModel):
    name: str = Field(max_length=60, description="a short name for the situation, e.g. 'Rainy match night'")
    weather: Weather = Weather.CLEAR
    temperature_c: float | None = Field(default=None, ge=-30.0, le=45.0)
    season: Season | None = None
    day_type: DayType = DayType.WEEKDAY
    only_days: list[int] = Field(default_factory=list[int], max_length=7,
                                 description="weekdays the situation applies to, 1 = Monday … 7 = Sunday; empty = every day")
    crowding: Crowding = Crowding.NORMAL
    traffic_multiplier: float = Field(default=1.0, ge=0.0, le=5.0,
                                      description="extra traffic beyond what weather and events imply; 1 = none")
    events: list[_Event] = Field(default_factory=list[_Event], max_length=4)
    promotions: list[_Promotion] = Field(default_factory=list[_Promotion], max_length=8)
    stockouts: list[str] = Field(default_factory=list[str], max_length=8,
                                 description="products or shelves that are out of stock, as listed")
    budget_multiplier: float = Field(default=1.0, ge=0.2, le=3.0)
    music: Literal["none", "calm", "upbeat"] = "none"
    lighting: Literal["dim", "normal", "bright"] = "normal"
    notes: str = Field(default="", max_length=400, description=(
        "what the description says that the fields cannot express, as one or two sentences of context for shoppers"))


class DescribedScenario(BaseModel):
    scenario: Scenario
    warnings: list[str] = []


WRITER_PROMPT = """You set up a store simulator from a store manager's description of a trading day. Fill in the
situation settings the description states or clearly implies, and leave everything else at its default (clear weather,
weekday, normal crowding, multipliers of 1, no events, promotions or stock-outs). Do not invent promotions, events or
stock-outs the description does not mention.

- Weather, temperature, season, day type and weekday: from the words used ("scorching" is a heatwave, "Friday" is
  only_days [5], "long weekend" is a public holiday).
- Events: pick the closest kind, with hours when the description gives a time of day (evening is about 17 to 22).
- Promotions and stock-outs must point at products or shelves from the store's list below; use the listed name or a
  word that appears in it. A deal like "1+1" or "buy one get one" is kind "1+1"; "20 % off" is a discount of 20.
- Put anything else that matters to shoppers (a nearby office lunch rush, a heat advisory) into notes.
Write in English."""


def _store_text(store: Store) -> str:
    racks = [r for r in store.product_racks if r.slots]
    names = list(dict.fromkeys(i.name for r in racks for s in r.slots for i in s.items))
    shown = names[:MAX_LISTED_PRODUCTS]
    more = f" (and {len(names) - len(shown)} more)" if len(names) > len(shown) else ""
    return (f"Shelves: {', '.join(dict.fromkeys(r.rack_name for r in racks))}\n"
            f"Products: {'; '.join(shown)}{more}")


def matched_skus(store: Store, target: str) -> set[str]:
    """SKUs a promotion or stock-out target reaches, exactly as a run would apply it."""
    before = Counter(i.sku for r in store.racks for s in r.slots for i in s.items)
    after, _ = apply_to_store(store, Scenario(stockouts=[target]))
    remaining = Counter(i.sku for r in after.racks for s in r.slots for i in s.items)
    return set(before - remaining)


def _reaches(store: Store, target: str, what: str, warnings: list[str]) -> bool:
    """Whether the target reaches any product; a target that reaches several is noted, since all of them change."""
    n = len(matched_skus(store, target))
    if n == 0:
        warnings.append(f'No product matches the {what} "{target}"; it was left out.')
    elif n > 1:
        warnings.append(f'The {what} "{target}" applies to {n} products.')
    return n > 0


def to_scenario(draft: ScenarioDraft, description: str, store: Store | None) -> DescribedScenario:
    """The draft as a custom `Scenario`; targets that reach no product of this store are dropped and reported."""
    warnings: list[str] = []
    promotions: list[Promotion] = []
    for p in draft.promotions:
        if store is not None and not _reaches(store, p.target, "promotion target", warnings):
            continue
        promotions.append(Promotion(target=p.target, kind=p.kind, discount_pct=p.discount_pct, label=p.label))
    stockouts: list[str] = []
    for target in dict.fromkeys(t.strip() for t in draft.stockouts if t.strip()):
        if store is not None and not _reaches(store, target, "stock-out", warnings):
            continue
        stockouts.append(target)
    events = [LocalEvent(kind=e.kind, intensity=e.intensity, start_hour=e.start_hour,
                         end_hour=e.end_hour if e.end_hour > e.start_hour else 24, note=e.note)
              for e in draft.events]
    scenario = Scenario(
        id="custom", name=draft.name.strip() or "Described situation", description=description.strip(),
        weather=draft.weather, temperature_c=draft.temperature_c, season=draft.season, day_type=draft.day_type,
        only_days=sorted({d for d in draft.only_days if 1 <= d <= 7}), crowding=draft.crowding,
        traffic_multiplier=draft.traffic_multiplier, events=events, promotions=promotions, stockouts=stockouts,
        budget_multiplier=draft.budget_multiplier, music=draft.music, lighting=draft.lighting, notes=draft.notes.strip(),
    )
    return DescribedScenario(scenario=scenario, warnings=warnings)


async def describe_scenario(
    llm: StructuredLLM, description: str, store: Store | None, examples: Sequence[str] = (),
) -> DescribedScenario:
    context = _store_text(store) if store is not None else "No store given: leave promotions and stock-outs empty."
    hint = f"\n\nPresets the user could also pick: {', '.join(examples)}" if examples else ""
    draft = await llm.generate_structured_async(
        ScenarioDraft, WRITER_PROMPT, f"Store:\n{context}{hint}\n\nDescription: {description.strip()}",
        max_retries=2, seed=0,
    )
    return to_scenario(draft, description, store)
