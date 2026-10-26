"""Local JSON answers may wrap values or quote integer hours; schema definitions are not values."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.generators.store_setup_writer import _Setup, draft_store_setup, to_setup


FACTS = {"name": "동네 약국", "description": "의약품과 생활용품", "address": "서울 마포구", "format": "corner",
         "open_days": "weekend", "open_hour": "10", "close_hour": "18", "currency": "KRW", "rationale": "Owner details"}
FORMATS = [("corner", "Corner", "convenience", "Local shop"),
           ("drugstore", "Pharmacy", "pharmacy", "Medication and health products")]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_sdk_values_survive_all_choice_stages_and_cache_as_flat_data(monkeypatch, tmp_path, mode, wrapped):
    original = llm_client.litellm.acompletion
    calls = []
    formats = 0

    def respond(request):
        nonlocal formats
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        if "primary business type described" in system:
            answer = {"store_type": "pharmacy"}
        elif "Choose one store layout" in system:
            formats += 1
            answer = {"format": "corner" if formats == 1 else "drugstore"}
        else:
            answer = FACTS
        if wrapped:
            answer = {"properties": answer, "title": "Data", "type": "object"}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/setup-values", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            first = await draft_store_setup(client, "서울의 동네 약국, 토요일과 일요일 10시부터 18시까지", FORMATS, "ko")
            assert (first.name, first.description, first.address) == (FACTS["name"], FACTS["description"], FACTS["address"])
            assert (first.open_hour, first.close_hour, first.open_days, first.currency) == (10, 18, "weekend", "KRW")
            assert (first.template_id, first.store_type) == ("drugstore", "pharmacy")
            assert not first.warnings and len(calls) == 4
            assert await draft_store_setup(client, "서울의 동네 약국, 토요일과 일요일 10시부터 18시까지", FORMATS, "ko") == first
            assert len(calls) == client.get_usage().cached_requests == 4
            cached = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            assert len(cached) == 4 and all("properties" not in row and "title" not in row for row in cached)
            saved = next(row for row in cached if "name" in row)
            assert (saved["name"], saved["open_hour"], saved["close_hour"]) == (FACTS["name"], 10, 18)

    asyncio.run(exercise())


@pytest.mark.parametrize("value", [None, [], "not an object", 17, {"name": {"type": "string", "default": "Invented"}},
                                    {"open_hour": {"type": "integer", "default": 9}}])
def test_schema_definitions_and_nonobject_wrappers_are_not_accepted_as_empty_drafts(value):
    with pytest.raises(ValidationError):
        _Setup.model_validate_json(json.dumps({"properties": value}), strict=True)


def test_real_top_level_fields_take_precedence_over_an_extra_properties_object():
    draft = _Setup.model_validate_json(json.dumps({"name": "Root", "properties": {"name": "Other", "open_hour": 7}}), strict=True)
    assert draft.name == "Root" and draft.open_hour is None


@pytest.mark.parametrize("opening,closing,expected,warning", [
    (" 10 ", "+18", (10, 18), False), ("0", "24", (0, 24), False),
    ("20", "2", (None, None), True), ("-1", "25", (None, None), True),
])
def test_quoted_hours_keep_the_existing_pair_validation(opening, closing, expected, warning):
    draft = _Setup.model_validate_json(json.dumps({"name": "Shop", "open_hour": opening, "close_hour": closing}), strict=True)
    result = to_setup(draft, [])
    assert (result.open_hour, result.close_hour) == expected and bool(result.warnings) == warning


@pytest.mark.parametrize("value", ["10.0", "1e1", "10:00", "10 hours", "1_0", "NaN", "true", "", True, 10.5, [], {}])
def test_hour_recovery_does_not_guess_or_round_noninteger_values(value):
    with pytest.raises(ValidationError):
        _Setup.model_validate_json(json.dumps({"open_hour": value}), strict=True)
