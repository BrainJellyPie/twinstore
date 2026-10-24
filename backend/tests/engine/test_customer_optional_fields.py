"""Absent optional preferences must not discard otherwise usable customer batches."""

import asyncio
import json
import re
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


def person(index):
    return dict(identity="resident", age_group="30s", gender="Female", description=f"Nearby resident {index}",
                intent="Buy groceries", purpose="groceries", budget_min=100 + index, budget_max=500 + index)


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["preferred_categories", "behavior_tendency"])
@pytest.mark.parametrize("position", [0, 2, 4])
def test_optional_null_preserves_every_customer_hours_budgets_and_cached_result(monkeypatch, tmp_path, mode, field, position):
    original_completion = llm_client.litellm.acompletion
    calls, batches = [], []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        calls.append(body)
        if "hourly_profiles" in system:
            payload = {"hourly_profiles": [{"hour": h, "visitor_count": n, "person_types": ["resident"]}
                                            for h, n in [(9, 2), (23, 3)]]}
        elif "personas" in system:
            prompt = next(m["content"] for m in body["messages"] if m["role"] == "user")
            count = len(re.findall(r"^\[\d+\] \d+시", prompt, re.MULTILINE))
            assert count == 5
            people = [{**person(i), "preferred_categories": ["snacks"], "behavior_tendency": "Careful shopper"}
                      for i in range(count)]
            people[position][field] = None
            payload = {"personas": people}
            batches.append(body)
        else:
            payload = dict(keywords=["local"], identities=["resident"], purposes=["groceries"])
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-customer-optional",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))

            async def generate():
                return await gen.generate_batched(client, "offline", "동네 주민",
                    [DaySchedule(day=d, open_hour=0, close_hour=24) for d in [1, 7]], batch_size=5, seed=42)

            people = await generate()
            assert len(people) == len({p.id for p in people}) == 10 and not any(p.twin_of for p in people)
            assert Counter((int(p.day), p.arrival_hour) for p in people) == {(d, h): n for d in [1, 7] for h, n in [(9, 2), (23, 3)]}
            for i, p in enumerate(people):
                index = i % 5
                assert (p.description, p.budget_min, p.budget_max) == (f"Nearby resident {index}", 100 + index, 500 + index)
                assert p.preferred_categories == ([] if field == "preferred_categories" and index == position else ["snacks"])
                assert p.behavior_tendency == ("" if field == "behavior_tendency" and index == position else "Careful shopper")
            previous = len(calls)
            assert await generate() == people and len(calls) == previous
            assert len(batches) == 2  # No repeated corrections for absent optional data.

    asyncio.run(exercise())


@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_null_optional_preferences_share_existing_defaults(missing):
    data = person(0) if missing else {**person(0), "preferred_categories": None, "behavior_tendency": None}
    result = gen.GeneratedPersona.model_validate_json(json.dumps(data), strict=True)
    assert result.preferred_categories == [] and result.behavior_tendency == ""


@pytest.mark.parametrize("field,value", [
    ("preferred_categories", "snacks"), ("preferred_categories", [None]), ("preferred_categories", [1]),
    ("preferred_categories", ["snacks"] * 11), ("preferred_categories", ["s" * 81]),
    ("behavior_tendency", []), ("behavior_tendency", {}), ("behavior_tendency", 1), ("behavior_tendency", "s" * 301),
    *[(field, None) for field in ["identity", "age_group", "gender", "description", "intent", "purpose", "budget_min", "budget_max"]],
])
def test_required_fields_types_and_bounds_remain_strict(field, value):
    with pytest.raises(ValidationError):
        gen.GeneratedPersona.model_validate_json(json.dumps({**person(0), field: value}), strict=True)


@pytest.mark.parametrize("value", [None, [], [None]])
def test_missing_customer_records_are_not_converted_to_empty_people(value):
    with pytest.raises(ValidationError):
        gen.PersonaBatch.model_validate_json(json.dumps({"personas": value}), strict=True)
