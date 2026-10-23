"""Cached replays and malformed histories must not make new model work appear free."""

import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import run_estimate
from store_emulator.application.storage.io import write_json
from store_emulator.domain.config import LLMConfig
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout

MODEL = "openai/gpt-6-luna"
ENGINE = "pattern_intent_impulse"


def history(name="run_history", **usage):
    root = Path(".data") / PID / "runs" / name
    write_json(root / "status.json", {"status": "completed", "completed_customers": 10,
        "started_at": "2026-10-23T09:00:00+00:00", "finished_at": "2026-10-23T09:10:00+00:00"})
    write_json(root / "output/manifest.json", {"engine_type": ENGINE, "model": MODEL})
    write_json(root / "output/token_usage.json", {"requests": 30, "prompt_tokens": 100000,
        "completion_tokens": 50000, "cached_requests": 0, **usage})
    return root


@pytest.fixture
def api(layout, monkeypatch):
    # Deterministic model pricing/resolution, without an API key or provider calls.
    monkeypatch.setattr(run_estimate, "resolve_model", lambda ref, **kwargs: LLMConfig(model=ref))
    monkeypatch.setattr(run_estimate, "cost_usd", lambda model, prompt, completion: (prompt + completion) / 1000)
    return TestClient(app, raise_server_exceptions=False)


def estimate(api):
    response = api.post(f"/api/projects/{PID}/runs/estimate", json={"setup_id": SID, "engine_type": ENGINE, "model": MODEL})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("cached", [1, 15, 30])
def test_cached_measurements_do_not_lower_next_runs_work_estimate(api, cached):
    baseline = estimate(api)
    history(cached_requests=cached, prompt_tokens=0, completion_tokens=0)
    assert estimate(api) == baseline


def test_partial_cache_with_nonzero_tokens_also_falls_back_to_uncached_measurement(api):
    old = history("run_uncached")
    write_json(old / "status.json", {"status": "completed", "completed_customers": 10,
        "started_at": "2026-10-22T09:00:00+00:00", "finished_at": "2026-10-22T09:10:00+00:00"})
    baseline = estimate(api)
    history("run_cached", cached_requests=15, prompt_tokens=5000, completion_tokens=2000)
    assert estimate(api) == baseline
    assert baseline["cost_usd"] == 15.0 and baseline["minutes"] == 1.0


@pytest.mark.parametrize("filename", ["status.json", "output/manifest.json", "output/token_usage.json"])
@pytest.mark.parametrize("value", [None, False, 7, "history", []])
def test_wrong_shaped_run_files_cannot_block_the_next_estimate(api, filename, value):
    baseline = estimate(api)
    root = history()
    write_json(root / filename, value)
    assert estimate(api) == baseline


@pytest.mark.parametrize("usage", [
    {}, {"requests": 30}, {"requests": 30, "prompt_tokens": 0, "completion_tokens": 0},
    {"prompt_tokens": -100, "completion_tokens": 30},
    {"prompt_tokens": 100, "completion_tokens": -30},
    {"prompt_tokens": "unknown", "completion_tokens": 30},
    {"prompt_tokens": True, "completion_tokens": 30},
    {"prompt_tokens": 100, "completion_tokens": 30, "cached_requests": "unknown"},
])
def test_missing_or_invalid_usage_does_not_fabricate_free_or_negative_work(api, usage):
    baseline = estimate(api)
    root = history()
    write_json(root / "output/token_usage.json", usage)
    assert estimate(api) == baseline


@pytest.mark.parametrize("started,finished", [
    ("2026-10-23T09:00:00", "2026-10-23T09:10:00+00:00"),
    ("2026-10-23T09:00:00+00:00", "2026-10-23T09:10:00"),
    ("invalid", "2026-10-23T09:10:00+00:00"),
])
def test_unusable_elapsed_time_keeps_valid_usage_and_uses_default_pace(api, started, finished):
    root = history()
    write_json(root / "status.json", {"status": "completed", "completed_customers": 10,
                                      "started_at": started, "finished_at": finished})
    result = estimate(api)
    assert result["cost_usd"] == 15.0 and result["model_calls"] == 3
    assert math.isfinite(result["minutes"]) and result["minutes"] >= 0


@pytest.mark.parametrize("cache_field", [False, True])
def test_valid_uncached_and_legacy_measurements_still_control_the_estimate(api, cache_field):
    root = history()
    if not cache_field:
        write_json(root / "output/token_usage.json", {"requests": 20, "prompt_tokens": 100000, "completion_tokens": 50000})
    result = estimate(api)
    assert result["cost_usd"] == 15.0 and result["minutes"] == 1.0
    assert result["model_calls"] == (3 if cache_field else 2)
