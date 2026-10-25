"""Known local capacity belongs to an endpoint, not just the special llama.cpp model name."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel

from store_emulator.application import local_vlm, providers
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ModelRef
from store_emulator.engine import llm_client


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("reference", ["llamacpp:local", "llamacpp:served", "custom:served", "vllm:served",
                                      "openai/served", "default-address"])
@pytest.mark.parametrize("configured", [None, 1, 4])
@pytest.mark.parametrize("image", [False, True])
def test_model_aliases_and_existing_client_limits_respect_known_capacity(monkeypatch, tmp_path, reference, configured, image):
    active = "http://127.0.0.1:9090/v1"
    selected = "http://127.0.0.1:8081/v1" if reference == "default-address" else active
    ref = "openai/served" if reference == "default-address" else reference
    manager = local_vlm.LocalVLMManager(tmp_path)
    manager._set(state="ready", api_base=active, slots=2)
    monkeypatch.setattr(local_vlm, "_manager", [manager])
    parsed = ModelRef.parse(ref)
    settings = {parsed.provider: providers.ProviderSettings(kind=parsed.provider, api_base=selected)} if parsed else {}
    config = providers.resolve_model(ref, base=LLMConfig(api_base=selected, max_tokens=100, max_parallel=configured), settings=settings)
    config.structured_output = "json_schema" if image else "json"
    expected = min(2, configured) if configured is not None else 2
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
            "model": "served", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"text": "ok"})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url=config.api_base, http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(config)

            async def ask(i):
                if image:
                    return await client.generate_structured_with_image_async(Answer, "Reply", str(i), "data:image/png;base64,AA==")
                return await client.generate_structured_async(Answer, "Reply", str(i))

            answers = await asyncio.wait_for(asyncio.gather(*(ask(i) for i in range(6))), timeout=5)
            assert all(answer.text == "ok" for answer in answers)

    asyncio.run(exercise())
    assert calls == 6 and peak == expected
    assert config.max_parallel == expected and config.api_base == active
