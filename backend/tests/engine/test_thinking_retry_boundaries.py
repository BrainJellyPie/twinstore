"""A provider hint must change the rejected request before another call is justified."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client as lc


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("kind", ["sync", "async", "text"])
def test_a_repeated_thinking_hint_does_not_repeat_the_same_failed_call(monkeypatch, kind):
    monkeypatch.setattr(lc, "_THINKING_OFF", {})
    monkeypatch.setattr(lc, "_REJECTED", {})
    error = RuntimeError('thinking.type: "disabled" is not supported; send "thinking": {"type": "minimal"} instead of "disabled"')
    create = Mock(side_effect=error) if kind == "sync" else AsyncMock(side_effect=error)
    client = lc.LiteLLMClient(LLMConfig(model="anthropic/thinking-retry-fixture"))
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create_with_completion=create)))
    if kind == "sync":
        monkeypatch.setattr(client, "_client", fake)
    elif kind == "async":
        monkeypatch.setattr(client, "_async_client", fake)
    else:
        monkeypatch.setattr(lc.litellm, "acompletion", create)
    with pytest.raises(RuntimeError, match="thinking.type"):
        if kind == "sync":
            client.generate_structured(Answer, "system", "user")
        elif kind == "async":
            asyncio.run(client.generate_structured_async(Answer, "system", "user"))
        else:
            asyncio.run(client.generate_text_async("system", "user"))
    assert create.call_count == 2
    assert [call.kwargs["thinking"] for call in create.call_args_list] == [{"type": "disabled"}, {"type": "minimal"}]


def test_concurrent_call_may_retry_an_old_request_after_another_call_learned_the_hint(monkeypatch):
    monkeypatch.setattr(lc, "_THINKING_OFF", {"anthropic/fixture": {"type": "minimal"}})
    error = RuntimeError('send "thinking": {"type": "minimal"} instead of "disabled"')
    assert lc._should_retry_without("anthropic/fixture", error, {"thinking": {"type": "disabled"}})
    assert not lc._should_retry_without("anthropic/fixture", error, {"thinking": {"type": "minimal"}})
