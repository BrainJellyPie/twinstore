"""A server's rejected request options must not affect another server's same model alias."""

import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client as lc


@pytest.mark.parametrize("explicit_first", [False, True])
@pytest.mark.parametrize("option,error", [
    ("temperature", "Unsupported parameter: temperature is not supported"),
    ("max_tokens", "Unsupported parameter: 'max_tokens' is not supported; use max_completion_tokens instead"),
    ("thinking", "Unsupported parameter: thinking is not supported"),
    ("hint", 'send "thinking": {"type": "minimal"} instead of "disabled"'),
    ("reasoning_effort", "Unsupported parameter: reasoning_effort is not supported"),
])
def test_parameter_learning_stays_with_the_receiving_endpoint(monkeypatch, explicit_first, option, error):
    monkeypatch.setattr(lc, "_REJECTED", {})
    monkeypatch.setattr(lc, "_THINKING_OFF", {})
    model = "anthropic/shared-option-alias" if option in ("thinking", "hint") else "openai/gpt-shared-option-alias"
    # OpenAI-hosted paths keep the reasoning option enabled in both requests; no network calls are made.
    first_config = LLMConfig(model=model, api_base="https://api.openai.com/v1/first" if explicit_first else None)
    other_config = first_config.model_copy(update={"api_base": "https://api.openai.com/v1/second"})
    first, same, other = [lc.LiteLLMClient(config) for config in [first_config, first_config, other_config]]
    sent, unchanged = first._call_kwargs(None), other._call_kwargs(None)
    assert lc._should_retry_without(model, RuntimeError(error), sent)
    changed = first._call_kwargs(None)
    assert changed != sent
    assert same._call_kwargs(None) == changed
    assert other._call_kwargs(None) == unchanged
