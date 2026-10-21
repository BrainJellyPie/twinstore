"""Rank layouts on the same successful shoppers after partial vision failures."""

import asyncio

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.optimize import JudgeSpec, OptimizeObjective, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import SimulationSummary, RunDiagnostics, FailedCustomer
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, store_fingerprint, objective_value
from store_emulator.engine.optimize.judge import judge_layout_search
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.aggregator import aggregate
from store_emulator.engine.simulation.factory import build_engine


@pytest.mark.parametrize("objective", [OptimizeObjective.WALKING_DISTANCE, OptimizeObjective.REVENUE_PER_VISITOR])
@pytest.mark.parametrize("mode", ["candidate_missing_worse", "baseline_missing_better", "no_common_panel"])
def test_partial_failures_do_not_change_the_population_used_to_rank_layouts(monkeypatch, objective, mode):
    store = generate_store("mini_mart")
    baseline = store_fingerprint(store)
    personas = [Persona(id=f"p{i}", identity="Shopper", age_group="20s", gender="Female",
                        description="Tea", intent="tea", purpose="tea") for i in range(2)]
    config = SimulationConfig(engine_type=EngineType.RULE_BASED)
    pathfinder = AStarPathFinder()
    walking = objective == OptimizeObjective.WALKING_DISTANCE
    count = 2 if mode == "no_common_panel" else 1
    spec = OptimizeSpec(objective=objective, budget=count, eval_customers=10, validation_customers=0)
    candidate_index = 0

    async def evaluate(self, layout):
        is_base = store_fingerprint(layout) == baseline
        score = (10 if is_base else 5) if walking else (100 if is_base else 150)
        return score, SimulationSummary(store_id=layout.id, avg_path_tiles=score if walking else 0,
                                        revenue_per_visitor=0 if walking else score)

    async def simulate(self, layout):
        nonlocal candidate_index
        is_base = store_fingerprint(layout) == baseline
        if mode == "candidate_missing_worse":
            if walking:
                values = {"p0": 1, "p1": 10} if is_base else {"p0": 2}
            else:
                values = {"p0": 100, "p1": 10} if is_base else {"p0": 90}
        elif mode == "baseline_missing_better":
            if walking:
                values = {"p0": 10} if is_base else {"p0": 9, "p1": 100}
            else:
                values = {"p0": 100} if is_base else {"p0": 110, "p1": 0}
        else:
            values = ({p.id: 10 if walking else 100 for p in personas} if is_base
                      else {f"p{candidate_index}": 1 if walking else 110})
            if not is_base:
                candidate_index += 1
        outcomes: list[CustomerResult] = []
        for pid, value in values.items():
            if walking:
                timeline = [TimelineEvent(elapsed_sec=i, x=1, y=1, action=Action.MOVE) for i in range(value)]
            else:
                timeline = [TimelineEvent(elapsed_sec=1, x=1, y=1, action=Action.BUY,
                                          target_rack=store.product_racks[0].id,
                                          product_sku="tea", product_name="Tea", price=value)]
            outcomes.append(CustomerResult(persona_id=pid, day=Weekday.MON, arrival_time="12:00:00",
                                           timeline=timeline, total_spent=0 if walking else value))
        result = aggregate(layout, outcomes, personas, [])
        result.diagnostics = RunDiagnostics(
            requested_customers=2, succeeded_customers=len(outcomes),
            failed_customers=[FailedCustomer(persona_id=p.id, reason="scripted failure")
                              for p in personas if p.id not in values],
        )
        return objective_value(objective, result.summary), result, outcomes

    monkeypatch.setattr(LayoutEvaluator, "evaluate", evaluate)
    monkeypatch.setattr(LayoutEvaluator, "simulate", simulate)
    job = judge_layout_search(
        store, spec, JudgeSpec(judge="vlm", top_k=count, calibrate=False, vlm_customers=4),
        surrogate_config=config, vlm_config=config, vlm_engine=build_engine(config, pathfinder=pathfinder),
        search_personas=personas, vlm_personas=personas, cue_sampler=sample_cue,
        patterns=BEHAVIOR_PATTERNS, pathfinder=pathfinder, model_label="scripted",
    )
    if mode == "no_common_panel":
        with pytest.raises(ValueError, match="common"):
            asyncio.run(job)
        return
    result = asyncio.run(job)
    assert result.judge is not None and result.judge.customers == 1
    assert result.baseline_summary is not None and result.best_summary is not None
    assert result.baseline_summary.total_customers == result.best_summary.total_customers == 1
    if mode == "candidate_missing_worse":
        assert result.judge.winner == "baseline"
        assert result.best_score == result.baseline_score == (1 if walking else 100)
    else:
        assert result.judge.winner != "baseline"
        assert result.best_score == (9 if walking else 110)
        assert result.validation is not None and result.validation.paired_customers == 1
