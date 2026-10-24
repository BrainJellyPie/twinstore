"""Constant candidate scores have no rank agreement, even with three layouts."""

import asyncio
import json
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


@pytest.mark.parametrize("surrogate,vision,expected", [
    ([100, 100, 100], [100, 110, 120], None),
    ([100, 110, 120], [100, 100, 100], None),
    ([100, 100, 100], [100, 100, 100], None),
    ([0, 0, 0], [0, 0, 0], None),
    ([100, 110, 120], [100, 110, 120], 1.0),
    ([100, 110, 120], [120, 110, 100], -1.0),
    ([100, 100, 120], [100, 100, 120], 1.0),
])
def test_judge_keeps_undefined_agreement_out_of_reports(monkeypatch, surrogate, vision, expected):
    layouts = [generate_store("mini_mart").model_copy(update={"id": f"layout-{i}"}) for i in range(3)]
    spec = OptimizeSpec(budget=2, eval_customers=10, validation_customers=0)
    search = OptimizeResult(
        spec=spec, baseline_score=surrogate[0], best_score=max(surrogate), relative_improvement=0,
        best_store=layouts[0], applied_moves=[], history=[], evaluations=3, seconds=0,
        top_candidates=[LayoutCandidate(iteration=i, score=surrogate[i], moves=[f"move-{i}"], store=layouts[i])
                        for i in range(1, 3)],
    )
    monkeypatch.setattr(judge, "optimize", AsyncMock(return_value=search))
    people = [Persona(id="p", identity="Shopper", age_group="20s", gender="Female", description="", intent="", purpose="")]

    async def simulate(self, layout):
        score = vision[int(layout.id.rsplit("-", 1)[1])]
        summary = SimulationSummary(store_id=layout.id, total_customers=1, total_revenue=score, revenue_per_visitor=score)
        aggregated = AggregatedResult(summary=summary, pathcalc_heatmap=[], persona_heatmap=[])
        return score, aggregated, [CustomerResult(persona_id="p", day=1, arrival_time="09:00:00", total_spent=score)]

    monkeypatch.setattr(LayoutEvaluator, "simulate", simulate)
    config = SimulationConfig(engine_type=EngineType.RULE_BASED)
    pathfinder = AStarPathFinder()
    result = asyncio.run(judge.judge_layout_search(
        layouts[0], spec, JudgeSpec(judge="vlm", top_k=2, calibrate=False, vlm_customers=4),
        surrogate_config=config, vlm_config=config, vlm_engine=build_engine(config, pathfinder=pathfinder),
        search_personas=people, vlm_personas=people, cue_sampler=sample_cue,
        patterns=BEHAVIOR_PATTERNS, pathfinder=pathfinder, model_label="scripted",
    ))
    assert result.judge is not None
    assert result.judge.spearman == expected
    assert "nan" not in " ".join(result.notes).lower()
    assert "nan" not in " ".join(result.judge.notes).lower()
    json.dumps(result.model_dump(mode="json"), allow_nan=False)
    assert result.judge.winner == ("baseline" if vision[0] == max(vision) else f"#{vision.index(max(vision))}")
