"""Known model choices keep their effects despite whitespace or letter-case differences."""

import asyncio
import copy
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.scenario import Crowding, DayType, EventKind, PromotionKind, Season, Weather
from store_emulator.engine import llm_client
from store_emulator.engine.scenario import apply_to_store, compile_scenario
from store_emulator.engine.scenario_writer import ScenarioDraft, describe_scenario, to_scenario
from tests.engine.test_scenario_optional_annotations import GOOD
from tests.engine.test_scenario_target_matching import target_store

CHOICES = {"weather": tuple(Weather), "season": tuple(Season), "day_type": tuple(DayType), "crowding": tuple(Crowding),
           "event": tuple(EventKind), "promotion": tuple(PromotionKind), "music": ("none", "calm", "upbeat"),
           "lighting": ("dim", "normal", "bright")}


def payload_for(field, value):
    payload = copy.deepcopy(GOOD)
    if field == "event":
        payload["events"][0]["kind"] = value
    elif field == "promotion":
        payload["promotions"][0]["kind"] = value
    else:
        payload[field] = value
    return payload


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field,value", [(field, value) for field, values in CHOICES.items() for value in values])
def test_http_known_choices_preserve_the_complete_scenario(monkeypatch, tmp_path, mode, field, value):
    store = target_store()
    before = store.model_dump()
    text = "Friday sale with an event and stock-out"
    expected = to_scenario(ScenarioDraft.model_validate(payload_for(field, value)), text, store)
    payload = payload_for(field, f"\u3000{value.upper()}\t")
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/scenario-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                result = await describe_scenario(client, text, store)
                assert result == expected
                assert compile_scenario(result.scenario) == compile_scenario(expected.scenario)
                assert apply_to_store(store, result.scenario) == apply_to_store(store, expected.scenario)
                assert result.scenario.only_days == [5] and result.scenario.stockouts == ["Lager Beer 500ml"]
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat
            assert store.model_dump() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("field", CHOICES)
@pytest.mark.parametrize("value", ["unknown", "", "rainy", "1 + 1", 1, True, [], {}])
def test_unlisted_synonyms_and_wrong_types_still_fail(field, value):
    with pytest.raises(ValidationError):
        ScenarioDraft.model_validate_json(json.dumps(payload_for(field, value)), strict=True)


@pytest.mark.parametrize("field", [field for field in CHOICES if field != "season"])
def test_null_is_not_a_known_operational_choice(field):
    with pytest.raises(ValidationError):
        ScenarioDraft.model_validate_json(json.dumps(payload_for(field, None)), strict=True)


def test_optional_season_defaults_and_identifiers_are_preserved():
    model = ScenarioDraft.model_validate_json(json.dumps({"name": "Unspecified", "season": None}), strict=True)
    assert model.season is None and model.weather == Weather.CLEAR
    data = payload_for("promotion", "Discount")
    data["promotions"][0]["target"] = "SkuCaseSensitive"
    data["promotions"][0]["label"] = "Mixed Case Sign"
    data["notes"] = "Keep this Text"
    parsed = ScenarioDraft.model_validate_json(json.dumps(data), strict=True)
    assert parsed.promotions[0].target == "SkuCaseSensitive"
    assert parsed.promotions[0].label == "Mixed Case Sign" and parsed.notes == "Keep this Text"


def test_repeated_invalid_choice_remains_a_failed_request(monkeypatch, tmp_path):
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        return llm_client.litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": json.dumps({
            "name": "Invalid", "weather": "Rainy"})}, "finish_reason": "stop", "index": 0}])

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    client = llm_client.LiteLLMClient(LLMConfig(model="openai/scenario-invalid-choice", cache_dir=str(tmp_path)))
    with pytest.raises(InstructorRetryException):
        asyncio.run(describe_scenario(client, "Rain", target_store()))
    assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
