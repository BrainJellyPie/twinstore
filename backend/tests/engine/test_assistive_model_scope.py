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
