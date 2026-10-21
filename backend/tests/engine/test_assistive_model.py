"""Assistive features (interviews, commentary, set-up helpers) use a provider that has a key when the app's text
model has none; simulation runs never fall back."""

import pytest

from store_emulator.application.providers import assistive_model, text_model_fallback
from store_emulator.domain.config import LLMConfig

KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DASHSCOPE_API_KEY", "OPENROUTER_API_KEY")


@pytest.fixture
def keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no saved provider settings
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)

    def set_keys(*names: str) -> None:
        for n in names:
            monkeypatch.setenv(n, "test-key")
    return set_keys


def test_a_text_model_without_a_key_falls_back_to_a_fast_model_that_has_one(keys):
    keys("ANTHROPIC_API_KEY")
    config = LLMConfig(model="gemini/gemini-3.1-pro-preview")
    assert assistive_model("", config) == "anthropic:claude-haiku-5-5"
    assert assistive_model("  openai:gpt-6-sol ", config) == "openai:gpt-6-sol"  # an explicit pick always wins
    assert text_model_fallback("anthropic:claude-opus-5-5") is None  # its provider has a key


def test_the_text_model_is_kept_when_it_has_a_key_or_nothing_else_does(keys):
    assert assistive_model("", LLMConfig(model="gemini/gemini-3.1-pro-preview")) == "gemini/gemini-3.1-pro-preview"
    keys("GEMINI_API_KEY", "OPENAI_API_KEY")
    assert assistive_model("", LLMConfig(model="gemini/gemini-3.1-pro-preview")) == "gemini/gemini-3.1-pro-preview"
    assert text_model_fallback("anthropic:claude-haiku-5-5") == "openai:gpt-6-luna"
    assert text_model_fallback("ollama_chat/qwen3.5:2b") is None  # local models need no key


@pytest.mark.parametrize(('primary', 'alternative_key'), [
    ('gemini/gemini-3.1-pro-preview', 'ANTHROPIC_API_KEY'),
    ('anthropic/claude-haiku-5-5', 'OPENAI_API_KEY'),
    ('openai/gpt-6-luna', 'GEMINI_API_KEY'),
])
def test_an_explicit_config_key_keeps_the_apps_model(keys, primary, alternative_key):
    from pydantic import SecretStr
    keys(alternative_key)
    config = LLMConfig(model=primary, api_key=SecretStr('fake-direct-config-key'))
    assert assistive_model('', config) == primary
