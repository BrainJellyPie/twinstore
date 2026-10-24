"""A missing address or explanation must not discard the rest of a store draft."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.generators.store_setup_writer import _Setup, draft_store_setup


FIELDS = ["name", "description", "address", "format", "rationale"]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("missing", [False, True])
def test_optional_null_or_omitted_text_preserves_the_draft_and_cache(monkeypatch, tmp_path, mode, field, missing):
    original = llm_client.litellm.acompletion
    calls = []
    answer = {"name": "Corner shop", "description": "A small neighborhood shop.", "address": "Seoul",
        "format": "Campus", "rationale": "A convenience store", "open_days": "weekday", "open_hour": 9,
        "close_hour": 22, "currency": "KRW"}
    if missing:
        answer.pop(field)
    else:
        answer[field] = None

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/setup-draft", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            args = (client, "A small store in Seoul, weekdays nine to twenty-two", [("campus", "Campus", "convenience", "A campus shop")])
            first = await draft_store_setup(*args)
            assert first == await draft_store_setup(*args) and client.get_usage().cached_requests == 1
            assert (first.open_days, first.open_hour, first.close_hour, first.currency) == ("weekday", 9, 22, "KRW")
            assert first.template_id == ("" if field == "format" else "campus")
            for key in FIELDS:
                if key != "format":
                    assert getattr(first, key) == ("" if field == key else answer[key])
            assert not first.warnings

    asyncio.run(exercise())
    assert len(calls) == 1


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [17, [], {}])
def test_wrong_non_text_values_still_fail(field, value):
    with pytest.raises(ValidationError):
        _Setup.model_validate_json(json.dumps({field: value}), strict=True)
