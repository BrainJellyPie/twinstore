"""Truncated customer batches shrink to a usable size without shifting visit times."""

import asyncio
import re
from collections import Counter

import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException

from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine.generators import persona as gen


def wrapped(error):
    return InstructorRetryException("retries exhausted", n_attempts=3, total_usage=0,
                                    failed_attempts=[FailedAttempt(3, error)])


class LimitedModel:
    def __init__(self, maximum, *, wrap=False, short=False, failure=None):
        self.maximum, self.wrap, self.short, self.failure = maximum, wrap, short, failure
        self.calls = []
        self.active = self.peak = 0

    async def generate_structured_async(self, schema, system, prompt, **kwargs):
        assert kwargs["max_retries"] == 3
        if schema is gen.TradeAreaProfile:
            return schema(keywords=["nearby"], identities=["resident"], purposes=["groceries"])
        if issubclass(schema, gen.DailyTrafficResult):
            return schema(hourly_profiles=[gen.HourlyProfile(hour=9, visitor_count=5, person_types=["resident"])])
        hours = [int(h) for h in re.findall(r"^\[\d+\] (\d+)시", prompt, re.MULTILINE)]
        self.calls.append((hours, prompt))
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0)
            if len(hours) > self.maximum or self.failure is not None:
                error = self.failure or IncompleteOutputException()
                raise wrapped(error) if self.wrap else error
            if self.short and len(hours) > 1:
                hours = hours[:1]
            return schema(personas=[gen.GeneratedPersona(identity="resident", age_group="30s", gender="Female",
                description=f"Arrived at {hour}", intent="Buy groceries", purpose="groceries").model_dump() for hour in hours])
        finally:
            self.active -= 1


def profile():
    return gen.TradeAreaProfile(keywords=["nearby"], identities=["resident"], purposes=["groceries"])


def hourly(count):
    return [gen.HourlyProfile(hour=9 + i, visitor_count=1, person_types=["resident"]) for i in range(count)]


@pytest.mark.parametrize("count", [2, 3, 5, 10, 12])
@pytest.mark.parametrize("wrap", [False, True])
def test_truncated_batch_recovers_in_two_smaller_requests_preserving_ids_hours_and_progress(count, wrap):
    model = LimitedModel((count + 1) // 2, wrap=wrap)
    tally, progress = gen.BatchTally(), []
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(count),
        seed=42, custom_instruction="Keep local shoppers", batch_size=count, max_concurrent=1,
        categories=["groceries"], currency="KRW", tally=tally, on_written=progress.append))
    assert [p.arrival_hour for p in people] == list(range(9, 9 + count))
    assert [p.id for p in people] == [f"F1{i:03d}" for i in range(1, count + 1)]
    assert all(p.description == f"Arrived at {p.arrival_hour}" and not p.twin_of for p in people)
    assert [len(hours) for hours, _ in model.calls] == [count, count // 2, count - count // 2]
    assert all("Keep local shoppers" in prompt and "groceries" in prompt for _, prompt in model.calls)
    assert tally.requested == 1 and tally.failed == 0 and tally.first_error is None
    assert progress == [count] and model.peak == 1


def test_short_nonempty_recovered_batches_keep_their_original_visit_hours():
    model = LimitedModel(3, short=True)
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.SUN, hourly(5), batch_size=5))
    assert [p.arrival_hour for p in people] == [9, 11]
    assert [p.description for p in people] == ["Arrived at 9", "Arrived at 11"]
    assert [p.id for p in people] == ["F7001", "F7002"]


@pytest.mark.parametrize("count,maximum", [(1, 0), (5, 0)])
def test_repeated_truncation_is_bounded_and_does_not_return_partial_customers(count, maximum):
    model = LimitedModel(maximum, wrap=True)
    tally, progress = gen.BatchTally(), []
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(count),
        batch_size=count, max_concurrent=1, tally=tally, on_written=progress.append))
    assert people == [] and tally.requested == tally.failed == 1
    assert progress == [count]
    assert [len(hours) for hours, _ in model.calls] == ([1] if count == 1 else [5, 2, 1])


@pytest.mark.parametrize("count,maximum", [(3, 1), (5, 2), (12, 2), (12, 1)])
@pytest.mark.parametrize("wrap", [False, True])
def test_repeated_output_truncation_recovers_all_customers_in_bounded_smaller_tasks(count, maximum, wrap):
    model = LimitedModel(maximum, wrap=wrap)
    tally, progress = gen.BatchTally(), []
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(count),
        batch_size=count, max_concurrent=1, seed=42, tally=tally, on_written=progress.append))
    assert [p.arrival_hour for p in people] == list(range(9, 9 + count))
    assert [p.id for p in people] == [f"F1{i:03d}" for i in range(1, count + 1)]
    assert all(p.description == f"Arrived at {p.arrival_hour}" and not p.twin_of for p in people)
    assert len(model.calls) <= 2 * count - 1 and model.peak == 1
    assert tally.requested == 1 and tally.failed == 0 and progress == [count]


