"""Scenarios: compiled effects, store/visitor transforms, and their direction in simulation."""

import asyncio
import json
from pathlib import Path

from store_emulator.application.config import local_config
from store_emulator.application.scenarios import PRESETS, get_preset, prepare_inputs
from store_emulator.application.simulation import (
    RunOptions,
    apply_options,
    run_simulation,
    subsample_personas,
)
from store_emulator.domain.config import EngineType
from store_emulator.domain.persona import Persona
from store_emulator.domain.scenario import (
    Crowding,
    EventKind,
    LocalEvent,
    Promotion,
    PromotionKind,
    Scenario,
    Weather,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action
from store_emulator.engine.scenario import (
    apply_to_personas,
    apply_to_store,
    compile_scenario,
    item_categories,
)

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


def _store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


def _personas() -> list[Persona]:
    return [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]


def test_presets_are_unique_and_compile():
    assert len({s.id for s in PRESETS}) == len(PRESETS) >= 15
    for s in PRESETS:
        fx = compile_scenario(s)
        assert fx.base_traffic > 0 and 0.2 <= fx.demand_for({"cold_drinks", "snacks"}) <= 3.0
        if s.id != "baseline":
            assert fx.situation, s.id


def test_weather_and_temperature_move_demand_the_right_way():
    hot = compile_scenario(Scenario(weather=Weather.HEATWAVE, temperature_c=35))
    cold = compile_scenario(Scenario(weather=Weather.COLD_SNAP, temperature_c=-10))
    assert hot.demand["cold_drinks"] > 1.3 and hot.demand["ice_cream"] > 1.5 and hot.demand["hot_food"] < 1
    assert cold.demand["hot_food"] > 1.3 and cold.demand["ice_cream"] < 0.6
    assert compile_scenario(Scenario(weather=Weather.TYPHOON)).base_traffic < 0.5
    packed = compile_scenario(Scenario(crowding=Crowding.PACKED))
    assert packed.dwell < 1 and packed.walkout > 1 and packed.impulse < 1


def test_events_apply_only_inside_their_hours_and_scale_with_intensity():
    fx = compile_scenario(Scenario(events=[LocalEvent(kind=EventKind.SPORTS_MATCH, intensity=1.0, start_hour=18, end_hour=21)]))
    assert fx.traffic(19) > 1.3 and fx.traffic(10) == 1.0
    weak = compile_scenario(Scenario(events=[LocalEvent(kind=EventKind.SPORTS_MATCH, intensity=0.2)]))
    strong = compile_scenario(Scenario(events=[LocalEvent(kind=EventKind.SPORTS_MATCH, intensity=1.0)]))
    assert 1.0 < weak.demand["alcohol"] < strong.demand["alcohol"]


def test_promotions_and_stockouts_change_the_store_not_the_input():
    store = _store()
    scenario = Scenario(promotions=[Promotion(target="Pepsi 20oz", kind=PromotionKind.DISCOUNT, discount_pct=50),
                                    Promotion(target="Snacks 1", kind=PromotionKind.ONE_PLUS_ONE)],
                        stockouts=["Sprite"])
    new, lifts = apply_to_store(store, scenario)
    old_items = {i.sku: i for r in store.racks for s in r.slots for i in s.items}
    new_items = {i.sku: i for r in new.racks for s in r.slots for i in s.items}
    pepsi = next(i for i in old_items.values() if i.name == "Pepsi 20oz")
    assert new_items[pepsi.sku].price == round(pepsi.price * 0.5) and "50%" in new_items[pepsi.sku].promo
    assert not any("Sprite" in i.name for i in new_items.values())
    assert any("Sprite" in i.name for i in old_items.values())          # input untouched
    snacks1 = {i.sku for r in new.racks if r.rack_name == "Snacks 1" for s in r.slots for i in s.items}
    assert snacks1 and all(new_items[s].promo == "1+1" for s in snacks1) and all(s in lifts for s in snacks1)


def test_traffic_scaling_is_deterministic_keeps_ids_and_filters_days():
    personas = _personas()[:600]
    busy = Scenario(traffic_multiplier=1.5, budget_multiplier=1.2)
    a = apply_to_personas(personas, busy, compile_scenario(busy), seed=1)
    b = apply_to_personas(personas, busy, compile_scenario(busy), seed=1)
    assert [p.id for p in a] == [p.id for p in b]
    assert 1.35 < len(a) / len(personas) < 1.65
    assert len({p.id for p in a}) == len(a)
    assert {p.id for p in personas} <= {p.id for p in a}
    first = next(p for p in a if p.id == personas[0].id)
    assert first.budget_max == round(personas[0].budget_max * 1.2)
    friday = Scenario(only_days=[5])
    assert {int(p.day) for p in apply_to_personas(personas, friday, compile_scenario(friday), seed=1)} <= {5}


def _cold_drink_units(scenario_id: str) -> float:
    cfg = apply_options(local_config(), RunOptions(engine_type=EngineType.RULE_BASED, seed=5, scenario_id=scenario_id))
    store0 = _store()
    personas = subsample_personas(_personas(), 400, cfg.seed)
    store, personas = prepare_inputs(cfg, store0, personas)
    _, customers, _ = asyncio.run(run_simulation(cfg, store, personas))
    cats = {i.sku: item_categories(r, i) for r in store0.racks for s in r.slots for i in s.items}
    units = sum(e.quantity for c in customers for e in c.timeline
                if e.action == Action.BUY and "cold_drinks" in cats.get(e.product_sku, set()))
    return units / max(1, len(customers))


def test_heatwave_sells_more_cold_drinks_than_an_ordinary_day():
    assert get_preset("heatwave_weekend") is not None
    assert _cold_drink_units("heatwave_weekend") > 1.15 * _cold_drink_units("baseline")


def test_grocery_formats_use_the_profile_fitted_to_real_data():
    from store_emulator.domain.scenario import Scenario, Weather
    from store_emulator.engine.scenario import (
        GROCERY_PRIORS,
        ScenarioPriors,
        compile_scenario,
        priors_for,
    )

    assert priors_for("supermarket") is GROCERY_PRIORS and priors_for("Pharmacy") is GROCERY_PRIORS
    assert priors_for("convenience") == ScenarioPriors()
    custom = ScenarioPriors(weather_traffic={"rain": 0.5})
    assert priors_for("supermarket", custom) is custom
    rain = Scenario(weather=Weather.RAIN)
    # Real grocery and drugstore traffic hardly moves with rain (Rossmann: −0.4 %); the convenience
    # priors assume −15 %.
    assert compile_scenario(rain, priors_for("supermarket")).base_traffic > 0.98
    assert compile_scenario(rain, priors_for("convenience")).base_traffic < 0.9


def test_part_of_day_demand_follows_the_shoppers_arrival_hour():
    from store_emulator.domain.config import SimulationConfig
    from store_emulator.engine.scenario import ScenarioPriors, compile_scenario, hour_effects, part_of_day
    from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine
    from store_emulator.engine.routing.pathfinder import AStarPathFinder

    assert [part_of_day(h) for h in (8, 11, 12, 16, 17, 22)] == ["morning", "morning", "midday", "midday",
                                                                  "evening", "evening"]
    priors = ScenarioPriors(hour_demand={"evening": {"alcohol": 2.0}, "morning": {"alcohol": 0.5}},
                            need_ratio={"hour:evening": {"alcohol": 1.8}})
    fx = hour_effects(priors)
    assert fx.hour_for(19, {"alcohol"}) == 2.0 and fx.hour_for(9, {"alcohol"}) == 0.5
    assert fx.hour_for(14, {"alcohol"}) == 1.0 and fx.hour_for(19, {"snacks"}) == 1.0
    assert fx.hour_need_for(19, {"alcohol"}) == 1.8 and fx.hour_need_for(9, {"alcohol"}) == 1.0
    # A scenario keeps the part-of-day tables of its priors.
    assert compile_scenario(Scenario(), priors).hour_for(20, {"alcohol"}) == 2.0
    # With no scenario the rule engine still takes them from the store format's profile.
    engine = RuleBasedEngine(AStarPathFinder(), SimulationConfig(scenario_priors=priors))
    engine.prepare(_store())
    assert engine._demand({"alcohol"}, 19) == 2.0 and engine._demand({"alcohol"}, 15) == 1.0  # pyright: ignore[reportPrivateUsage]
