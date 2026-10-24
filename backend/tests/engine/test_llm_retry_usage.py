"""Failed structured output still consumed model requests and reported tokens."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client


class Reply(BaseModel):
    text: str


async def exercise(monkeypatch, mode, respond, cache_dir, *, succeed, attempts=3, reroute=None):
    original_sync, original_async = llm_client.litellm.completion, llm_client.litellm.acompletion
    base = "http://127.0.0.1:8081/v1"
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as ah:
        with httpx.Client(transport=httpx.MockTransport(respond)) as sh:
            sync = OpenAI(api_key="offline", base_url=base, http_client=sh)
            async_client = AsyncOpenAI(api_key="offline", base_url=base, http_client=ah)

            def completion(**kwargs):
                return original_sync(**{**kwargs, "client": sync, "api_key": "offline"})

            async def acompletion(**kwargs):
                return await original_async(**{**kwargs, "client": async_client, "api_key": "offline"})

            monkeypatch.setattr(llm_client.litellm, "completion", completion)
            monkeypatch.setattr(llm_client.litellm, "acompletion", acompletion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-usage", api_base=base,
                structured_output="json_schema", cache_dir=cache_dir), reroute=reroute)

            async def ask():
                if mode == "sync":
                    return client.generate_structured(Reply, "Reply", "Hello", max_retries=attempts)
                if mode == "sync_image":
                    return client.generate_structured_with_image(Reply, "Reply", "Hello", "data:image/png;base64,AA==", max_retries=attempts)
                if mode == "async_image":
                    return await client.generate_structured_with_image_async(Reply, "Reply", "Hello", "data:image/png;base64,AA==", max_retries=attempts)
                if mode == "raw":
                    return await client.generate_text_async("Reply", "Hello")
                return await client.generate_structured_async(Reply, "Reply", "Hello", max_retries=attempts)

            if succeed:
                first = await ask()
                usage = client.get_usage()
                second = await ask()
                if mode != "raw":
                    assert first.model_dump() == second.model_dump()
                    assert client.get_usage().cached_requests == 1
                    assert client.get_usage().requests == usage.requests + 1
                    assert client.get_usage().total_tokens == usage.total_tokens
            else:
                with pytest.raises(Exception):
                    await ask()
                usage = client.get_usage()
            client.reset_usage()
            assert client.get_usage().model_dump() == dict(prompt_tokens=0, completion_tokens=0, total_tokens=0, requests=0, cached_requests=0)
            return usage


def response(request, content, *, finish="stop", tokens=(10, 5)):
    prompt, completion = tokens
    return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
        "model": "local", "usage": {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion},
        "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": content}}]})


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("kind", ["first_success", "corrected", "invalid", "truncated", "provider_error"])
def test_usage_includes_every_attempt_and_tokens_from_failed_completions(monkeypatch, tmp_path, mode, kind):
    calls = []

    def respond(request):
        calls.append(request)
        if kind == "provider_error":
            return httpx.Response(400, request=request, json={"error": {"message": "bad request", "type": "invalid_request_error"}})
        good = kind == "first_success" or (kind == "corrected" and len(calls) > 1)
        return response(request, '{"text":"ready"}' if good else '{}', finish="length" if kind == "truncated" else "stop")

    success = kind in {"first_success", "corrected"}
    usage = asyncio.run(exercise(monkeypatch, mode, respond, str(tmp_path), succeed=success))
    attempts = 1 if kind == "first_success" else 2 if kind == "corrected" else 3
    received = 0 if kind == "provider_error" else attempts
    assert len(calls) == usage.requests == attempts
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (10 * received, 5 * received, 15 * received)
    assert usage.cached_requests == 0


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
def test_failed_provider_usage_is_retained_when_fallback_succeeds(monkeypatch, tmp_path, mode):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body["model"])
        if body["model"] == "local-usage":
            return httpx.Response(401, request=request, json={"error": {"message": "invalid api key", "type": "authentication_error"}})
        return response(request, '{"text":"ready"}')

    def reroute(model, error):
        return LLMConfig(model="openai/local-fallback", api_base="http://127.0.0.1:8081/v1", cache_dir=str(tmp_path))

    usage = asyncio.run(exercise(monkeypatch, mode, respond, str(tmp_path), succeed=True, reroute=reroute))
    assert calls == ["local-usage"] * 3 + ["local-fallback"]
    assert usage.requests == 4 and usage.total_tokens == 15


def test_concurrent_retry_counters_do_not_leak_between_calls(monkeypatch, tmp_path):
    from collections import Counter
    from litellm import ModelResponse

    calls = Counter()

    async def completion(**kwargs):
        key = next(m["content"] for m in kwargs["messages"] if m["role"] == "user")
        calls[key] += 1
        await asyncio.sleep(0)
        valid = key != "fail" and calls[key] > 1
        return ModelResponse(model="openai/local", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            choices=[{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"text":"ready"}' if valid else '{}'}}])

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    client = llm_client.LiteLLMClient(LLMConfig(model="openai/local", api_base="http://127.0.0.1:8081/v1", cache_dir=str(tmp_path)))

    async def run():
        return await asyncio.gather(*[client.generate_structured_async(Reply, "Reply", key, max_retries=3)
                                      for key in ["first", "second", "fail"]], return_exceptions=True)

    results = asyncio.run(run())
    assert results[0].text == results[1].text == "ready" and isinstance(results[2], Exception)
    assert calls == {"first": 2, "second": 2, "fail": 3}
    usage = client.get_usage()
    assert usage.requests == 7 and usage.cached_requests == 0
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (70, 35, 105)
    assert len(list(tmp_path.glob("*/*.json"))) == 2
