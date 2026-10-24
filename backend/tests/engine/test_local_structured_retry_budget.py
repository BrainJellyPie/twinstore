"""Local structured calls must not multiply Instructor attempts by SDK retries."""

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


async def ask(monkeypatch, mode, base, responder, attempts=3):
    original_sync, original_async = llm_client.litellm.completion, llm_client.litellm.acompletion
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as ah:
        with httpx.Client(transport=httpx.MockTransport(responder)) as sh:
            # Keep the SDK's actual default retry policy. Do not mask it with test-only num_retries=0.
            sync = OpenAI(api_key="offline", base_url=base, http_client=sh)
            async_client = AsyncOpenAI(api_key="offline", base_url=base, http_client=ah)

            def completion(**kwargs):
                return original_sync(**{**kwargs, "client": sync, "api_key": "offline"})

            async def acompletion(**kwargs):
                return await original_async(**{**kwargs, "client": async_client, "api_key": "offline"})

            monkeypatch.setattr(llm_client.litellm, "completion", completion)
            monkeypatch.setattr(llm_client.litellm, "acompletion", acompletion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-retry-budget", api_base=base, structured_output="json_schema"))
            if mode == "raw":
                return await client.generate_text_async("Reply", "Hello")
            if mode == "sync":
                return client.generate_structured(Reply, "Reply", "Hello", max_retries=attempts)
            if mode == "sync_image":
                return client.generate_structured_with_image(Reply, "Reply", "Hello", "data:image/png;base64,AA==", max_retries=attempts)
            if mode == "async_image":
                return await client.generate_structured_with_image_async(Reply, "Reply", "Hello", "data:image/png;base64,AA==", max_retries=attempts)
            return await client.generate_structured_async(Reply, "Reply", "Hello", max_retries=attempts)


def unavailable(request, status=503):
    return httpx.Response(status, request=request, headers={"retry-after-ms": "1"}, json={
        "error": {"message": "temporarily unavailable", "type": "server_error"}})


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("base", ["http://127.0.0.1:8081/v1", "http://localhost:11434/v1", "http://[::1]:8000/v1"])
@pytest.mark.parametrize("attempts,status", [(1, 503), (3, 503), (3, 429)])
def test_local_http_attempts_match_the_structured_budget(monkeypatch, mode, base, attempts, status):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return unavailable(request, status)

    with pytest.raises(Exception):
        asyncio.run(ask(monkeypatch, mode, base, respond, attempts))
    assert len(calls) == attempts
    assert all("num_retries" not in body and "max_retries" not in body for body in calls)


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("failure", ["server", "validation"])
def test_transient_error_and_bad_output_can_recover_inside_the_existing_budget(monkeypatch, mode, failure):
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1 and failure == "server":
            return unavailable(request)
        content = '{}' if len(calls) == 1 else '{"text":"ready"}'
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}]})

    result = asyncio.run(ask(monkeypatch, mode, "http://127.0.0.1:8081/v1", respond))
    assert result.text == "ready" and len(calls) == 2


@pytest.mark.parametrize("base", ["https://api.openai.com/v1", "https://local.invalid/v1", "http://localhost.example/v1", "http://192.168.0.2/v1"])
def test_remote_endpoints_keep_their_existing_sdk_retry_policy(monkeypatch, base):
    calls = []

    def respond(request):
        calls.append(request)
        return unavailable(request)

    with pytest.raises(Exception):
        asyncio.run(ask(monkeypatch, "async", base, respond, attempts=1))
    assert len(calls) == 3


def test_raw_local_text_keeps_transport_retries_because_it_has_no_instructor_budget(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return unavailable(request)

    with pytest.raises(Exception):
        asyncio.run(ask(monkeypatch, "raw", "http://127.0.0.1:8081/v1", respond))
    assert len(calls) == 3


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("attempts", [1, 3])
def test_local_timeout_does_not_multiply_the_attempt_budget(monkeypatch, mode, attempts):
    calls = []

    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout("offline timeout", request=request)

    with pytest.raises(Exception):
        asyncio.run(ask(monkeypatch, mode, "http://127.0.0.1:8081/v1", respond, attempts))
    assert len(calls) == attempts


@pytest.mark.parametrize("base", ["http://127.2.3.4:8081/v1", "http://LOCALHOST.:8081/v1", "http://[0:0:0:0:0:0:0:1]:8081/v1"])
def test_loopback_addresses_keep_the_bounded_policy_with_other_spellings(monkeypatch, base):
    calls = []

    def respond(request):
        calls.append(request)
        return unavailable(request)

    with pytest.raises(Exception):
        asyncio.run(ask(monkeypatch, "async", base, respond, attempts=1))
    assert len(calls) == 1
