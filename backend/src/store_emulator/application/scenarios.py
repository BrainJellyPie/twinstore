"""Scenario presets, scenarios written from a description, and applying a scenario to a run's inputs."""

import asyncio
import logging
import re

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
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
from store_emulator.domain.types import RESOURCE_ID_PATTERN
from store_emulator.engine.scenario import (
    apply_to_personas,
    apply_to_store,
    compile_scenario,
    priors_for,
)
from store_emulator.engine.scenario_writer import DescribedScenario, describe_scenario

from .errors import AppError, model_failure
from .providers import assistive_client
from .storage.setups import read_setup

logger = logging.getLogger(__name__)

PRESETS: list[Scenario] = [
    Scenario(id="baseline", name="Ordinary day", description="Mild weather, no events, normal crowding."),
    Scenario(id="rainy_commute", name="Rainy commute", weather=Weather.RAIN, temperature_c=14,
             description="Rain all day: fewer walk-ins, more hot food, umbrellas sell."),
    Scenario(id="heatwave_weekend", name="Heatwave weekend", weather=Weather.HEATWAVE, temperature_c=35,
             season=Season.SUMMER, day_type=DayType.WEEKEND,
             description="35 °C Saturday: cold drinks, water and ice cream surge; hot food drops."),
    Scenario(id="snowy_evening", name="Snowy evening", weather=Weather.SNOW, temperature_c=-3, season=Season.WINTER,
             hourly_traffic={17: 0.8, 18: 0.8, 19: 0.75, 20: 0.7},
             description="Snowfall: fewer visitors, hot food and ramen up, people stock up a little."),
    Scenario(id="cold_snap", name="Cold snap morning", weather=Weather.COLD_SNAP, temperature_c=-12,
             season=Season.WINTER, description="−12 °C: short trips, hot drinks and instant noodles."),
    Scenario(id="typhoon", name="Typhoon warning", weather=Weather.TYPHOON,
             description="Typhoon approaching: few visitors who buy water and ramen in bulk."),
    Scenario(id="fine_dust", name="Fine-dust alert", weather=Weather.FINE_DUST,
             description="Air-quality alert: masks and water, slightly fewer walk-ins."),
    Scenario(id="payday_friday", name="Payday Friday night", only_days=[5],
             events=[LocalEvent(kind=EventKind.PAYDAY, intensity=0.8)],
             hourly_traffic={18: 1.2, 19: 1.3, 20: 1.3, 21: 1.2},
             description="Payday: bigger budgets, beer and treats in the evening."),
    Scenario(id="exam_week", name="Exam week (campus)", events=[LocalEvent(kind=EventKind.EXAM_PERIOD, intensity=0.9)],
             hourly_traffic={21: 1.3, 22: 1.4, 23: 1.4},
             description="Students cramming: energy drinks, coffee and snacks late at night."),
    Scenario(id="big_match", name="Big match night", day_type=DayType.WEEKEND,
             events=[LocalEvent(kind=EventKind.SPORTS_MATCH, intensity=0.9, start_hour=17, end_hour=22)],
             description="Fans before kick-off: beer and snacks, evening rush."),
    Scenario(id="local_festival", name="Local festival", day_type=DayType.WEEKEND, crowding=Crowding.BUSY,
             events=[LocalEvent(kind=EventKind.FESTIVAL, intensity=0.8, start_hour=12, end_hour=22)],
             description="Street festival: crowds, drinks, snacks and impulse buys."),
    Scenario(id="holiday_season", name="Holiday season (Chuseok/Seollal)", day_type=DayType.HOLIDAY_SEASON,
             description="Family holiday: fewer regulars, gifts, desserts and alcohol."),
    Scenario(id="summer_vacation", name="Summer vacation", season=Season.SUMMER, day_type=DayType.SCHOOL_VACATION,
             temperature_c=29, description="Schools out: ice cream and snacks, quieter mornings."),
    Scenario(id="competitor_opens", name="Competitor opens next door",
             events=[LocalEvent(kind=EventKind.COMPETITOR_OPENING, intensity=0.8)],
             description="A new convenience store opened 50 m away."),
    Scenario(id="drink_1plus1", name="1+1 drink promotion",
             promotions=[Promotion(target="drink", kind=PromotionKind.ONE_PLUS_ONE)],
             description="Buy-one-get-one on the drink racks."),
    Scenario(id="snack_discount", name="Weekend snack sale", day_type=DayType.WEEKEND,
             promotions=[Promotion(target="snack", kind=PromotionKind.DISCOUNT, discount_pct=25)],
             description="25 % off every snack."),
    Scenario(id="supply_disruption", name="Supply disruption", stockouts=["water", "ramen", "noodle"],
             description="Water and instant noodles out of stock."),
    Scenario(id="lunch_rush", name="Packed lunch rush", crowding=Crowding.PACKED,
             hourly_traffic={11: 1.4, 12: 1.7, 13: 1.5},
             description="Office lunch peak with a queue: quick trips, walk-outs."),
    Scenario(id="night_market", name="Night market",
             events=[LocalEvent(kind=EventKind.NIGHT_MARKET, intensity=0.8, start_hour=18, end_hour=24)],
             music="upbeat", lighting="bright", description="Evening street market, upbeat music, bright store."),
]

_BY_ID = {s.id: s for s in PRESETS}


def get_preset(scenario_id: str) -> Scenario | None:
    return _BY_ID.get(scenario_id)


def prepare_inputs(
    config: SimulationConfig, store: Store, personas: list[Persona], *, traffic_applied: bool = False,
) -> tuple[Store, list[Persona]]:
    """Apply operating hours and the run's scenario: promotions/stock-outs, day filter, traffic and
    visitor budgets. `traffic_applied` skips the
    traffic scaling when the visitors already came from a demand model that included it."""
    scenario = config.scenario
    if scenario is not None:
        effects = compile_scenario(scenario, priors_for(store.type, config.scenario_priors))
        store, _ = apply_to_store(store, scenario)
        personas = apply_to_personas(personas, scenario, effects, seed=config.seed, scale_traffic=not traffic_applied)
    if store.weekly_schedule:
        personas = [person for person in personas if store.is_open_at(person.day, person.arrival_hour)]
    return store, personas


# ── a situation described in words ───────────────────────────────────────────────

class DescribeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=3, max_length=800, description="the day in plain words")
    project_id: str = Field(default="", description="with setup_id: ground promotions and stock-outs in that store")
    setup_id: str = ""
    model: str = Field(default="", description='model reference; "" = the app text model')


def _store_for(project_id: str, setup_id: str) -> Store | None:
    if not project_id or not setup_id:
        return None
    if not re.fullmatch(RESOURCE_ID_PATTERN, project_id) or not re.fullmatch(RESOURCE_ID_PATTERN, setup_id):
        raise AppError("invalid project or layout id", 400)
    try:
        data = read_setup(project_id, setup_id).get("store")
    except FileNotFoundError:
        raise AppError(f"layout not found: {setup_id}", 404) from None
    return Store.model_validate(data) if data else None


def describe(req: DescribeRequest, config: SimulationConfig) -> DescribedScenario:
    """A custom scenario written by the text model from the description, checked against the store's products."""
    store = _store_for(req.project_id, req.setup_id)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 1200})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(describe_scenario(llm, req.text, store, [p.name for p in PRESETS]))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[scenarios] describe failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The situation could not be set up"), 502) from e
