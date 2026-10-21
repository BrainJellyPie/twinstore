"""Knobs added for real-data calibration: traffic profile, assortment store, basket size."""

import asyncio
import random
from collections import Counter

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.application.supplemental import traffic_from_supplemental
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.generators.traffic_profile import (
    TrafficProfile,
    assign_visit_times,
    fit_traffic_profile,
    reshape_hourly_counts,
)
from store_emulator.engine.layout_gen.assortment import (
    AssortmentCategory,
    generate_assortment_store,
)
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance.prompt import (
    plan_system_prompt,
)
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner


def test_fit_profile_keeps_closed_hours_closed() -> None:
    visits = [(1, 9)] * 3 + [(6, 15)] * 5
    prof = fit_traffic_profile(visits, smoothing=0.5)
    hours = {h for _, h, _ in prof.cells()}
    assert hours == {9, 15}
    assert abs(prof.weights[6][15] - 5.5) < 1e-9
    assert abs(prof.weights[3][9] - 0.5) < 1e-9  # smoothed, still open
    assert abs(sum(prof.weekday_shares().values()) - 1.0) < 1e-9


def _persona(pid: str, **kw: object) -> Persona:
    base: dict[str, object] = {"id": pid, "identity": "household", "age_group": "40s", "gender": "Female",
                               "description": "", "intent": "groceries", "purpose": "groceries"}
    return Persona.model_validate(base | kw)


def test_assign_visit_times_reproduces_profile_shape() -> None:
    prof = TrafficProfile(weights={1: {9: 1.0}, 6: {15: 3.0}})
    personas = [_persona(f"p{i}") for i in range(100)]
    out = assign_visit_times(personas, prof, seed=1)
    counts = Counter((int(p.day), p.arrival_hour) for p in out)
    assert counts == {(1, 9): 25, (6, 15): 75}           # stratified, not i.i.d.
    assert [p.id for p in out] == [p.id for p in personas]
    again = assign_visit_times(personas, prof, seed=1)
    assert [(p.day, p.arrival_hour) for p in again] == [(p.day, p.arrival_hour) for p in out]
    assert assign_visit_times(personas, TrafficProfile()) == personas  # empty profile: unchanged


def _store():
    cats = [
        AssortmentCategory(key="milk", label="Milk", storage="fridge", items=[(f"Milk {i}", 300 + i) for i in range(6)]),
        AssortmentCategory(key="bread", label="Bread", storage="shelf", items=[(f"Bread {i}", 250 + i) for i in range(6)]),
        AssortmentCategory(key="snacks", label="Snacks", storage="shelf", items=[(f"Chips {i}", 199 + i) for i in range(6)]),
        AssortmentCategory(key="ice", label="Ice cream", storage="freezer", items=[(f"Ice {i}", 499 + i) for i in range(6)]),
    ]
    return generate_assortment_store(cats, store_id="t", name="T")


def test_assortment_store_places_every_item() -> None:
    store = _store()
    names = {item.name for rack in store.product_racks for slot in rack.slots for item in slot.items}
    assert len(names) == 24
    assert {rack.rack_desc for rack in store.product_racks} >= {"milk", "bread", "snacks", "ice"}
    assert store.type == "supermarket"


async def _lines(config: SimulationConfig, n: int = 40) -> tuple[float, float]:
    store = _store()
    pf = AStarPathFinder()
    engine = build_engine(config, llm=None, pathfinder=pf)
    runner = PerCustomerSimulationRunner(config, engine, pf, sample_cue, BEHAVIOR_PATTERNS)
    personas = [_persona(f"c{i}", day=Weekday.SAT, arrival_hour=15, budget_max=20000,
                         preferred_categories=["Milk", "Bread", "Snacks", "Ice cream"]) for i in range(n)]
    _, customers = await runner.run(store, personas, max_concurrent=4)
    buys = [[e for e in c.timeline if e.action == Action.BUY] for c in customers]
    bought = [b for b in buys if b]
    lines = sum(len({e.product_sku for e in b}) for b in bought) / max(1, len(bought))
    units = sum(sum(e.quantity for e in b) for b in bought) / max(1, sum(len(b) for b in bought))
    return lines, units


def test_basket_knobs_grow_baskets() -> None:
    base = SimulationConfig(engine_type=EngineType.RULE_BASED, seed=3)
    lines0, units0 = asyncio.run(_lines(base))
    big = base.model_copy(update={"basket_scale": 3.0})
    big.engines.rule_based = big.engines.rule_based.model_copy(update={"items_per_category": 2.5, "multi_unit_prob": 0.5})
    lines1, units1 = asyncio.run(_lines(big))
    assert lines1 > lines0 + 1.0
    assert units1 > units0


def test_plan_prompt_names_store_kind_and_size_hint() -> None:
    small = plan_system_prompt(max_items=3, image=False, store_type="convenience")
    large = plan_system_prompt(max_items=12, image=False, store_type="supermarket")
    assert "convenience store" in small and "supermarket" in large
    assert "quick stop" in large and "quick stop" not in small


