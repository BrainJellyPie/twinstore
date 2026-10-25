"""Named self-hosted providers keep the attempt budget outside loopback too."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI, OpenAI
from openai._base_client import BaseClient
from pydantic import BaseModel

from store_emulator.application import providers
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind
from store_emulator.engine import llm_client


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("kind,base", [(ProviderKind.LLAMACPP, "http://192.168.10.8:8081/v1"),
    (ProviderKind.VLLM, "https://gpu.internal.invalid/v1"), (ProviderKind.CUSTOM, "http://[fd00::2]:8001/v1")])
@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("failure", ["503", "429", "timeout"])
def test_named_remote_local_servers_do_not_multiply_structured_attempts(monkeypatch, tmp_path, kind, base, mode, failure):
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    # Retain the SDK's actual retry decisions; skip only their backoff delays.
    monkeypatch.setattr(BaseClient, "_calculate_retry_timeout", lambda *args, **kwargs: 0)
    config = providers.resolve_model(f"{kind.value}:served", base=LLMConfig(cache_dir=str(tmp_path)),
        settings={kind: providers.ProviderSettings(kind=kind, api_base=base, api_key="offline")})
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        if failure == "timeout":
            raise httpx.ReadTimeout("offline timeout", request=request)
        return httpx.Response(int(failure), request=request,
            json={"error": {"message": "temporarily unavailable", "type": "server_error"}})
    original_sync, original_async = llm_client.litellm.completion, llm_client.litellm.acompletion
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as ah:
            with httpx.Client(transport=httpx.MockTransport(respond)) as sh:
                sync = OpenAI(api_key="offline", base_url=base, http_client=sh)
                asynchronous = AsyncOpenAI(api_key="offline", base_url=base, http_client=ah)
                def completion(**kwargs):
                    return original_sync(**{**kwargs, "client": sync})
                async def acompletion(**kwargs):
                    return await original_async(**{**kwargs, "client": asynchronous})
                monkeypatch.setattr(llm_client.litellm, "completion", completion)
                monkeypatch.setattr(llm_client.litellm, "acompletion", acompletion)
                client = llm_client.LiteLLMClient(config)
                with pytest.raises(InstructorRetryException):
                    if mode == "sync":
                        client.generate_structured(Answer, "Reply", "Hello", max_retries=3)
                    elif mode == "sync_image":
                        client.generate_structured_with_image(Answer, "Reply", "Hello", "offline-image", max_retries=3)
                    elif mode == "async_image":
                        await client.generate_structured_with_image_async(Answer, "Reply", "Hello", "offline-image", max_retries=3)
                    else:
                        await client.generate_structured_async(Answer, "Reply", "Hello", max_retries=3)
                assert len(calls) == 3
                assert not list(tmp_path.glob("*/*.json"))
                assert all("num_retries" not in body and "max_retries" not in body for body in calls)
    asyncio.run(exercise())


@pytest.mark.parametrize("reference,raw,expected", [("vllm:served", False, 1), ("vllm:served", True, 3),
    ("openai:served", False, 3), ("openai/served", False, 3)])
def test_retry_policy_is_runtime_only_and_does_not_leak_into_other_providers_or_raw_text(monkeypatch, reference, raw, expected):
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    monkeypatch.setattr(providers, "_on_local_server", lambda config: config)
    monkeypatch.setattr(BaseClient, "_calculate_retry_timeout", lambda *args, **kwargs: 0)
    base = "https://gpu.internal.invalid/v1"
    settings = {kind: providers.ProviderSettings(kind=kind, api_base=base, api_key="offline")
                for kind in (ProviderKind.VLLM, ProviderKind.OPENAI)}
    local = providers.resolve_model("vllm:served", settings=settings)
    config = providers.resolve_model(reference, base=local, settings=settings)
    assert "structured_sdk_retries" not in config.model_dump()
    calls = []
    async def send(self, request, *args, **kwargs):
        calls.append(request)
        return httpx.Response(503, request=request, json={"error": {"message": "temporarily unavailable", "type": "server_error"}})
    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    client = llm_client.LiteLLMClient(config)
    async def exercise():
        with pytest.raises(Exception):
            if raw:
                await client.generate_text_async("Reply", "Hello")
            else:
                await client.generate_structured_async(Answer, "Reply", "Hello", max_retries=1)
    asyncio.run(exercise())
    assert len(calls) == expected
