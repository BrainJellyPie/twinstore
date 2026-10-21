"""A vision judge must honor cancellation inside its rule-based candidate search."""

import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.optimize import JudgeSpec, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import SimulationSummary
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator
from store_emulator.engine.optimize.judge import OptimizationCanceled, judge_layout_search
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine


@pytest.mark.parametrize("algorithm", ["hill_climb", "anneal", "genetic"])
def test_vision_candidate_search_stops_before_evaluating_more_layouts(monkeypatch, algorithm):
    store = generate_store("mini_mart")
    panel = [Persona(id="p0", identity="Shopper", age_group="20s", gender="Female",
                     description="Tea", intent="tea", purpose="tea")]
    config = SimulationConfig(engine_type=EngineType.RULE_BASED)
    pathfinder = AStarPathFinder()
    calls = 0

    async def evaluate(self, layout):
        nonlocal calls
        calls += 1
        return 100.0, SimulationSummary(store_id=layout.id, revenue_per_visitor=100)

    async def unexpected_vision(self, layout):
        pytest.fail("A canceled search must not start vision judging")

    monkeypatch.setattr(LayoutEvaluator, "evaluate", evaluate)
    monkeypatch.setattr(LayoutEvaluator, "simulate", unexpected_vision)
    with pytest.raises(OptimizationCanceled):
        asyncio.run(judge_layout_search(
            store, OptimizeSpec(algorithm=algorithm, budget=6, eval_customers=20),
            JudgeSpec(judge="vlm", vlm_customers=4, top_k=1, calibrate=False),
            surrogate_config=config, vlm_config=config, vlm_engine=build_engine(config, pathfinder=pathfinder),
            search_personas=panel, vlm_personas=panel, cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS,
            pathfinder=pathfinder, should_stop=lambda: calls >= 2,
        ))
    assert calls == 2
