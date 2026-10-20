"""Scenario presets and applying a scenario to a run's inputs (store and visitors)."""

from store_emulator.domain.config import SimulationConfig
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
from store_emulator.engine.scenario import apply_to_personas, apply_to_store, compile_scenario

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


def prepare_inputs(config: SimulationConfig, store: Store, personas: list[Persona]) -> tuple[Store, list[Persona]]:
    """Apply the run's scenario: promotions/stock-outs to the store, day filter, traffic and
    budgets to the visitors. Identity when the run has no scenario."""
    scenario = config.scenario
    if scenario is None:
        return store, personas
    effects = compile_scenario(scenario)
    store, _ = apply_to_store(store, scenario)
    personas = apply_to_personas(personas, scenario, effects, seed=config.seed)
    return store, personas
