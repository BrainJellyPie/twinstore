"""Explicit major-unit model amounts become exact minor-unit persisted budgets."""
import asyncio
import json
import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI
from pydantic import ValidationError
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen

PERSON = dict(identity="resident", purpose="buy books", age_group="30s", gender="Female", description="A neighborhood reader", intent="Browse books", preferred_categories=["books"])
PROFILE = gen.TradeAreaProfile(keywords=[], identities=["resident"], purposes=["buy books"])
HOURS = [gen.HourlyProfile(hour=9, visitor_count=1, person_types=["resident"])]

def response_model(currency):
    captured = []
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            captured.append(schema)
            return schema(personas=[PERSON])
    asyncio.run(gen.generate_personas_for_day(Model(), "offline", PROFILE, Weekday.MON, HOURS, currency=currency))
    return captured[0]

@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency,low,high,expected", [
    ("EUR", "5", "20", (500, 2000)), ("USD", "2.50", "7.75", (250, 775)),
    ("jpy", "500", "1500", (500, 1500)), ("KRW", "3000", "10000", (3000, 10000)),
    ("EUR", 5, 20, (500, 2000)), ("EUR", "0", "0", (0, 0)),
    ("EUR", "0.01", "90071992547409.91", (1, 9007199254740991)),
    ("JPY", "0", "9007199254740991", (0, 9007199254740991)),
])
def test_sdk_converts_once_and_caches_minor_integers(monkeypatch, tmp_path, mode, currency, low, high, expected):
    original, calls = llm_client.litellm.acompletion, []
    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if mode == "json_schema":
            props = body["response_format"]["json_schema"]["schema"]["$defs"]["LabelledPersona"]["properties"]
            assert "budget_min" not in props and "budget_max" not in props
            assert props["budget_min_major"]["type"] == props["budget_max_major"]["type"] == "string"
        data = {"personas": [{**PERSON, "budget_min_major": low, "budget_max_major": high}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(data)}}]})
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})
            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-money", api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            async def generate():
                return await gen.generate_personas_for_day(client, "offline", PROFILE, Weekday.MON, HOURS, currency=currency, seed=4)
            people = await generate()
            assert len(people) == 1 and (people[0].budget_min, people[0].budget_max) == expected
            assert await generate() == people and len(calls) == client.get_usage().cached_requests == 1
            data = json.loads(next(tmp_path.rglob("*.json")).read_text())["result"]["personas"][0]
            assert (data["budget_min"], data["budget_max"]) == expected
            assert not {"budget_min_major", "budget_max_major"}.intersection(data)
    asyncio.run(exercise())

@pytest.mark.parametrize("currency,amount", [
    ("EUR", "90071992547409.92"), ("JPY", "9007199254740992"), ("EUR", "1.001"), ("JPY", "1.50"),
    ("EUR", "-1"), ("EUR", "1e3"), ("EUR", "5,50"), ("EUR", "€5"), ("EUR", "NaN"), ("EUR", "Infinity"),
    ("EUR", True), ("EUR", 5.5), ("EUR", None), ("EUR", []), ("EUR", {}),
])
def test_invalid_values_are_not_rounded_guessed_or_dropped(currency, amount):
    with pytest.raises(ValidationError):
        response_model(currency).model_validate_json(json.dumps({"personas": [{**PERSON, "budget_min_major": amount, "budget_max_major": "0"}]}), strict=True)

@pytest.mark.parametrize("extra", [
    {"budget_min_major": "5"}, {"budget_max_major": "20"},
    {"budget_min_major": "5", "budget_max_major": "20", "budget_min": 500},
    {"budget_min_major": "5", "budget_max_major": "20", "budget_max": 2000},
    {"budget_min_major": "20", "budget_max_major": "5"},
    {"budget_min_major": "", "budget_max_major": "20"},
    {"budget_min_major": "5", "budget_max_major": ""},
])
def test_incomplete_mixed_or_reversed_pairs_fail(extra):
    with pytest.raises(ValidationError):
        response_model("EUR").model_validate_json(json.dumps({"personas": [{**PERSON, **extra}]}), strict=True)

@pytest.mark.parametrize("currency", ["USD", "EUR", "KRW", "JPY"])
def test_legacy_minor_budgets_are_never_scaled_again(currency):
    model = response_model(currency)
    result = model.model_validate_json(json.dumps({"personas": [{**PERSON, "budget_min": 500, "budget_max": 2000}]}), strict=True)
    assert (result.personas[0].budget_min, result.personas[0].budget_max) == (500, 2000)
    assert model.model_validate_json(result.model_dump_json(), strict=True) == result
    assert model(personas=[PERSON]).personas[0].budget_max == 0

def test_wire_requires_both_major_amounts_and_preserves_other_fields():
    model = response_model("EUR")
    schema = model.model_json_schema()
    assert "preferred_categories" in schema["$defs"]["LabelledPersona"]["required"]
    validator = Draft202012Validator(schema)
    valid = {"personas": [{**PERSON, "budget_min_major": "5.50", "budget_max_major": "20"}]}
    assert validator.is_valid(valid)
    del valid["personas"][0]["budget_max_major"]
    assert not validator.is_valid(valid)
    legacy = {key: value for key, value in PERSON.items() if key != "preferred_categories"}
    assert model(personas=[legacy]).personas[0].preferred_categories == []
