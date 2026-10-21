"""A pending managed llama.cpp startup must not block independent model servers."""

import pytest

from store_emulator.application import local_vlm, providers
from store_emulator.application.providers import ProviderSettings
from store_emulator.application.simulation import RunOptions, apply_options
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.providers import ProviderKind


@pytest.fixture
def starting_manager(tmp_path, monkeypatch):
    mgr = local_vlm.LocalVLMManager(tmp_path)
    mgr._set(state="downloading", message="Downloading the managed model")
    monkeypatch.setattr(local_vlm, "_manager", [mgr])
    monkeypatch.setattr(providers, "load_settings", lambda: {})
    return mgr


@pytest.mark.parametrize("ref, settings", [
    ("vllm:my-model", {}),
    ("ollama:my-model", {}),
    ("custom:my-model", {ProviderKind.CUSTOM: ProviderSettings(kind=ProviderKind.CUSTOM, api_base="http://127.0.0.1:9000/v1")}),
    ("llamacpp:local", {ProviderKind.LLAMACPP: ProviderSettings(kind=ProviderKind.LLAMACPP, api_base="http://gpu-box:8081/v1")}),
])
def test_unrelated_local_or_remote_servers_are_not_blocked(starting_manager, monkeypatch, ref, settings):
    monkeypatch.setattr(providers, "load_settings", lambda: settings)
    config = apply_options(SimulationConfig(), RunOptions(engine_type=EngineType.VLM_GLANCE, model=ref))
    providers.ensure_resolvable(config)


@pytest.mark.parametrize("state", ["preparing", "downloading", "starting"])
def test_managed_model_is_rejected_while_starting(starting_manager, state):
    starting_manager._set(state=state)
    config = apply_options(SimulationConfig(), RunOptions(engine_type=EngineType.VLM_GLANCE, model="llamacpp:local"))
    with pytest.raises(ValueError, match="not ready yet"):
        providers.ensure_resolvable(config)


@pytest.mark.parametrize("endpoint", ["http://127.0.0.1:8081/v1", "http://localhost:8081/v1/"])
def test_raw_model_keeps_its_endpoint_for_readiness_check(starting_manager, endpoint):
    config = SimulationConfig(llm=LLMConfig(model="openai/local-model", api_base=endpoint))
    with pytest.raises(ValueError, match="not ready yet"):
        providers.ensure_resolvable(config)


def test_custom_provider_on_managed_endpoint_is_rejected(starting_manager, monkeypatch):
    starting_manager._set(api_base="http://127.0.0.1:9090/v1")
    monkeypatch.setattr(providers, "load_settings", lambda: {
        ProviderKind.CUSTOM: ProviderSettings(kind=ProviderKind.CUSTOM, api_base="http://localhost:9090/v1"),
    })
    config = apply_options(SimulationConfig(), RunOptions(engine_type=EngineType.VLM_GLANCE, model="custom:my-model"))
    with pytest.raises(ValueError, match="not ready yet"):
        providers.ensure_resolvable(config)
