"""Ensemble estimates account for every voter and each mixture member's work."""

import math

import pytest

from store_emulator.application import run_estimate
from store_emulator.application.simulation import RunOptions
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig, EnsembleMember
from store_emulator.domain.store import Store


@pytest.fixture
def estimate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    store = Store(id="s", name="Store", type="Convenience store", grid_size=(5, 5))
    people = [Persona(id=f"p{i}", identity="Visitor", age_group="20s", gender="Female",
                      description="", intent="", purpose="snack") for i in range(100)]
    monkeypatch.setattr(run_estimate, "_inputs", lambda *args: (store, people))

    def resolve(model, **kwargs):
        return LLMConfig(model=model, api_base="http://127.0.0.1:8081/v1" if model == "local" else None,
                         max_parallel=1 if model == "limited-cloud" else None)

    def price(model, prompt, completion):
        assert model != "local", "local work must not ask for a cloud token price"
        rate = {"cheap": 1, "expensive": 10, "limited-cloud": 1}.get(model)
        return None if rate is None else rate * (prompt + completion) / 1_000_000

    monkeypatch.setattr(run_estimate, "resolve_model", resolve)
    monkeypatch.setattr(run_estimate, "cost_usd", price)

    def run(models, weights, *, mode="mixture", engine=EngineType.PATTERN_INTENT_IMPULSE, measured=None):
        ensemble = EnsembleConfig(mode=mode, members=[
            EnsembleMember(model=model, weight=weight) for model, weight in zip(models, weights, strict=True)
        ])
        monkeypatch.setattr(run_estimate, "_measured", lambda *args: measured)
        return run_estimate.estimate_run("project", "s", RunOptions(engine_type=engine, ensemble=ensemble),
                                         SimulationConfig())

    return run


@pytest.mark.parametrize("scale", [math.ulp(0.0), 1.0, 5e307])
@pytest.mark.parametrize("weights", [(1, 3), (3, 1)])
@pytest.mark.parametrize("engine", [EngineType.PATTERN_INTENT_IMPULSE, EngineType.VLM_GLANCE])
def test_mixture_prices_follow_weights_at_all_finite_scales(estimate, scale, weights, engine):
    result = estimate(["cheap", "expensive"], [w * scale for w in weights], engine=engine)
    tokens = 2_800_000 if engine == EngineType.PATTERN_INTENT_IMPULSE else 230_000
    expected = tokens / 1_000_000 * (weights[0] + 10 * weights[1]) / sum(weights)
    assert result.cost_usd == round(expected, 2)
    assert result.model_calls == (300 if engine == EngineType.PATTERN_INTENT_IMPULSE else 150)


@pytest.mark.parametrize("models", [["cheap"], ["cheap", "expensive"], ["cheap"] * 4])
@pytest.mark.parametrize("engine", [EngineType.VLM_GLANCE, EngineType.PATTERN_INTENT_IMPULSE])
def test_vote_counts_all_vision_members_but_text_engines_use_mixture(estimate, models, engine):
    result = estimate(models, [1] * len(models), mode="vote", engine=engine)
    vision = engine == EngineType.VLM_GLANCE
    assert result.model_calls == (150 * len(models) if vision else 300)
    rates = [10 if model == "expensive" else 1 for model in models]
    assert result.cost_usd == round(0.23 * sum(rates) if vision else 2.8 * sum(rates) / len(rates), 2)


def test_voters_ignore_mixture_weights(estimate):
    ordinary = estimate(["cheap", "expensive"], [1, 1], mode="vote", engine=EngineType.VLM_GLANCE)
    skewed = estimate(["cheap", "expensive"], [1, 999], mode="vote", engine=EngineType.VLM_GLANCE)
    assert ordinary.cost_usd == skewed.cost_usd == 2.53
    assert ordinary.model_calls == skewed.model_calls == 300


def test_mixed_local_cloud_keeps_known_cloud_cost_and_local_runtime(estimate):
    result = estimate(["local", "cheap"], [3, 1])
    assert result.local is False
    assert result.cost_usd == 0.7
    assert result.minutes >= 150 and result.warn


@pytest.mark.parametrize("mode", ["mixture", "vote"])
def test_all_local_is_free_and_unknown_cloud_cost_stays_unknown(estimate, mode):
    result = estimate(["local", "local"], [1, 1], mode=mode, engine=EngineType.VLM_GLANCE)
    assert result.local and result.cost_usd is None and result.minutes > 0
    unknown = estimate(["local", "unpriced"], [1, 1], mode=mode, engine=EngineType.VLM_GLANCE)
    assert not unknown.local and unknown.cost_usd is None


@pytest.mark.parametrize("mode", ["mixture", "vote"])
def test_recorded_aggregate_usage_is_not_multiplied_again(estimate, mode):
    measured = run_estimate._Measured(requests=4, prompt=3000, completion=1000, seconds=2)
    result = estimate(["cheap", "expensive"], [1, 3], mode=mode, engine=EngineType.VLM_GLANCE,
                      measured=measured)
    assert result.model_calls == 400 and result.minutes == 3.3
    assert result.cost_usd == (2.2 if mode == "vote" else 3.1)


def test_vote_default_requests_expand_when_history_has_tokens_but_no_request_count(estimate):
    measured = run_estimate._Measured(requests=None, prompt=3000, completion=1000, seconds=None)
    result = estimate(["cheap", "expensive"], [1, 1], mode="vote", engine=EngineType.VLM_GLANCE,
                      measured=measured)
    assert result.model_calls == 300 and result.cost_usd == 2.2


def test_multiple_votes_trigger_cost_warning_that_one_model_does_not(estimate):
    one = estimate(["cheap"], [1], mode="vote", engine=EngineType.VLM_GLANCE)
    six = estimate(["cheap"] * 6, [1] * 6, mode="vote", engine=EngineType.VLM_GLANCE)
    assert not one.warn and six.warn
    assert six.cost_usd == 1.38


def test_paid_provider_with_a_concurrency_limit_is_not_classified_as_free_local_work(estimate):
    result = estimate(["limited-cloud"], [1])
    assert not result.local and result.cost_usd == 2.8
    assert result.minutes == 20


@pytest.mark.parametrize("mode", ["mixture", "vote"])
def test_members_on_the_same_local_server_share_its_capacity(estimate, mode):
    result = estimate(["local", "local"], [1, 3], mode=mode, engine=EngineType.VLM_GLANCE)
    assert result.minutes == (200 if mode == "vote" else 100)
