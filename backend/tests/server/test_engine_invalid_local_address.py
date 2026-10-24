"""A mistyped model endpoint must not remove the engine selector or appear ready."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from store_emulator.application import local_vlm, providers
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.providers import ProviderKind
from store_emulator.server.main import app
from store_emulator.server.routes import simulate


@pytest.mark.parametrize("endpoint", ["http://[", "http://[not-ip]", "http://[::1",
    "http://[::ffff:999.1.2.3]", "http://localhost:not-a-port/v1", "http:///v1"])
@pytest.mark.parametrize("engine", [EngineType.PATTERN_INTENT_IMPULSE, EngineType.VLM_GLANCE])
@pytest.mark.parametrize("saved_provider", [False, True])
@pytest.mark.parametrize("authenticated", [False, True])
def test_invalid_endpoint_does_not_hide_other_engines(monkeypatch, tmp_path, endpoint, engine, saved_provider, authenticated):
    monkeypatch.chdir(tmp_path)
    for preset in providers.PRESETS.values():
        if preset.api_key_env:
            monkeypatch.delenv(preset.api_key_env, raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    manager = local_vlm.LocalVLMManager(tmp_path)
    monkeypatch.setattr(local_vlm, "_manager", [manager])
    key = SecretStr("offline-local-test-key") if authenticated else None
    settings = {ProviderKind.LLAMACPP: providers.ProviderSettings(kind=ProviderKind.LLAMACPP, api_base=endpoint, api_key=key)}
    monkeypatch.setattr(providers, "load_settings", lambda: settings)
    monkeypatch.setattr(simulate, "load_settings", lambda: settings)
    good = LLMConfig(model="openai/independent-model", api_base="http://127.0.0.1:9000/v1")
    bad = LLMConfig(model="llamacpp:local") if saved_provider else LLMConfig(model="openai/mistyped-model", api_base=endpoint, api_key=key)
    config = SimulationConfig(llm=bad if engine == EngineType.PATTERN_INTENT_IMPULSE else good)
    config.engines.vlm_glance.llm = bad if engine == EngineType.VLM_GLANCE else good
    monkeypatch.setattr(simulate, "get_config", lambda: config)
    probes = []

    def answers(base):
        probes.append(base)
        assert base == good.api_base, "Do not send a network probe to a structurally invalid endpoint"
        return True

    monkeypatch.setattr(local_vlm, "server_answers", answers)
    with pytest.raises(ValueError, match="model server address is invalid"):
        providers.ensure_resolvable(config.model_copy(update={"engine_type": engine}))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/engines")
    assert response.status_code == 200, response.text
    choices = {row["engine_type"]: row for row in response.json()}
    assert choices[engine.value]["model_ready"] is False
    assert choices["rule_based"]["model_ready"] is True
    other = EngineType.VLM_GLANCE if engine == EngineType.PATTERN_INTENT_IMPULSE else EngineType.PATTERN_INTENT_IMPULSE
    assert choices[other.value]["model_ready"] is True
    assert probes and all(base == good.api_base for base in probes)


def test_inline_cloud_key_still_makes_both_model_engines_available(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for preset in providers.PRESETS.values():
        if preset.api_key_env:
            monkeypatch.delenv(preset.api_key_env, raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(providers, "load_settings", lambda: {})
    monkeypatch.setattr(simulate, "load_settings", lambda: {})
    model = LLMConfig(model="openai/gpt-test", api_key=SecretStr("offline-inline-key"))
    config = SimulationConfig(llm=model)
    config.engines.vlm_glance.llm = model
    monkeypatch.setattr(simulate, "get_config", lambda: config)
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: pytest.fail("Cloud availability needs no local probe"))
    with TestClient(app) as client:
        response = client.get("/api/engines")
    assert response.status_code == 200
    assert all(row["model_ready"] for row in response.json())
    assert "offline-inline-key" not in response.text
