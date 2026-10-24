"""Contradictory generated budgets must be corrected before customer persistence."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_generated_budget_bounds import MAX_BUDGET, PERSON


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("minimum,maximum", [(2, 1), (500, 100), (MAX_BUDGET, 1000)])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_inverted_positive_budgets_do_not_become_cached_customers(monkeypatch, tmp_path, mode, minimum, maximum, outcome):
    original, calls = llm_client.litellm.acompletion, []
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    bad = {**PERSON, "budget_min": minimum, "budget_max": maximum}

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "hourly_profiles" in system:
            kind, payload = "traffic", {"hourly_profiles": [{"visitor_count": 1, "person_types": ["resident"]}]}
        elif "personas" in system:
            kind = "customers"
            invalid = phase == "invalid" and not (outcome == "corrected" and calls.count("customers") > 0)
            payload = {"personas": [bad if invalid else PERSON]}
        else:
            kind, payload = "profile", dict(keywords=[], identities=["resident"], purposes=["groceries"])
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/budget-order", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def generate():
                return await gen.generate_batched(client, "offline", "동네 주민",
                    [DaySchedule(day=1, open_hour=9, close_hour=10)], batch_size=1, seed=42)

            if outcome == "legacy_cache":
                await generate()
                matches = []
                for path in tmp_path.rglob("*.json"):
                    saved = json.loads(path.read_text())
                    if "personas" in saved["result"]:
                        saved["result"]["personas"][0].update(budget_min=minimum, budget_max=maximum)
                        path.write_text(json.dumps(saved))
                        matches.append(path)
                assert len(matches) == 1
                phase = "invalid"
            if outcome in {"repeated", "legacy_cache"}:
                before = calls.count("customers")
                with pytest.raises(gen.TooManyBatchesFailed):
                    await generate()
                assert calls.count("customers") == before + 3
                phase = "complete"
            people = await generate()
            assert len(people) == 1 and (people[0].budget_min, people[0].budget_max) == (500, 1000)
            assert people[0].arrival_hour == 9 and not people[0].twin_of
            if outcome == "corrected":
                assert calls.count("customers") == 2
            before = len(calls)
            assert await generate() == people and len(calls) == before
            saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            batches = [entry for entry in saved if "personas" in entry]
            assert len(batches) == 1 and batches[0]["personas"][0]["budget_min"] <= batches[0]["personas"][0]["budget_max"]

    asyncio.run(exercise())


@pytest.mark.parametrize("minimum,maximum", [(0, 0), (500, 0), (MAX_BUDGET, 0), (0, 1), (1, 1), (MAX_BUDGET, MAX_BUDGET)])
def test_equal_ranges_and_unspecified_upper_limits_remain_valid(minimum, maximum):
    person = gen.GeneratedPersona.model_validate({**PERSON, "budget_min": minimum, "budget_max": maximum})
    assert (person.budget_min, person.budget_max) == (minimum, maximum)


def test_reversed_range_is_invalid_even_within_numeric_field_bounds():
    with pytest.raises(ValidationError):
        gen.GeneratedPersona.model_validate({**PERSON, "budget_min": 1001, "budget_max": 1000})
