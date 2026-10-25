"""Minor spelling variations must not discard otherwise valid generated customers."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.persona import AGE_GROUPS, GENDERS
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_generated_budget_bounds import PERSON


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("age", AGE_GROUPS)
@pytest.mark.parametrize("gender", GENDERS)
@pytest.mark.parametrize("variant", ["lower", "upper", "padded"])
def test_demographic_variants_generate_one_canonical_customer_without_retries(monkeypatch, tmp_path, mode, age, gender, variant):
    def vary(value):
        return f"\u3000{value.swapcase()}\t" if variant == "padded" else value.upper() if variant == "upper" else value.lower()

    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "hourly_profiles" in system:
            kind, payload = "traffic", {"hourly_profiles": [{"visitor_count": 1, "person_types": ["resident"]}]}
        elif "personas" in system:
            kind, payload = "customers", {"personas": [{**PERSON, "age_group": vary(age), "gender": vary(gender)}]}
        else:
            kind, payload = "profile", dict(keywords=[], identities=["resident"], purposes=["groceries"])
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                return await gen.generate_batched(client, "offline", "동네 주민", [DaySchedule(day=1, open_hour=9, close_hour=10)],
                                                   batch_size=1, seed=42)

            people = await run()
            assert len(people) == 1 and people[0].age_group == age and people[0].gender == gender
            assert people[0].id.startswith("F" if gender == "Female" else "M") and people[0].arrival_hour == 9
            assert not people[0].twin_of and calls == ["profile", "traffic", "customers"]
            cached = []
            for path in tmp_path.rglob("*.json"):
                saved = json.loads(path.read_text())
                if "personas" in saved["result"]:
                    person = saved["result"]["personas"][0]
                    assert person["age_group"] == age and person["gender"] == gender
                    # Older/manual cache values must be validated on reads too.
                    person.update(age_group=vary(age), gender=vary(gender))
                    path.write_text(json.dumps(saved))
                    cached.append(path)
            assert len(cached) == 1 and await run() == people
            assert len(calls) == 3 and client.get_usage().cached_requests == 3

    asyncio.run(exercise())


@pytest.mark.parametrize("field,value", [
    ("age_group", "20"), ("age_group", 20), ("age_group", "65+"), ("age_group", None),
    ("age_group", []), ("age_group", " "), ("gender", "shopper"), ("gender", 1),
    ("gender", None), ("gender", []), ("gender", " "),
])
def test_unknown_or_nonstring_demographics_still_require_correction(field, value):
    with pytest.raises(ValidationError):
        gen.GeneratedPersona.model_validate({**PERSON, field: value})


def test_demographic_schema_keeps_required_canonical_enum_values():
    schema = gen.GeneratedPersona.model_json_schema()
    assert schema["$defs"]["AgeGroup"]["enum"] == AGE_GROUPS
    assert schema["$defs"]["Gender"]["enum"] == GENDERS
    assert {"age_group", "gender"} <= set(schema["required"])
    for age in AGE_GROUPS:
        for gender in GENDERS:
            person = gen.GeneratedPersona.model_validate({**PERSON, "age_group": age, "gender": gender})
            assert person.age_group == age and person.gender == gender
