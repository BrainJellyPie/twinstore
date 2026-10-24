"""Model-generated budgets must remain usable by browser and simulation consumers."""

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
from store_emulator.engine.prompting import display_price


PERSON = dict(identity="resident", age_group="30s", gender="Female", description="Nearby resident",
              intent="Buy groceries", purpose="groceries", budget_min=500, budget_max=1000)
MAX_BUDGET = 9_007_199_254_740_991


@pytest.mark.parametrize("field", ["budget_min", "budget_max"])
@pytest.mark.parametrize("value", [MAX_BUDGET + 1, 10**400, str(10**400)], ids=["unsafe-integer", "overflow", "numeric-string"])
@pytest.mark.parametrize("recovers", [False, True])
def test_out_of_range_budget_is_corrected_before_customer_cache(tmp_path, monkeypatch, field, value, recovers):
    requests = []
    customer_requests = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            name = body["response_format"]["json_schema"]["name"]
            if name == "TradeAreaProfile":
                payload = dict(keywords=["local"], identities=["resident"], purposes=["groceries"])
            elif name == "DailyTrafficResult":
                payload = {"hourly_profiles": [{"hour": 9, "visitor_count": 1, "person_types": ["resident"]}]}
            else:
                assert name == "PersonaBatch"
                customer_requests.append(body)
                person = dict(PERSON)
                if not recovers or len(customer_requests) == 1:
                    person[field] = value
                payload = {"personas": [person]}
            return httpx.Response(200, request=request, json={
                "id": "offline-budget", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-budget-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=42))

            async def generate():
                return await gen.generate_batched(client, "offline", "local residents",
                    [DaySchedule(day=1, open_hour=9, close_hour=10)], batch_size=1, seed=42)

            if recovers:
                people = await generate()
                assert len(people) == 1 and people[0].budget_min == 500 and people[0].budget_max == 1000
                assert display_price(people[0].budget_max, "USD") == "$10.00"
                previous_calls = len(requests)
                assert await generate() == people
                assert len(requests) == previous_calls
            else:
                with pytest.raises(gen.TooManyBatchesFailed):
                    await generate()
            cached = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            batches = [data for data in cached if "personas" in data]
            assert batches == ([{"personas": [gen.GeneratedPersona(**PERSON).model_dump()]}] if recovers else [])

    asyncio.run(exercise())
    assert len(customer_requests) == (2 if recovers else 3)


@pytest.mark.parametrize("field", ["budget_min", "budget_max"])
@pytest.mark.parametrize("value", [0, 1, MAX_BUDGET, MAX_BUDGET + 1])
def test_generated_budget_boundaries(field, value):
    data = {**PERSON, field: value}
    if value > MAX_BUDGET:
        with pytest.raises(ValidationError):
            gen.GeneratedPersona.model_validate(data)
    else:
        assert getattr(gen.GeneratedPersona.model_validate(data), field) == value
