"""Managed local readiness applies only to the server selected in provider settings."""

import pytest

from store_emulator.application import local_vlm, providers
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind


@pytest.fixture
def local_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("PARASTORE_SETTINGS_DIR", str(tmp_path / "settings"))
    for preset in providers.PRESETS.values():
        if preset.api_key_env:
            monkeypatch.delenv(preset.api_key_env, raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(providers, "_REJECTED_KEYS", {})
    mgr = local_vlm.LocalVLMManager(tmp_path)
    monkeypatch.setattr(local_vlm, "_manager", [mgr])
    return mgr


@pytest.mark.parametrize("state", ["ready", "preparing", "downloading", "starting", "error", "off", "disabled"])
@pytest.mark.parametrize("endpoint", [
    "http://127.0.0.1:9000/v1", "http://gpu-box:8081/v1", "http://127.0.0.1:8081/other/v1",
    "http://localhost:8081/v1", "http://[::1]:8081/v1",
])
@pytest.mark.parametrize("answering", [False, True])
def test_independent_endpoint_is_probed_regardless_of_managed_state(
    local_provider, monkeypatch, state, endpoint, answering,
):
    local_provider._set(state=state, api_base="http://127.0.0.1:8081/v1")
    providers.use_local_server(endpoint)
    probes = []
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: (probes.append(base), answering)[1])
    configured = LLMConfig(model="anthropic/claude-haiku-5-5")
    expected = "llamacpp:local" if answering else configured.model
    assert providers.assistive_model("", configured) == expected
    assert any(model["ref"] == "llamacpp:local" for model in providers.available_models()) is answering
    assert probes == [endpoint, endpoint]


@pytest.mark.parametrize("state", ["ready", "preparing", "downloading", "starting", "error"])
@pytest.mark.parametrize("endpoint", [
    "http://127.0.0.1:8081/v1", "http://127.0.0.1:8081/v1/",
])
def test_same_managed_endpoint_uses_its_lifecycle_state(local_provider, monkeypatch, state, endpoint):
    local_provider._set(state=state, api_base="http://127.0.0.1:8081/v1")
    providers.use_local_server(endpoint)

    def unexpected_probe(base):
        pytest.fail(f"Managed endpoint should use its known lifecycle state: {base}")

    monkeypatch.setattr(local_vlm, "server_answers", unexpected_probe)
    configured = LLMConfig(model="anthropic/claude-haiku-5-5")
    assert providers.assistive_model("", configured) == ("llamacpp:local" if state == "ready" else configured.model)


@pytest.mark.parametrize("endpoint", ["http://[broken/v1", "http://localhost:not-a-port/v1"])
def test_invalid_saved_endpoint_is_not_an_automatically_available_model(local_provider, monkeypatch, endpoint):
    local_provider._set(state="ready", api_base="http://127.0.0.1:8081/v1")
    providers.use_local_server(endpoint)
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: pytest.fail("Invalid address must not be probed"))
    configured = LLMConfig(model="anthropic/claude-haiku-5-5")
    assert providers.assistive_model("", configured) == configured.model
    assert not any(model["ref"] == "llamacpp:local" for model in providers.available_models())
