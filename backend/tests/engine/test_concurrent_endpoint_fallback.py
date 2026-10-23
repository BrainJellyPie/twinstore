"""Delayed authentication failures belong to the endpoint that received the request."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace

import pytest

from store_emulator.engine import llm_client
from store_emulator.engine.llm_client import LiteLLMClient
from tests.engine.test_llm_reroute_cache import Answer, configurations


@pytest.mark.parametrize("same_model", [False, True])
@pytest.mark.parametrize("mode", ["sync", "structured", "text"])
def test_late_failure_from_old_endpoint_reuses_working_fallback(tmp_path, monkeypatch, same_model, mode):
    first, second = configurations(tmp_path, same_model)
    first = first.model_copy(update={"max_parallel": None})
    second = second.model_copy(update={"max_parallel": None})
    reroutes = []

    def reroute(model, error):
        reroutes.append(model)
        return second

    client = LiteLLMClient(first, reroute=reroute)
    if mode == "sync":
        both = Barrier(2)
        succeeded = Event()

        def respond(schema, messages, *args):
            endpoint = client.api_base
            request = messages[-1]["content"]
            if endpoint == first.api_base:
                both.wait(timeout=5)
                if request == "slow":
                    assert succeeded.wait(5)
                raise RuntimeError("invalid API key")
            succeeded.set()
            return Answer(provider=endpoint), SimpleNamespace(usage=None)

        monkeypatch.setattr(client, "_create", respond)
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = [pool.submit(client.generate_structured, Answer, "s", request) for request in ["fast", "slow"]]
            answers = [request.result(timeout=5).provider for request in requests]
    else:
        both, succeeded = asyncio.Event(), asyncio.Event()
        entered = 0

        async def respond(**kwargs):
            nonlocal entered
            endpoint = kwargs["api_base"]
            request = kwargs["messages"][-1]["content"]
            if endpoint == first.api_base:
                entered += 1
                if entered == 2:
                    both.set()
                await both.wait()
                if request == "slow":
                    await succeeded.wait()
                raise RuntimeError("invalid API key")
            succeeded.set()
            raw = SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content=endpoint))])
            return raw if mode == "text" else (Answer(provider=endpoint), raw)

        adapter = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create_with_completion=respond)))
        monkeypatch.setattr(llm_client.instructor, "from_litellm", lambda *a, **k: adapter)
        monkeypatch.setattr(llm_client.litellm, "acompletion", respond)
        client = LiteLLMClient(first, reroute=reroute)

        async def exercise():
            calls = [client.generate_text_async("s", request) if mode == "text"
                     else client.generate_structured_async(Answer, "s", request) for request in ["fast", "slow"]]
            return await asyncio.wait_for(asyncio.gather(*calls), timeout=5)
        results = asyncio.run(exercise())
        answers = [result if mode == "text" else result.provider for result in results]
    assert answers == [second.api_base, second.api_base]
    assert reroutes == [first.model]


@pytest.mark.parametrize("mode", ["sync", "structured", "text"])
@pytest.mark.parametrize("outcome", ["candidate", "error"])
def test_delayed_fallback_selection_cannot_override_a_newer_working_endpoint(tmp_path, monkeypatch, mode, outcome):
    first, second = configurations(tmp_path, True)
    current = first.model_copy(update={"api_base": "http://127.0.0.1:11/v1"})
    entered, release = Event(), Event()

    def reroute(model, error):
        entered.set()
        assert release.wait(5)
        if outcome == "error":
            raise RuntimeError("old fallback selection failed")
        return second

    client = LiteLLMClient(first, reroute=reroute)

    def respond(*args):
        if client.api_base == first.api_base:
            raise RuntimeError("invalid API key")
        return Answer(provider=client.api_base), SimpleNamespace(usage=None)

    async def arespond(*args):
        return respond(*args)

    async def text_response(**kwargs):
        answer, _ = respond()
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content=answer.provider))])

    monkeypatch.setattr(client, "_create", respond)
    monkeypatch.setattr(client, "_acreate", arespond)
    monkeypatch.setattr(llm_client.litellm, "acompletion", text_response)
    if mode == "sync":
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(client.generate_structured, Answer, "s", "request")
            try:
                assert entered.wait(5)
                assert client._move_on(first.model, current)
            finally:
                release.set()
            result = pending.result(timeout=5).provider
    else:
        async def exercise():
            pending = asyncio.create_task(client.generate_text_async("s", "request") if mode == "text"
                                          else client.generate_structured_async(Answer, "s", "request"))
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                assert client._move_on(first.model, current)
            finally:
                release.set()
            return await asyncio.wait_for(pending, 5)
        answer = asyncio.run(exercise())
        result = answer if mode == "text" else answer.provider
    assert result == client.api_base == current.api_base
