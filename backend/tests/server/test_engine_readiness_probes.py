"""Engine availability should inspect each endpoint once per request, without stale readiness."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm, providers
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.server.main import app
from store_emulator.server.routes import simulate


@pytest.mark.parametrize("other", ["http://127.0.0.1:9000/v1", "http://127.0.0.1:9001/v1",
    "http://127.0.0.1:9000/another/v1", "http://localhost:9000/v1"])
def test_one_probe_per_endpoint_with_fresh_results_on_each_request(monkeypatch, tmp_path, other):
    monkeypatch.chdir(tmp_path)
    for preset in providers.PRESETS.values():
        if preset.api_key_env:
            monkeypatch.delenv(preset.api_key_env, raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(providers, "load_settings", lambda: {})
    monkeypatch.setattr(simulate, "load_settings", lambda: {})
    monkeypatch.setattr(local_vlm, "_manager", [local_vlm.LocalVLMManager(tmp_path)])
    base = "http://127.0.0.1:9000/v1"
    config = SimulationConfig(llm=LLMConfig(model="openai/text-local", api_base=base))
    config.engines.vlm_glance.llm = LLMConfig(model="openai/vision-local", api_base=other)
    monkeypatch.setattr(simulate, "get_config", lambda: config)
    available = {endpoint: False for endpoint in {base, other}}
    calls = []

    def answers(endpoint):
        calls.append(endpoint)
        return available[endpoint]

    monkeypatch.setattr(local_vlm, "server_answers", answers)
    with TestClient(app) as client:
        for state in [False, True, False]:
            available[base] = state
            if other != base:
                available[other] = not state
            calls.clear()
            response = client.get("/api/engines")
            assert response.status_code == 200
            choices = {row["engine_type"]: row for row in response.json()}
            assert choices["pattern_intent_impulse"]["model_ready"] is state
            assert choices["vlm_glance"]["model_ready"] is available[other]
            assert choices["rule_based"]["model_ready"] is True
            assert calls == list(dict.fromkeys([base, other]))