def test_unrecoverable_single_customer_keeps_the_original_batch_atomic():
    class LastCustomerFails(LimitedModel):
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            self.failure = IncompleteOutputException() if "13시" in prompt else None
            return await super().generate_structured_async(schema, system, prompt, **kwargs)

    model = LastCustomerFails(2, wrap=True)
    tally, progress = gen.BatchTally(), []
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(5),
        batch_size=5, max_concurrent=1, tally=tally, on_written=progress.append))
    assert people == [] and tally.requested == tally.failed == 1 and progress == [5]
    assert len(model.calls) <= 9 and model.calls[-1][0] == [13]


@pytest.mark.parametrize("error", [TimeoutError("offline"), ValueError("max_tokens length limit in user data")])
@pytest.mark.parametrize("wrap", [False, True])
def test_unrelated_failures_do_not_decompose_customer_requests(error, wrap):
    model = LimitedModel(3, failure=error, wrap=wrap)
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(5), batch_size=5))
    assert people == [] and len(model.calls) == 1


@pytest.mark.parametrize("maximum", [1, 2, 3])
def test_recovered_probe_can_proceed_to_the_existing_write_choice_and_full_population(maximum):
    model, plans = LimitedModel(maximum, wrap=True), []

    async def decide(plan):
        plans.append(plan)
        return 5

    people = asyncio.run(gen.generate_batched(model, "offline", "동네 주민",
        [DaySchedule(day=day, open_hour=9, close_hour=10) for day in [1, 7]],
        batch_size=5, max_concurrent=1, decide=decide, seed=42))
    assert len(plans) == 1 and plans[0].probe_customers == 5
    assert Counter(int(p.day) for p in people) == {1: 5, 7: 5}
    assert len({p.id for p in people}) == 10 and not any(p.twin_of for p in people)
    assert model.peak == 1


@pytest.mark.parametrize("limit", [1, 2])
def test_recovery_across_days_uses_the_shared_concurrency_limit_without_deadlock(limit):
    model = LimitedModel(3, wrap=True)
    async def exercise():
        return await asyncio.wait_for(gen.generate_batched(model, "offline", "동네 주민",
            [DaySchedule(day=day, open_hour=9, close_hour=10) for day in [1, 7]],
            batch_size=5, max_concurrent=limit, seed=42), timeout=2)
    people = asyncio.run(exercise())
    assert Counter(int(p.day) for p in people) == {1: 5, 7: 5}
    assert len(model.calls) == 6 and model.peak <= limit
    assert len({p.id for p in people}) == 10


@pytest.mark.parametrize("earlier_cutoff", [False, True])
def test_an_instructor_wrapper_requires_the_last_failure_to_be_truncation(earlier_cutoff):
    attempts = ([FailedAttempt(1, IncompleteOutputException()), FailedAttempt(2, TimeoutError("offline"))]
                if earlier_cutoff else [])
    error = InstructorRetryException("max_tokens length limit", n_attempts=2, total_usage=0, failed_attempts=attempts)
    model = LimitedModel(3, failure=error)
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(5), batch_size=5))
    assert people == [] and len(model.calls) == 1


def test_real_http_length_finish_reason_recovers_and_caches_only_complete_children(monkeypatch, tmp_path):
    import json

    import httpx
    from openai import AsyncOpenAI

    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine import llm_client

    calls = []
    original_completion = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        prompt = next(message["content"] for message in body["messages"]
                      if message["role"] == "user" and "페르소나" in message["content"])
        hours = [int(h) for h in re.findall(r"^\[\d+\] (\d+)시", prompt, re.MULTILINE)]
        calls.append(len(hours))
        truncated = len(hours) > 3
        content = ('{"personas":[' if truncated else json.dumps({"personas": [
            gen.GeneratedPersona(identity="resident", age_group="30s", gender="Female",
                description=f"Arrived at {hour}", intent="Buy groceries", purpose="groceries").model_dump()
            for hour in hours]}))
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if truncated else "stop",
                "message": {"role": "assistant", "content": content}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-customers", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))
            first = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hourly(5), batch_size=5, seed=42)
            second = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hourly(5), batch_size=5, seed=42)
            assert first == second and [p.arrival_hour for p in first] == [9, 10, 11, 12, 13]
            assert [p.description for p in first] == [f"Arrived at {h}" for h in range(9, 14)]
            assert client.get_usage().cached_requests == 2
            assert client.get_usage().requests == 10  # Eight HTTP completions and two cached children.
            assert client.get_usage().total_tokens == 120  # Include the six truncated responses.

    asyncio.run(exercise())
    assert calls == [5, 5, 5, 2, 3, 5, 5, 5]
    entries = [json.loads(path.read_text())["result"] for path in tmp_path.glob("*/*.json")]
    assert sorted(len(entry["personas"]) for entry in entries) == [2, 3]
