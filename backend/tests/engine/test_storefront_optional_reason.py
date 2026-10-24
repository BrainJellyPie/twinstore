"""Optional narration must not discard complete storefront measurements."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.vision_inputs import _StorefrontRating, vlm_appeal


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("score,pull", [(0, .6), (5, 1), (10, 1.4)])
@pytest.mark.parametrize("reason", [None, "", "omitted"])
def test_complete_scores_survive_missing_explanation_and_cache(monkeypatch, tmp_path, mode, score, pull, reason):
    payload = dict(signage=score, entrance=score, window=score, upkeep=score, overall=score)
    if reason != "omitted":
        payload["reasons"] = reason
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/storefront-reason", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                first = await vlm_appeal(client, photo, model=client.model)
                assert first.method == "vlm" and first.model == client.model
                assert all(getattr(first, field) == score for field in ["signage", "entrance", "window", "upkeep", "overall"])
                assert first.attractiveness == pull and first.reasons == ""
                assert await vlm_appeal(client, photo, model=client.model) == first and len(calls) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["signage", "entrance", "window", "upkeep", "overall"])
@pytest.mark.parametrize("value", [None, -1, 11, "omitted"])
def test_measurements_are_still_required_and_bounded(field, value):
    payload = dict(signage=5, entrance=5, window=5, upkeep=5, overall=5)
    if value == "omitted":
        payload.pop(field)
    else:
        payload[field] = value
    with pytest.raises(ValidationError):
        _StorefrontRating.model_validate(payload)


@pytest.mark.parametrize("value", [12, [], {}, "x" * 241])
def test_invalid_nonnull_explanations_are_not_guessed(value):
    with pytest.raises(ValidationError):
        _StorefrontRating.model_validate(dict(signage=5, entrance=5, window=5, upkeep=5, overall=5, reasons=value))
