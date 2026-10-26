import asyncio
import json

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.town.vlm_synergy import vlm_basket_synergy
from tests.engine.test_vlm_synergy import SAMPLE, town


class IntermittentModel:
    def __init__(self, fail_arm, successes):
        self.fail_arm = fail_arm
        self.successes = successes
        self.arm = -1
        self.calls = 0

    def reset_usage(self):
        self.arm += 1
        self.calls = 0

    def get_usage(self):
        return TokenUsage(requests=self.calls)

    async def generate_structured_async(self, response_model, *args, **kwargs):
        self.calls += 1
        if self.arm == self.fail_arm and self.calls > self.successes:
            raise RuntimeError("offline provider quota exhausted")
        return response_model.model_validate({"mission": "browsing", "enter": False, "items": []})


def run(town, model):
    store = Store.model_validate_json((SAMPLE / "store.json").read_text())
    pool = [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())][:300]
    config = SimulationConfig(engine_type=EngineType.VLM_GLANCE, seed=5)
    config.engines.vlm_glance.max_glances = 0
    config.engines.vlm_glance.entrance_image = False
    pf = AStarPathFinder()
    engine = VLMGlanceEngine(llm=model, pathfinder=pf, config=config)
    return asyncio.run(vlm_basket_synergy(
        town, "cafe-next-door", store, pool, config=config, engine=engine, pathfinder=pf,
        cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, customers=12, max_concurrent=1,
    ))


@pytest.mark.parametrize("fail_arm", [0, 1])
@pytest.mark.parametrize("successes", [1, 2])
def test_mostly_fallback_visitors_cannot_produce_a_vision_revenue_report(town, fail_arm, successes):
    model = IntermittentModel(fail_arm, successes)
    with pytest.raises(ValueError, match="vision model failed.*calls"):
        run(town, model)
    assert model.arm == fail_arm


@pytest.mark.parametrize("fail_arm,successes", [(0, 6), (1, 4)])
def test_half_failed_calls_remain_available_with_explicit_model_warning(town, fail_arm, successes):
    result = run(town, IntermittentModel(fail_arm, successes))
    assert result.plan_errors == successes and result.failed_customers == 0
    assert any("model calls failed" in note for note in result.notes)


def test_valid_decisions_to_buy_nothing_remain_valid_vision_evidence(town):
    result = run(town, IntermittentModel(-1, 0))
    assert result.plan_errors == result.failed_customers == 0
    assert result.delta_revenue_per_day == 0


@pytest.mark.parametrize("plans,plan_errors,glances,errors,rejected", [
    (0, 0, 0, 0, False), (0, 0, 2, 1, False), (0, 0, 3, 2, True),
    (4, 0, 6, 6, True), (4, 0, 4, 4, True), (3, 2, 3, 2, True),
    (100, 0, 1, 1, True), (1, 1, 100, 0, True),
    (3, 1, 3, 1, False), (1, 0, 1, 0, False),
])
def test_call_quality_counts_planning_and_shelf_glances_together(town, monkeypatch, plans, plan_errors, glances, errors, rejected):
    metadata = VLMGlanceEngine.metadata

    def with_counts(self):
        return {**metadata(self), "planning": {"plans": plans, "plan_errors": plan_errors},
                "glances": glances, "errors": errors}

    monkeypatch.setattr(VLMGlanceEngine, "metadata", with_counts)
    if rejected:
        with pytest.raises(ValueError, match=f"failed on {plan_errors + errors} of {plans + glances} calls"):
            run(town, IntermittentModel(-1, 0))
    else:
        result = run(town, IntermittentModel(-1, 0))
        assert any("model calls failed" in note for note in result.notes) == bool(plan_errors + errors)