def test_reshape_hourly_counts_follows_profile_and_keeps_closed_hours() -> None:
    prof = TrafficProfile(weights={d: {9: 1.0, 15: 3.0, 22: 5.0} for d in range(1, 8)})
    out = reshape_hourly_counts({9: 10, 15: 10, 16: 0}, prof, 3)
    assert set(out) == {9, 15, 16}          # 22 is closed in this schedule: never added
    assert out == {9: 5, 15: 15, 16: 0}     # 20 visitors split 1:3


def test_traffic_from_pos_export_counts_baskets() -> None:
    import io

    rng = random.Random(0)
    rows = ["receipt_id,timestamp,product,price"]
    for i in range(300):
        hour = 17 if i % 3 else 9
        ts = f"2026-03-{2 + i % 7:02d} {hour:02d}:{rng.randint(0, 59):02d}:00"
        for k in range(1 + i % 3):                      # several lines per basket
            rows.append(f"r{i},{ts},item{k},1.5")
    data = io.StringIO("\n".join(rows)).getvalue().encode()
    prof = traffic_from_supplemental(data, "pos.csv")
    assert prof is not None
    shares = prof.hour_shares()
    assert abs(shares[17] - 2 / 3) < 0.02 and abs(shares[9] - 1 / 3) < 0.02   # per basket, not per line
    assert traffic_from_supplemental(b"a,b\n1,2\n", "x.csv") is None


async def _baskets(config: SimulationConfig, size: int, n: int = 20) -> list[int]:
    store = _store()
    pf = AStarPathFinder()
    engine = build_engine(config, llm=None, pathfinder=pf)
    runner = PerCustomerSimulationRunner(config, engine, pf, sample_cue, BEHAVIOR_PATTERNS)
    personas = [_persona(f"s{i}", day=Weekday.SAT, arrival_hour=15, budget_max=50000, basket_size=size,
                         preferred_categories=["Milk", "Bread", "Snacks", "Ice cream"]) for i in range(n)]
    _, customers = await runner.run(store, personas, max_concurrent=4)
    return [len({e.product_sku for e in c.timeline if e.action == Action.BUY and e.origin == "planned"}) for c in customers]


def test_basket_size_sets_the_planned_trip_size() -> None:
    config = SimulationConfig(engine_type=EngineType.RULE_BASED, seed=5)
    config.engines.rule_based = config.engines.rule_based.model_copy(update={"walkout_prob": 0.0})
    assert asyncio.run(_baskets(config, 9)) == [9] * 20     # beyond any pattern cap, list reused round by round
    assert asyncio.run(_baskets(config, 1)) == [1] * 20


def test_plan_prompt_states_basket_size() -> None:
    from store_emulator.application.presets.behavior import (
        BEHAVIOR_PATTERNS as patterns,
    )
    from store_emulator.engine.simulation.engines.vlm_glance.prompt import (
        plan_user_prompt,
    )

    cue = sample_cue(random.Random(0))
    text = plan_user_prompt(_persona("p", basket_size=7), cue, patterns[0], day=Weekday.MON, hour=9,
                            situation="", budget=None, currency="USD", directory="Milk: ...")
    assert "about 7 different items" in text
    plain = plan_user_prompt(_persona("p"), cue, patterns[0], day=Weekday.MON, hour=9,
                             situation="", budget=None, currency="USD", directory="Milk: ...")
    assert "different item" not in plain


def test_plan_prompt_lists_usual_products() -> None:
    from store_emulator.application.presets.behavior import (
        BEHAVIOR_PATTERNS as patterns,
    )
    from store_emulator.engine.simulation.engines.vlm_glance.prompt import (
        plan_user_prompt,
    )

    text = plan_user_prompt(_persona("p", usual_products=["Bag of Organic Bananas", "Sour Cream"]), sample_cue(random.Random(0)),
                            patterns[0], day=Weekday.MON, hour=9, situation="", budget=None, currency="USD",
                            directory="Milk: ...")
    assert "Products they usually buy: Bag of Organic Bananas, Sour Cream" in text


def test_rule_planner_prefers_usual_products() -> None:
    config = SimulationConfig(engine_type=EngineType.RULE_BASED, seed=5)
    config.engines.rule_based = config.engines.rule_based.model_copy(update={"walkout_prob": 0.0, "habit_prob": 1.0})
    store = _store()
    pf = AStarPathFinder()
    engine = build_engine(config, llm=None, pathfinder=pf)
    runner = PerCustomerSimulationRunner(config, engine, pf, sample_cue, BEHAVIOR_PATTERNS)
    personas = [_persona(f"u{i}", day=Weekday.SAT, arrival_hour=15, budget_max=50000, basket_size=1,
                         preferred_categories=["Milk"], usual_products=["Milk 4"]) for i in range(10)]
    _, customers = asyncio.run(runner.run(store, personas, max_concurrent=4))
    planned = [e.product_name for c in customers for e in c.timeline if e.action == Action.BUY and e.origin == "planned"]
    assert planned == ["Milk 4"] * 10
