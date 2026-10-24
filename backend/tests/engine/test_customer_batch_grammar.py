"""Customer request grammars must describe the actual number of records to write."""

import asyncio
import json
import re

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_customer_truncated_batches import profile


def person(index):
    return gen.GeneratedPersona(identity="resident", age_group="30s", gender="Female", description=f"Customer {index}",
                                intent="Buy groceries", purpose="groceries")


@pytest.mark.parametrize("count,batch_size", [(1, 5), (2, 5), (5, 5), (6, 5), (11, 5), (10, 10), (12, 12), (13, 12),
                                           (13, 13), (25, 25), (5, 0), (5, -1)])
def test_actual_http_grammar_never_requests_more_customers_than_the_current_chunk(monkeypatch, tmp_path, count, batch_size):
    requests = []
    original_completion = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        prompt = next(message["content"] for message in body["messages"] if message["role"] == "user")
        requested = len(re.findall(r"^\[\d+\] \d+시", prompt, re.MULTILINE))
        schema = body["response_format"]["json_schema"]
        assert schema["name"] == "PersonaBatch"
        maximum = schema["schema"]["properties"]["personas"]["maxItems"]
        minimum = schema["schema"]["properties"]["personas"]["minItems"]
        requests.append((requested, maximum))
        assert minimum == maximum == requested and 1 <= requested <= 12
        content = json.dumps({"personas": [person(i).model_dump() for i in range(maximum)]})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": content}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-customer-count", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))
            hours = [gen.HourlyProfile(hour=9, visitor_count=count, person_types=["resident"])]
            first = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hours,
                                                        batch_size=batch_size, seed=42)
            before = len(requests)
            second = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hours,
                                                         batch_size=batch_size, seed=42)
            assert first == second and len(first) == count and len({p.id for p in first}) == count
            assert len(requests) == before

    asyncio.run(exercise())
    assert requests and all(expected == maximum for expected, maximum in requests)
    assert gen.PersonaBatch.model_json_schema()["properties"]["personas"]["maxItems"] == 12


@pytest.mark.parametrize("batch_size", [2, 5, 13, 25])
def test_grammar_cannot_finish_early_and_substitute_twins_for_full_generation(batch_size):
    requests, plans = [], []

    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if schema is gen.TradeAreaProfile:
                return profile()
            if schema is gen.DailyTrafficResult:
                return schema(hourly_profiles=[gen.HourlyProfile(hour=9, visitor_count=25, person_types=["resident"])])
            bounds = schema.model_json_schema()["properties"]["personas"]
            requested = len(re.findall(r"^\[\d+\] \d+시", prompt, re.MULTILINE))
            requests.append(requested)
            # A grammar permits completion at minItems. It used to permit one,
            # silently turning the rest of a full generation into cloned people.
            return schema(personas=[person(i) for i in range(bounds["minItems"])])

    async def decide(plan):
        plans.append(plan)
        return plan.all.per_day

    people = asyncio.run(gen.generate_batched(Model(), "offline", "Residents",
        [DaySchedule(day=1, open_hour=9, close_hour=10)], batch_size=batch_size, decide=decide))
    assert len(people) == len({p.id for p in people}) == 25
    assert not any(p.twin_of for p in people)
    assert plans[0].all.requests == len(requests)
    assert max(requests) <= 12 and sum(requests) == 25


@pytest.mark.parametrize("returned", [1, 12])
def test_servers_ignoring_the_grammar_keep_existing_short_and_surplus_response_handling(returned):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            assert schema.model_json_schema()["properties"]["personas"]["maxItems"] == 5
            return schema.model_validate({"personas": [person(i).model_dump() for i in range(returned)]})

    people = asyncio.run(gen.generate_personas_for_day(Model(), "offline", profile(), Weekday.MON,
        [gen.HourlyProfile(hour=9, visitor_count=5, person_types=["resident"])], batch_size=5))
    assert len(people) == min(returned, 5)


def test_concurrent_customer_requests_keep_separate_count_limits():
    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            requested = prompt.count("\n[")
            await asyncio.sleep(0)
            assert schema.model_json_schema()["properties"]["personas"]["maxItems"] == requested
            return schema(personas=[person(i) for i in range(requested)])

    async def exercise():
        return await asyncio.gather(*[gen.generate_personas_for_day(Model(), "offline", profile(), day,
            [gen.HourlyProfile(hour=9, visitor_count=count, person_types=["resident"])], batch_size=5)
            for day, count in [(Weekday.MON, 1), (Weekday.SUN, 5)]])

    first, second = asyncio.run(exercise())
    assert len(first) == 1 and len(second) == 5
