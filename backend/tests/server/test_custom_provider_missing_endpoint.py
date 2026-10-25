"""An old custom-model selection with no endpoint cannot fall through to the SDK's default host."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm, providers, simulation
from store_emulator.application.storage.setups import setup_path
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.providers import ProviderKind
from store_emulator.server.main import app
from store_emulator.server.routes import simulate
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("setting", ["absent", "null", "empty"])
@pytest.mark.parametrize("key", [False, True])
@pytest.mark.parametrize("engine", [EngineType.PATTERN_INTENT_IMPULSE, EngineType.VLM_GLANCE])
@pytest.mark.parametrize("action", ["availability", "start"])
def test_missing_custom_address_is_unavailable_before_any_run_is_created(layout, monkeypatch, setting, key, engine, action):
    if key:
        monkeypatch.setenv("CUSTOM_LLM_API_KEY", "offline-custom-key")
    else:
        monkeypatch.delenv("CUSTOM_LLM_API_KEY", raising=False)
    settings = {} if setting == "absent" else {ProviderKind.CUSTOM: providers.ProviderSettings(
        kind=ProviderKind.CUSTOM, enabled=True, api_base=None if setting == "null" else "", default_model="served")}
    monkeypatch.setattr(providers, "load_settings", lambda: settings)
    monkeypatch.setattr(simulate, "load_settings", lambda: settings)
    independent = LLMConfig(model="openai/independent", api_base="http://127.0.0.1:9000/v1")
    custom = LLMConfig(model="custom:served")
    config = SimulationConfig(llm=custom if engine == EngineType.PATTERN_INTENT_IMPULSE else independent)
    config.engines.vlm_glance.llm = custom if engine == EngineType.VLM_GLANCE else independent
    monkeypatch.setattr(simulate, "get_config", lambda: config)
    probes, starts = [], []

    def answers(base):
        probes.append(base)
        assert base == independent.api_base
        return True

    monkeypatch.setattr(local_vlm, "server_answers", answers)
    monkeypatch.setattr(simulate, "submit_background", lambda *args: starts.append(args))
    client = TestClient(app)
    before = setup_path(PID, SID).read_bytes()
    if action == "availability":
        response = client.get("/api/engines")
        assert response.status_code == 200, response.text
        choices = {row["engine_type"]: row for row in response.json()}
        assert choices[engine.value]["model_ready"] is False
        assert all(row["model_ready"] for name, row in choices.items() if name != engine.value)
    else:
        response = client.post(f"/api/projects/{PID}/runs", json={"setup_id": SID, "engine_type": engine.value})
        assert response.status_code == 400, response.text
        assert "server address" in response.json()["detail"] and "Settings" in response.json()["detail"]
        assert not probes
    assert "offline-custom-key" not in response.text
    assert not starts and not simulation.list_runs(PID)
    assert setup_path(PID, SID).read_bytes() == before
