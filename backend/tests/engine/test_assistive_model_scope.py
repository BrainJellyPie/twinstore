"""Automatic fallback must preserve configured endpoints and exclude disabled providers."""
import pytest
from pydantic import SecretStr

from store_emulator.application.providers import (
    PRESETS, ProviderSettings, assistive_model, text_model_fallback,
)
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('PARASTORE_SETTINGS_DIR', str(tmp_path / 'settings'))
    for preset in PRESETS.values():
        if preset.api_key_env:
            monkeypatch.delenv(preset.api_key_env, raising=False)


@pytest.mark.parametrize('endpoint', ['http://127.0.0.1:9000/v1', 'http://localhost:8081/v1', 'https://custom.example/v1'])
@pytest.mark.parametrize('model', ['openai/self-hosted-model', 'anthropic/configured-model'])
def test_a_configured_endpoint_does_not_fall_back_to_another_provider(monkeypatch, endpoint, model):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-alternative-key')
    config = LLMConfig(model=model, api_base=endpoint)
    assert assistive_model('', config) == model
    assert assistive_model(' gemini:chosen-model ', config) == 'gemini:chosen-model'


@pytest.mark.parametrize('provider', [ProviderKind.ANTHROPIC, ProviderKind.OPENAI, ProviderKind.GEMINI, ProviderKind.QWEN])
@pytest.mark.parametrize('source', ['settings', 'env'])
def test_disabled_providers_are_not_automatic_fallbacks(monkeypatch, provider, source):
    setting = ProviderSettings(kind=provider, enabled=False)
    if source == 'settings':
        setting.api_key = SecretStr('fake-disabled-key')
    else:
        monkeypatch.setenv(PRESETS[provider].api_key_env, 'fake-disabled-key')
    primary = 'anthropic/missing' if provider == ProviderKind.GEMINI else 'gemini/missing'
    assert text_model_fallback(primary, {provider: setting}) is None
    setting.enabled = True
    assert text_model_fallback(primary, {provider: setting}).startswith(f'{provider.value}:')


def test_fallback_skips_a_disabled_first_provider_and_uses_the_next_ready_one():
    settings = {
        ProviderKind.ANTHROPIC: ProviderSettings(kind=ProviderKind.ANTHROPIC, enabled=False, api_key=SecretStr('fake-disabled')),
        ProviderKind.OPENAI: ProviderSettings(kind=ProviderKind.OPENAI, enabled=True, api_key=SecretStr('fake-enabled')),
    }
    assert text_model_fallback('gemini/missing', settings).startswith('openai:')


def stopped_local_model(monkeypatch):
    from types import SimpleNamespace
    from store_emulator.application import local_vlm
    status = SimpleNamespace(state='off', api_base=None)
    monkeypatch.setattr(local_vlm, 'manager', lambda: SimpleNamespace(status=lambda: status))
    return status


@pytest.mark.parametrize('endpoint', [
    'http://127.0.0.1:9000/v1', 'http://localhost:9000/v1', 'http://[::1]:9000/v1',
    'https://127.0.0.1:8081/v1', 'http://127.0.0.1:8081/custom/v1',
])
def test_a_custom_local_vision_endpoint_is_not_replaced_by_a_cloud_model(monkeypatch, endpoint):
    from store_emulator.application.providers import assistive_vision_model
    stopped_local_model(monkeypatch)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fake-alternative')
    config = LLMConfig(model='openai/custom-vision', api_base=endpoint)
    assert assistive_vision_model('', config) == ''
    assert assistive_vision_model(' openai:explicit-vision ', config) == 'openai:explicit-vision'


@pytest.mark.parametrize('provider', [ProviderKind.ANTHROPIC, ProviderKind.OPENAI, ProviderKind.GEMINI, ProviderKind.QWEN])
@pytest.mark.parametrize('source', ['settings', 'env'])
def test_vision_fallback_excludes_disabled_providers(monkeypatch, provider, source):
    from store_emulator.application import providers
    stopped_local_model(monkeypatch)
    setting = ProviderSettings(kind=provider, enabled=False)
    if source == 'settings':
        setting.api_key = SecretStr('fake-disabled')
    else:
        monkeypatch.setenv(PRESETS[provider].api_key_env, 'fake-disabled')
    monkeypatch.setattr(providers, 'load_settings', lambda: {provider: setting})
    config = LLMConfig(model='openai/local-vlm', api_base='http://127.0.0.1:8081/v1')
    assert providers.assistive_vision_model('', config) == ''
    setting.enabled = True
    assert providers.assistive_vision_model('', config).startswith(f'{provider.value}:')


@pytest.mark.parametrize('endpoint', ['http://127.0.0.1:8081/v1', 'http://localhost:8081/v1', 'http://[::1]:8081/v1'])
def test_the_managed_vision_endpoint_can_fall_back_until_it_is_ready(monkeypatch, endpoint):
    from store_emulator.application.providers import assistive_vision_model
    status = stopped_local_model(monkeypatch)
    status.api_base = endpoint
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fake-alternative')
    config = LLMConfig(model='openai/local-vlm', api_base=endpoint)
    assert assistive_vision_model('', config).startswith('anthropic:')
    status.state = 'ready'
    assert assistive_vision_model('', config) == ''
