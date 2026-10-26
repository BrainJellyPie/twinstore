"""Completed fallback journeys do not establish successful vision judgments."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.optimize import JudgeSpec, LayoutCandidate, OptimizeResult, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, SimulationSummary
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize import judge
from store_emulator.engine.optimize.evaluate import LayoutEvaluator
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine


@pytest.mark.parametrize("failing_layout,calibrate", [(0, True), (0, False), (1, False)])
@pytest.mark.parametrize("glances,glance_errors,plans,plan_errors,blocked", [
    (20, 20, 0, 0, True), (0, 0, 20, 20, True),
    (20, 12, 20, 12, True), (100, 51, 0, 0, True),
    (20, 10, 0, 0, False), (20, 0, 20, 20, True),
    (20, 20, 20, 0, True), (1, 1, 100, 0, True),
    (20, 1, 20, 1, False), (0, 0, 0, 0, False),
])
def test_judge_counts_failed_model_calls_even_when_every_shopper_completes(
    monkeypatch, failing_layout, calibrate, glances, glance_errors, plans, plan_errors, blocked,
):
    layouts = [generate_store("mini_mart").model_copy(update={"id": f"layout-{i}"}) for i in range(3)]
    spec = OptimizeSpec(budget=2, eval_customers=10, validation_customers=0)
    search = AsyncMock(return_value=OptimizeResult(
        spec=spec, baseline_score=100, best_score=120, relative_improvement=.2,
        best_store=layouts[2], applied_moves=[], history=[], evaluations=3, seconds=0,
        top_candidates=[LayoutCandidate(iteration=i, score=100 + 10 * i, moves=[f"move-{i}"], store=layouts[i])
                        for i in range(1, 3)],
    ))
    monkeypatch.setattr(judge, "optimize", search)
    people = [Persona(id="p", identity="Shopper", age_group="20s", gender="Female", description="", intent="", purpose="")]
    visited = []

    async def simulate(self, layout):
        index = int(layout.id.rsplit("-", 1)[1])
        visited.append(index)
        score = 100 + 10 * index
        summary = SimulationSummary(store_id=layout.id, total_customers=1, total_revenue=score, revenue_per_visitor=score)
        aggregated = AggregatedResult(summary=summary, pathcalc_heatmap=[], persona_heatmap=[])
        return score, aggregated, [CustomerResult(persona_id="p", day=1, arrival_time="09:00:00", total_spent=score)]

    def metadata(self):
        if visited[-1] != failing_layout:
            return {"glances": 20, "errors": 0, "planning": {"plans": 20, "plan_errors": 0}}
        return {"glances": glances, "errors": glance_errors, "planning": {"plans": plans, "plan_errors": plan_errors}}

    monkeypatch.setattr(LayoutEvaluator, "simulate", simulate)
    monkeypatch.setattr(LayoutEvaluator, "engine_metadata", metadata)
    config = SimulationConfig(engine_type=EngineType.RULE_BASED)
    calibration = AsyncMock(return_value=(config, None))
    monkeypatch.setattr(judge, "calibrate_surrogate", calibration)
    pathfinder = AStarPathFinder()
    job = judge.judge_layout_search(
        layouts[0], spec, JudgeSpec(judge="vlm", top_k=2, calibrate=calibrate, vlm_customers=4),
        surrogate_config=config, vlm_config=config, vlm_engine=build_engine(config, pathfinder=pathfinder),
        search_personas=people, vlm_personas=people, cue_sampler=sample_cue,
        patterns=BEHAVIOR_PATTERNS, pathfinder=pathfinder, model_label="scripted",
    )
    label = "baseline" if failing_layout == 0 else "#1"
    failed, total = glance_errors + plan_errors, glances + plans
    if blocked:
        with pytest.raises(ValueError, match=rf"{failed} of {total}.*{label}"):
            asyncio.run(job)
        assert visited == list(range(failing_layout + 1))
        if calibrate:
            calibration.assert_not_called()
            search.assert_not_called()
    else:
        result = asyncio.run(job)
        assert result.judge is not None and result.judge.winner == "#2"
        assert visited == [0, 1, 2]
        notes = " ".join(result.judge.notes)
        assert (f"{failed} of {total} model calls failed for {label}" in notes) == bool(failed)
