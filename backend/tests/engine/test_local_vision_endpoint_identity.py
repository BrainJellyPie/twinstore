"""An independent local endpoint must not inherit managed startup or cloud routing."""

import pytest
from pydantic import SecretStr

from store_emulator.application import local_vlm, providers
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind


@pytest.fixture
def manager(tmp_path, monkeypatch):
    for preset in providers.PRESETS.values():
        if preset.api_key_env:
            monkeypatch.delenv(preset.api_key_env, raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    mgr = local_vlm.LocalVLMManager(tmp_path)
    monkeypatch.setattr(local_vlm, "_manager", [mgr])
    settings = {ProviderKind.OPENAI: providers.ProviderSettings(kind=ProviderKind.OPENAI,
                                                               api_key=SecretStr("offline-test-key"))}
    monkeypatch.setattr(providers, "load_settings", lambda: settings)
    monkeypatch.setattr(providers, "_REJECTED_KEYS", {})
    return mgr


@pytest.mark.parametrize("endpoint", [
    "http://localhost:8081/v1", "http://[::1]:8081/v1", "http://127.0.0.1:8081/other/v1",
    "http://127.0.0.1:8081/v1?deployment=other", "http://127.0.0.1:9090/v1",
])
@pytest.mark.parametrize("state", ["preparing", "downloading", "starting", "ready", "error", "off"])
def test_independent_vision_server_keeps_its_model_and_readiness(manager, monkeypatch, endpoint, state):
    manager._set(state=state, api_base="http://127.0.0.1:8081/v1")
    probes = []
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: (probes.append(base), True)[1])
    vision = LLMConfig(model="openai/my-local-model", api_base=endpoint)
    providers.ensure_local_ready(endpoint)
    assert probes == [endpoint]
    assert providers.run_vision_model(vision) == ""
    assert providers.assistive_vision_model("", vision) == ""


@pytest.mark.parametrize("endpoint", ["http://127.0.0.1:8081/v1", "http://127.0.0.1:8081/v1/"])
def test_same_managed_endpoint_retains_startup_guard_and_optional_cloud_fallback(manager, endpoint):
    manager._set(state="starting", api_base="http://127.0.0.1:8081/v1")
    vision = LLMConfig(model="openai/local-vlm", api_base=endpoint)
    with pytest.raises(ValueError, match="not ready yet"):
        providers.ensure_local_ready(endpoint)
    assert providers.run_vision_model(vision).startswith("openai:")
    assert providers.assistive_vision_model("", vision).startswith("openai:")
    assert providers.assistive_vision_model("llamacpp:local", vision) == "llamacpp:local"
