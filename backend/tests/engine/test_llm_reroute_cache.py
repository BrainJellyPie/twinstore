"""Queued requests must not cache a fallback provider's answer under the original model."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine import llm_client


class Answer(BaseModel):
    provider: str


def configurations(tmp_path, same_model):
    first = LLMConfig(model="openai/first", api_base="http://127.0.0.1:9/v1",
                      cache_dir=str(tmp_path), max_parallel=1)
    second = first.model_copy(update={"model": first.model if same_model else "openai/second",
                                      "api_base": "http://127.0.0.1:10/v1"})
    return first, second


@pytest.mark.parametrize("same_model", [False, True])
def test_queued_call_uses_the_fallback_cache_and_does_not_poison_original_provider(tmp_path, monkeypatch, same_model):
    first, second = configurations(tmp_path, same_model)
    client = LiteLLMClient(first)
    calls = []

    async def respond(*args):
        calls.append(client.api_base)
        return Answer(provider=client.api_base), SimpleNamespace(usage=None)

    monkeypatch.setattr(client, "_acreate", respond)

    async def exercise():
        slots = client._slots_here()
        await slots.acquire()
        pending = asyncio.create_task(client.generate_structured_async(Answer, "system", "request"))
        await asyncio.sleep(0)
        assert not pending.done()
        assert client._move_on(first.model, second)
        slots.release()
        result = await pending
        again = await client.generate_structured_async(Answer, "system", "request")
        assert result.provider == again.provider == second.api_base
        assert calls == [second.api_base]

    asyncio.run(exercise())
    original = LiteLLMClient(first)
    messages, _ = original._messages("system", "request")
    assert original._cache_get(original._cache_path(Answer, messages, None), Answer) is None


@pytest.mark.parametrize("same_model", [False, True])
def test_inflight_sync_retry_cannot_write_a_changed_provider_to_the_old_cache(tmp_path, monkeypatch, same_model):
    first, second = configurations(tmp_path, same_model)
    client = LiteLLMClient(first)
    entered, release = Event(), Event()

    def respond(*args):
        entered.set()
        assert release.wait(5)
        # A provider retry reads the client's new configuration after another call reroutes it.
        return Answer(provider=client.api_base), SimpleNamespace(usage=None)

    monkeypatch.setattr(client, "_create", respond)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.generate_structured, Answer, "system", "request")
        try:
            assert entered.wait(5)
            assert client._move_on(first.model, second)
        finally:
            release.set()
        assert pending.result(timeout=5).provider == second.api_base
    original = LiteLLMClient(first)
    messages, _ = original._messages("system", "request")
    assert original._cache_get(original._cache_path(Answer, messages, None), Answer) is None


@pytest.mark.parametrize("plain_text", [False, True])
def test_old_provider_rejection_does_not_disable_fallback_models_parameters(tmp_path, monkeypatch, plain_text):
    first, second = configurations(tmp_path, False)
    first = first.model_copy(update={"model": f"openai/original-retry-{plain_text}"})
    second = second.model_copy(update={"model": f"openai/fallback-retry-{plain_text}"})
    entered, release = asyncio.Event(), asyncio.Event()
    sent = []

    async def respond(**kwargs):
        sent.append(kwargs)
        if kwargs["model"] == first.model:
            entered.set()
            await release.wait()
            raise RuntimeError("Unsupported parameter: temperature is not supported")
        raw = SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content=kwargs["api_base"]))])
        return raw if plain_text else (Answer(provider=kwargs["api_base"]), raw)

    adapter = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create_with_completion=respond)))
    monkeypatch.setattr(llm_client.instructor, "from_litellm", lambda *a, **k: adapter)
    monkeypatch.setattr(llm_client.litellm, "acompletion", respond)
    client = LiteLLMClient(first)

    async def exercise():
        pending = asyncio.create_task(client.generate_text_async("system", "request") if plain_text
                                      else client.generate_structured_async(Answer, "system", "request"))
        await entered.wait()
        assert client._move_on(first.model, second)
        release.set()
        result = await pending
        assert (result if plain_text else result.provider) == second.api_base
    asyncio.run(exercise())
    assert [call["model"] for call in sent] == [first.model, second.model]
    assert sent[1].get("temperature") == second.temperature
    original = LiteLLMClient(first)
    messages, _ = original._messages("system", "request")
    assert original._cache_get(original._cache_path(Answer, messages, None), Answer) is None


def test_queued_text_request_also_switches_to_the_new_provider(tmp_path, monkeypatch):
    first, second = configurations(tmp_path, False)
    calls = []

    async def respond(**kwargs):
        calls.append(kwargs["api_base"])
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content=kwargs["api_base"]))])

    monkeypatch.setattr(llm_client.litellm, "acompletion", respond)
    client = LiteLLMClient(first)

    async def exercise():
        slots = client._slots_here()
        await slots.acquire()
        pending = asyncio.create_task(client.generate_text_async("system", "request"))
        await asyncio.sleep(0)
        assert not pending.done()
        assert client._move_on(first.model, second)
        slots.release()
        assert await pending == second.api_base

    asyncio.run(exercise())
    assert calls == [second.api_base]
