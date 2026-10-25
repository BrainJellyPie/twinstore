"""Equivalent endpoint spelling must preserve the local server's request-capacity limit."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel

from store_emulator.application import local_vlm, providers
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind
from store_emulator.engine import llm_client


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("active,selected", [
    ("http://127.0.0.1:8081/v1", "http://127.0.0.1:8081/v1"),
    ("http://127.0.0.1:8081/v1", "http://127.0.0.1:8081/v1/"),
    ("http://localhost:8081/v1", "http://LOCALHOST:8081/v1/"),
])
@pytest.mark.parametrize("slots", [1, 2])
@pytest.mark.parametrize("call", ["json_text", "json_image", "schema_text", "schema_image", "raw_text"])
def test_equivalent_selected_endpoint_respects_real_http_request_capacity(monkeypatch, tmp_path, active, selected, slots, call):
    manager = local_vlm.LocalVLMManager(tmp_path)
    manager._set(state="ready", api_base=active, slots=slots)
    monkeypatch.setattr(local_vlm, "_manager", [manager])
    settings = {ProviderKind.LLAMACPP: providers.ProviderSettings(kind=ProviderKind.LLAMACPP, api_base=selected)}
    config = providers.resolve_model("llamacpp:local", base=LLMConfig(max_tokens=100), settings=settings)
    config.structured_output = "json_schema" if call.startswith("schema") else "json"
    current = peak = calls = 0
    original = llm_client.litellm.acompletion

    async def respond(request):
        nonlocal current, peak, calls
        current += 1
        calls += 1
        peak = max(peak, current)
        await asyncio.sleep(.01)
        current -= 1
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"text": "ok"})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url=selected, http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(config)

            async def ask(i):
                if call == "raw_text":
                    return Answer.model_validate_json(await client.generate_text_async("Reply", str(i)))
                if call.endswith("image"):
                    return await client.generate_structured_with_image_async(Answer, "Reply", str(i), "data:image/png;base64,AA==")
                return await client.generate_structured_async(Answer, "Reply", str(i))

            answers = await asyncio.wait_for(asyncio.gather(*(ask(i) for i in range(6))), timeout=5)
            assert all(answer.text == "ok" for answer in answers)

    asyncio.run(exercise())
    assert calls == 6 and peak == slots
    assert config.max_parallel == slots and config.api_base == selected


@pytest.mark.parametrize("selected", [
    "http://localhost:8081/v1", "http://127.0.0.1:9000/v1", "https://127.0.0.1:8081/v1",
    "http://127.0.0.1:8081/other/v1", "http://127.0.0.1:8081/v1?deployment=other",
    "http://user@127.0.0.1:8081/v1", "http://localhost:not-a-port/v1",
])
def test_other_endpoints_do_not_borrow_slots(monkeypatch, tmp_path, selected):
    manager = local_vlm.LocalVLMManager(tmp_path)
    manager._set(state="ready", api_base="http://127.0.0.1:8081/v1", slots=2)
    monkeypatch.setattr(local_vlm, "_manager", [manager])
    settings = {ProviderKind.LLAMACPP: providers.ProviderSettings(kind=ProviderKind.LLAMACPP, api_base=selected)}
    config = providers.resolve_model("llamacpp:local", base=LLMConfig(max_parallel=3), settings=settings)
    assert config.max_parallel == 3


@pytest.mark.parametrize("state,slots", [("off", 2), ("starting", 2), ("error", 2), ("ready", 0)])
def test_unavailable_or_unknown_capacity_preserves_the_configured_limit(monkeypatch, tmp_path, state, slots):
    manager = local_vlm.LocalVLMManager(tmp_path)
    manager._set(state=state, api_base="http://127.0.0.1:8081/v1", slots=slots)
    monkeypatch.setattr(local_vlm, "_manager", [manager])
    config = providers.resolve_model("llamacpp:local", base=LLMConfig(max_parallel=3), settings={})
    assert config.max_parallel == 3
