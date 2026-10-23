"""Bound model time before scenario arithmetic, preserving the scenario's effect."""

import asyncio
import json

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.scenario import Scenario, ScenarioPriors
from store_emulator.domain.types import Action, TokenUsage
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner
from tests.engine.test_vlm_plan import _personas


class TimedEngine:
    engine_type = "offline"

    def __init__(self, dwell):
        self.dwell = dwell

    def reset_usage(self):
        pass

    def get_usage(self):
        return TokenUsage()

    async def decide_actions(self, context):
        return EngineDecision(engine_type=self.engine_type, actions=[
            CustomerAction(nav="area", action=Action.WANDER, dwell=self.dwell),
            CustomerAction(nav="leave"),
        ])


@pytest.mark.parametrize("factor", [0.5, 1, 2])
@pytest.mark.parametrize("dwell", [-10**400, -1, 0, 1, 119, 120, 121, 86400, 10**400])
def test_full_run_bounds_raw_time_before_scenario_scaling(dwell, factor):
    store = generate_store("compact_cvs", seed=0)
    store.weekly_schedule = []
    config = SimulationConfig(walk_pace_sd=0, scenario=Scenario(),
        scenario_priors=ScenarioPriors(music_dwell={"none": factor}))

    def run(value):
        runner = PerCustomerSimulationRunner(config, TimedEngine(value), AStarPathFinder(),
                                             sample_cue, BEHAVIOR_PATTERNS)
        return asyncio.run(runner.run(store, _personas(1), path_heatmap=False))

    zero, zero_results = run(0)
    report, results = run(dwell)
    assert zero.diagnostics.failed_customers == report.diagnostics.failed_customers == []
    assert len(results) == len(zero_results) == 1
    bounded = max(0, min(120, dwell))
    expected = max(1, round(bounded * factor)) if bounded else 0
    assert results[0].duration_sec - zero_results[0].duration_sec == expected
    assert report.summary.avg_visit_sec == results[0].duration_sec


@pytest.mark.parametrize("kind", list(Action))
@pytest.mark.parametrize("raw", [-10**400, -1, 0, 1, 120, 121, 10**400])
def test_model_json_times_are_bounded_without_retries_or_input_mutation(kind, raw):
    payload = {"nav": "path", "action": kind, "dwell": raw}
    action = CustomerAction.model_validate_json(json.dumps(payload))
    assert action.dwell == max(0, min(120, raw))
    assert payload["dwell"] == raw


def test_action_response_schema_advertises_the_same_raw_time_bounds():
    schema = CustomerAction.model_json_schema()["properties"]["dwell"]
    assert schema["minimum"] == 0 and schema["maximum"] == 120
