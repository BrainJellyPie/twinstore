"""Finite profile fields become ordered label pools through SDK and cache boundaries."""
import asyncio
import json

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen

COUNTS = {"keywords": 8, "identities": 16, "purposes": 16}


def keyed_profile():
    return {field: {str(i): f"{label} {i}" for i in range(1, count + 1)}
            for (field, count), label in zip(COUNTS.items(), ["nearby", "resident", "buy tea"], strict=True)}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("reversed_keys", [False, True])
def test_numbered_profile_survives_http_generation_and_canonical_cache(monkeypatch, tmp_path, mode, reversed_keys):
    original, calls = llm_client.litellm.acompletion, []
    payload = keyed_profile()
    if reversed_keys:
        payload = {field: dict(reversed(list(values.items()))) for field, values in payload.items()}

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "hourly_profiles" in system:
            assert "  - resident 1\n  - resident 2\n" in user
            data = {"hourly_profiles": [{"visitor_count": 1, "person_types": ["resident 1"]}]}
        elif "personas" in system:
            assert "  - buy tea 1\n  - buy tea 2\n" in user
            data = {"personas": [dict(identity="resident 1", purpose="buy tea 1", age_group="30s", gender="Female",
                description="Nearby tea drinker", intent="Buy tea", preferred_categories=["tea"],
                budget_min_major="2.50", budget_max_major="7.75")]}
        else:
            data = payload
            if mode == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                Draft202012Validator(schema).validate(payload)
                for field, count in COUNTS.items():
                    pool = schema["properties"][field]
                    assert pool["type"] == "object" and pool["additionalProperties"] is False
                    assert set(pool["required"]) == {str(i) for i in range(1, count + 1)}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(data)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/keyed-profile", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def generate():
                return await gen.generate_batched(client, "offline", "Tea drinkers; EUR 2.50–7.75 per visit",
                    [DaySchedule(day=1, open_hour=9, close_hour=10)], currency="EUR", seed=4)

            people = await generate()
            assert len(people) == 1 and (people[0].budget_min, people[0].budget_max) == (250, 775)
            assert people[0].identity == "resident 1" and people[0].purpose == "buy tea 1"
            assert await generate() == people and len(calls) == 3
            assert client.get_usage().cached_requests == 3
            cached = [json.loads(p.read_text())["result"] for p in tmp_path.rglob("*.json")]
            profile = next(row for row in cached if "identities" in row)
            assert profile == {field: list(keyed_profile()[field].values()) for field in COUNTS}

    asyncio.run(exercise())


@pytest.mark.parametrize("field", COUNTS)
@pytest.mark.parametrize("defect", ["missing", "extra", "schema", "null", "number", "object", "long"])
def test_numbered_profile_rejects_incomplete_invented_or_nontext_values(field, defect):
    payload = keyed_profile()
    if defect == "missing":
        payload[field].pop("1")
    elif defect == "extra":
        payload[field][str(COUNTS[field] + 1)] = "extra"
    elif defect == "schema":
        payload[field] = {"type": "array", "items": {"default": "resident"}}
    else:
        payload[field]["1"] = {"null": None, "number": 1, "object": {"default": "resident"}, "long": "x" * 121}[defect]
    with pytest.raises(ValidationError):
        gen.TradeAreaProfile.model_validate_json(json.dumps(payload), strict=True)


def test_numbered_and_legacy_labels_keep_the_same_cleanup_and_length_limits():
    payload = keyed_profile()
    for field in payload:
        payload[field]["1"], payload[field]["2"], payload[field]["3"] = "\u3000", " Café regular\t", "Café regular"
    profile = gen.TradeAreaProfile.model_validate(payload)
    assert all(values[0] == "Café regular" and len(values) == COUNTS[field] - 2
               for field, values in profile.model_dump().items())
    assert gen.TradeAreaProfile.model_validate_json(profile.model_dump_json(), strict=True) == profile
    for field, limit in [("keywords", 20), ("identities", 40), ("purposes", 40)]:
        values = [f"label {i}" for i in range(limit)]
        legacy = {"keywords": [], "identities": [], "purposes": [], field: values}
        assert getattr(gen.TradeAreaProfile.model_validate(legacy), field) == values
        with pytest.raises(ValidationError):
            gen.TradeAreaProfile.model_validate({**legacy, field: values + ["one more"]})
