import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.optimize import JudgeSpec, OptimizeConstraints, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, SimulationSummary
from store_emulator.domain.types import Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, store_fingerprint
from store_emulator.engine.optimize.judge import judge_layout_search
from store_emulator.engine.optimize.search import optimize
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine


@pytest.mark.parametrize("kind", ["rule", "vlm"])
@pytest.mark.parametrize("threshold", [0, 0.05, 0.2])
@pytest.mark.parametrize("baseline_score", [0, 100])
def test_improvement_threshold_and_validation_respect_the_baseline(monkeypatch, kind, threshold, baseline_score):
    store = generate_store("mini_mart")
    baseline = store_fingerprint(store)
    personas = [Persona(id=f"p{i}", identity="Shopper", age_group="20s", gender="Female",
                        description="Tea", intent="tea", purpose="tea") for i in range(2)]
    config = SimulationConfig(engine_type=EngineType.RULE_BASED)
    pathfinder = AStarPathFinder()
    spec = OptimizeSpec(budget=1, eval_customers=10, validation_customers=2,
                        constraints=OptimizeConstraints(min_improvement=threshold))

    async def evaluate(self, layout):
        score = baseline_score if store_fingerprint(layout) == baseline else baseline_score + 10
        return score, SimulationSummary(store_id=layout.id, total_customers=2, total_revenue=2 * score,
                                        revenue_per_visitor=score)

    async def customers(self, layout, panel, *, replicate):
        score, _ = await evaluate(self, layout)
        return [CustomerResult(persona_id=p.id, day=Weekday.MON, arrival_time="12:00:00", total_spent=score)
                for p in panel]

    async def simulate(self, layout):
        score, summary = await evaluate(self, layout)
        result = AggregatedResult(summary=summary, pathcalc_heatmap=[], persona_heatmap=[])
        return score, result, await customers(self, layout, personas, replicate=0)

    monkeypatch.setattr(LayoutEvaluator, "evaluate", evaluate)
    monkeypatch.setattr(LayoutEvaluator, "evaluate_customers", customers)
    monkeypatch.setattr(LayoutEvaluator, "simulate", simulate)
    if kind == "rule":
        evaluator = LayoutEvaluator(config, personas, sample_cue, BEHAVIOR_PATTERNS, pathfinder, spec.objective)
        result = asyncio.run(optimize(store, spec, evaluator))
    else:
        result = asyncio.run(judge_layout_search(
            store, spec, JudgeSpec(judge="vlm", top_k=1, calibrate=False, vlm_customers=4),
            surrogate_config=config, vlm_config=config, vlm_engine=build_engine(config, pathfinder=pathfinder),
            search_personas=personas, vlm_personas=personas, cue_sampler=sample_cue,
            patterns=BEHAVIOR_PATTERNS, pathfinder=pathfinder, model_label="scripted",
        ))
    if baseline_score and threshold > 0.1:
        assert result.best_score == baseline_score
        assert result.applied_moves == []
        return
    assert result.best_score == baseline_score + 10
    assert result.applied_moves
    if baseline_score:
        assert result.validation_relative_improvement == pytest.approx(0.1)
    else:
        assert result.validation_relative_improvement is None
        assert any("absolute change from zero" in note for note in result.notes)
    assert result.validation_prob_better == 1
    assert not any("not better than the baseline" in n or "gain is likely noise" in n for n in result.notes)
