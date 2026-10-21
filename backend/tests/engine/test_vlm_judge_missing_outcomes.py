"""Missing shopper results are not zero-cost journeys or evidence for a winning layout."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.optimize import JudgeSpec, OptimizeSpec, OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, SimulationSummary, RunDiagnostics, FailedCustomer
from store_emulator.domain.types import Weekday, Action
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize import judge
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, store_fingerprint
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine


@pytest.mark.parametrize("failure,calibrate", [
    ("baseline_empty", False), ("baseline_empty", True), ("candidate_empty", False),
    ("disjoint", False), ("candidate_zero_walk", False), ("complete", False),
])
def test_judge_requires_paired_results_but_allows_real_zero_outcomes(monkeypatch, failure, calibrate):
    store = generate_store("mini_mart")
    baseline = store_fingerprint(store)
    personas = [Persona(id=f"p{i}", identity="Shopper", age_group="20s", gender="Female",
                        description="Tea", intent="tea", purpose="tea") for i in range(2)]
    config = SimulationConfig(engine_type=EngineType.RULE_BASED)
    pathfinder = AStarPathFinder()
    spec = OptimizeSpec(objective=OptimizeObjective.WALKING_DISTANCE, budget=1,
                        eval_customers=10, validation_customers=0)

    async def evaluate(self, layout):
        score = 10 if store_fingerprint(layout) == baseline else 5
        return score, SimulationSummary(store_id=layout.id, avg_path_tiles=score)

    async def simulate(self, layout):
        is_base = store_fingerprint(layout) == baseline
        panel = personas
        if (failure == "baseline_empty" and is_base) or (failure == "candidate_empty" and not is_base):
            panel = []
        elif failure == "disjoint":
            panel = personas[:1] if is_base else personas[1:]
        walks = 10 if is_base else 0 if failure == "candidate_zero_walk" else 1
        outcomes = [CustomerResult(
            persona_id=p.id, day=Weekday.MON, arrival_time="12:00:00",
            timeline=[TimelineEvent(elapsed_sec=i, x=i, y=0, action=Action.MOVE) for i in range(walks)],
        ) for p in panel]
        score = walks if outcomes else 0
        summary = SimulationSummary(store_id=layout.id, total_customers=len(outcomes), avg_path_tiles=score)
        missing = [FailedCustomer(persona_id=p.id, reason="scripted failure") for p in personas if p not in panel]
        result = AggregatedResult(summary=summary, pathcalc_heatmap=[], persona_heatmap=[], diagnostics=RunDiagnostics(
            requested_customers=2, succeeded_customers=len(outcomes), failed_customers=missing,
        ))
        return score, result, outcomes

    calibration = AsyncMock(return_value=(config, None))
    monkeypatch.setattr(judge, "calibrate_surrogate", calibration)
    monkeypatch.setattr(LayoutEvaluator, "evaluate", evaluate)
    monkeypatch.setattr(LayoutEvaluator, "simulate", simulate)
    job = judge.judge_layout_search(
        store, spec, JudgeSpec(judge="vlm", top_k=1, calibrate=calibrate, vlm_customers=4),
        surrogate_config=config, vlm_config=config, vlm_engine=build_engine(config, pathfinder=pathfinder),
        search_personas=personas, vlm_personas=personas, cue_sampler=sample_cue,
        patterns=BEHAVIOR_PATTERNS, pathfinder=pathfinder, model_label="scripted",
    )
    if failure == "baseline_empty":
        with pytest.raises(ValueError, match="baseline.*no successful shopper results"):
            asyncio.run(job)
        calibration.assert_not_called()
        return
    result = asyncio.run(job)
    assert result.judge is not None
    candidate = result.judge.candidates[1]
    if failure in {"complete", "candidate_zero_walk"}:
        assert result.judge.winner == candidate.label
        assert candidate.vlm_score == (0 if failure == "candidate_zero_walk" else 1)
        assert candidate.vlm_rank == 1
        assert result.applied_moves
    else:
        assert result.judge.winner == "baseline"
        assert result.applied_moves == []
        assert candidate.vlm_score is None and candidate.vlm_rank is None
        assert candidate.relative_improvement is None and candidate.prob_better is None
        assert any("excluded from ranking" in note for note in result.judge.notes)
        assert not any("None" in note for note in result.judge.notes)
