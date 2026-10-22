"""Optimizing for a situation walks every layout as the situation has it, and saves the layout without it."""

import asyncio
import json
from functools import partial
from pathlib import Path

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.application.scenarios import (
    get_preset,
    scenario_shoppers,
    scenario_store,
    who_can_come,
)
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.optimize.evaluate import (
    LayoutEvaluator,
    select_personas,
    store_fingerprint,
)
from store_emulator.engine.routing.pathfinder import AStarPathFinder

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"
STOCKED_OUT = ("water", "ramen", "noodle")


def _inputs() -> tuple[Store, list[Persona]]:
    store = Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))
    return store, [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]


def _stocked_out_units(customers) -> int:
    return sum(e.quantity for c in customers for e in c.purchases if any(w in e.product_name.lower() for w in STOCKED_OUT))


def test_the_optimizers_shoppers_find_the_situations_stock_outs():
    store, personas = _inputs()
    config = SimulationConfig(seed=2).model_copy(update={"engine_type": EngineType.RULE_BASED,
                                                         "scenario": get_preset("supply_disruption")})
    panel = select_personas(scenario_shoppers(config, store, personas), 400, seed=2)

    def evaluator(prepare=None) -> LayoutEvaluator:
        return LayoutEvaluator(config, panel, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(),
                               OptimizeObjective.REVENUE_PER_VISITOR, prepare_store=prepare)

    plain = asyncio.run(evaluator().evaluate_customers(store, panel))
    situated_evaluator = evaluator(partial(scenario_store, config))
    situated = asyncio.run(situated_evaluator.evaluate_customers(store, panel))
    assert _stocked_out_units(plain) > 0 and _stocked_out_units(situated) == 0
    # The layout itself, and its cache key, keep the shelves stocked: the saved layout has no stock-outs in it.
    asyncio.run(situated_evaluator.evaluate(store))
    assert store_fingerprint(store) in situated_evaluator._cache  # pyright: ignore[reportPrivateUsage]
    assert store.model_dump() == _inputs()[0].model_dump()


def test_a_capped_run_samples_from_the_situations_days():
    store, personas = _inputs()
    config = SimulationConfig(seed=1).model_copy(update={"scenario": get_preset("payday_friday")})
    pool = who_can_come(config, store, personas)
    assert pool and all(int(p.day) == 5 for p in pool)
