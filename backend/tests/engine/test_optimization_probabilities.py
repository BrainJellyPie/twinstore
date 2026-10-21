"""A tied bootstrap outcome is not an improvement when minimizing walking distance."""

import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.optimize import JudgeSpec, OptimizeObjective, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, SimulationSummary
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, store_fingerprint
from store_emulator.engine.optimize.judge import judge_layout_search
from store_emulator.engine.optimize.search import optimize
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine


@pytest.mark.parametrize("judge_kind", ["rule", "vlm"])
@pytest.mark.parametrize("variant_walks,probability", [([5, 5], 0), ([4, 6], 0.25), ([4, 4], 1), ([6, 6], 0)])
def test_minimizing_probability_excludes_ties(monkeypatch, judge_kind, variant_walks, probability):
    store = generate_store("mini_mart")
    baseline = store_fingerprint(store)
    personas = [Persona(id=f"p{i}", identity="Shopper", age_group="20s", gender="Female",
                        description="Buys tea", intent="tea", purpose="tea") for i in range(2)]
    config = SimulationConfig(engine_type=EngineType.RULE_BASED)
    pathfinder = AStarPathFinder()
    spec = OptimizeSpec(objective=OptimizeObjective.WALKING_DISTANCE, budget=1,
                        eval_customers=10, validation_customers=2)

    async def evaluate(self, layout):
        score = 10 if store_fingerprint(layout) == baseline else 5
        return score, SimulationSummary(store_id=layout.id, avg_path_tiles=score)

    async def customers(self, layout, panel, *, replicate):
        walks = [5, 5] if store_fingerprint(layout) == baseline else variant_walks
        return [CustomerResult(
            persona_id=persona.id, day=Weekday.MON, arrival_time="12:00:00",
            timeline=[TimelineEvent(elapsed_sec=i, x=i, y=0, action=Action.MOVE) for i in range(count)],
        ) for persona, count in zip(panel, walks, strict=True)]

    async def simulate(self, layout):
        outcomes = await customers(self, layout, personas, replicate=0)
        score = sum(len(c.timeline) for c in outcomes) / len(outcomes)
        summary = SimulationSummary(store_id=layout.id, total_customers=2, avg_path_tiles=score)
        return score, AggregatedResult(summary=summary, pathcalc_heatmap=[], persona_heatmap=[]), outcomes

    monkeypatch.setattr(LayoutEvaluator, "evaluate", evaluate)
    monkeypatch.setattr(LayoutEvaluator, "evaluate_customers", customers)
    monkeypatch.setattr(LayoutEvaluator, "simulate", simulate)

    if judge_kind == "rule":
        evaluator = LayoutEvaluator(config, personas, sample_cue, BEHAVIOR_PATTERNS, pathfinder, spec.objective)
        result = asyncio.run(optimize(store, spec, evaluator))
        assert result.validation is not None
        actual = result.validation_prob_better
    else:
        result = asyncio.run(judge_layout_search(
            store, spec, JudgeSpec(judge="vlm", top_k=1, calibrate=False, vlm_customers=4),
            surrogate_config=config, vlm_config=config, vlm_engine=build_engine(config, pathfinder=pathfinder),
            search_personas=personas, vlm_personas=personas, cue_sampler=sample_cue,
            patterns=BEHAVIOR_PATTERNS, pathfinder=pathfinder, model_label="scripted",
        ))
        assert result.judge is not None and len(result.judge.candidates) == 2
        actual = result.judge.candidates[1].prob_better
    assert actual == pytest.approx(probability, abs=0.03)
