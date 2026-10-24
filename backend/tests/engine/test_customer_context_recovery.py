"""Input-context rejection can split one customer batch, without retrying unrelated errors."""

import asyncio
import json
import re

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException
from litellm.exceptions import BadRequestError, ContextWindowExceededError
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_customer_truncated_batches import LimitedModel, hourly, profile, wrapped


MESSAGES = [
    "request (9000 tokens) exceeds the available context size (8192 tokens), try increasing it",
    "input (9000 tokens) is larger than the max context size (8192 tokens). skipping",
    "This model's maximum context length is 8192 tokens. However, your request has 9000 input tokens.",
]


def overflow(kind):
    cls = ContextWindowExceededError if kind == 2 else BadRequestError
    return cls(MESSAGES[kind], model="openai/local", llm_provider="openai")


class ContextModel(LimitedModel):
    def __init__(self, maximum, kind, wrap):
        super().__init__(maximum)
        self.kind, self.enclose = kind, wrap

    async def generate_structured_async(self, *args, **kwargs):
        try:
            return await super().generate_structured_async(*args, **kwargs)
        except IncompleteOutputException:
            error = overflow(self.kind)
            raise wrapped(error) if self.enclose else error


@pytest.mark.parametrize("count", [2, 3, 5, 12])
@pytest.mark.parametrize("kind", range(3))
@pytest.mark.parametrize("wrap", [False, True])
def test_input_overflow_splits_once_preserving_customer_times_ids_and_progress(count, kind, wrap):
    model = ContextModel((count + 1) // 2, kind, wrap)
    tally, progress = gen.BatchTally(), []
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(count),
        batch_size=count, max_concurrent=1, seed=42, tally=tally, on_written=progress.append))
    assert [p.arrival_hour for p in people] == list(range(9, 9 + count))
    assert [p.id for p in people] == [f"F1{i:03d}" for i in range(1, count + 1)]
    assert all(p.description == f"Arrived at {p.arrival_hour}" and not p.twin_of for p in people)
    assert [len(hours) for hours, _ in model.calls] == [count, count // 2, count - count // 2]
    assert tally.requested == 1 and tally.failed == 0 and progress == [count]
    assert model.peak == 1


@pytest.mark.parametrize("count,maximum", [(1, 0), (5, 0), (5, 2)])
def test_a_shared_oversized_prefix_or_child_overflow_does_not_keep_splitting(count, maximum):
    model = ContextModel(maximum, 2, True)
    tally = gen.BatchTally()
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(count),
        batch_size=count, max_concurrent=1, tally=tally))
    assert people == [] and tally.requested == tally.failed == 1
    assert [len(hours) for hours, _ in model.calls] == ([1] if count == 1 else [5, 2] if maximum == 0 else [5, 2, 3])


@pytest.mark.parametrize("error", [
    ValueError(MESSAGES[0]),
    BadRequestError("Unsupported context parameter", model="openai/local", llm_provider="openai"),
    TimeoutError(MESSAGES[1]),
    InstructorRetryException("context exceeded", n_attempts=2, total_usage=0,
        failed_attempts=[FailedAttempt(1, overflow(2)), FailedAttempt(2, TimeoutError("offline"))]),
])
def test_only_the_last_typed_context_rejection_can_split_a_request(error):
    model = LimitedModel(3, failure=error)
    people = asyncio.run(gen.generate_personas_for_day(model, "offline", profile(), Weekday.MON, hourly(5), batch_size=5))
    assert people == [] and len(model.calls) == 1


@pytest.mark.parametrize("limit", [1, 2])
def test_context_recovery_across_days_keeps_the_shared_request_limit(limit):
    model = ContextModel(3, 2, True)

    async def exercise():
        return await asyncio.wait_for(gen.generate_batched(model, "offline", "동네 주민",
            [DaySchedule(day=day, open_hour=9, close_hour=10) for day in [1, 7]],
            batch_size=5, max_concurrent=limit, seed=42), timeout=2)

    people = asyncio.run(exercise())
    assert len(people) == len({p.id for p in people}) == 10
    assert model.peak <= limit and len(model.calls) == 6


@pytest.mark.parametrize("message", MESSAGES)
@pytest.mark.parametrize("status", [400, 403, 429])
def test_actual_http_context_recovery_respects_original_status_and_caches_only_children(monkeypatch, tmp_path, message, status):
    calls = []
    original_completion = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        prompt = next(m["content"] for m in body["messages"] if m["role"] == "user" and "페르소나" in m["content"])
        hours = [int(h) for h in re.findall(r"^\[\d+\] (\d+)시", prompt, re.MULTILINE)]
        calls.append(len(hours))
        if len(hours) > 3:
            return httpx.Response(status, request=request, json={"error": {"message": message, "type": "exceed_context_size_error"}})
        answer = {"personas": [gen.GeneratedPersona(identity="resident", age_group="30s", gender="Female",
            description=f"Arrived at {hour}", intent="Buy groceries", purpose="groceries").model_dump() for hour in hours]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-customer-context", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))
            people = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hourly(5), batch_size=5, seed=42)
            if status == 400:
                assert [p.arrival_hour for p in people] == list(range(9, 14))
                again = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hourly(5), batch_size=5, seed=42)
                assert again == people and client.get_usage().cached_requests == 2
            else:
                assert people == []

    asyncio.run(exercise())
    if status == 400:
        assert calls == [5, 5, 5, 2, 3, 5, 5, 5]
        entries = [json.loads(p.read_text())["result"] for p in tmp_path.glob("*/*.json")]
        assert sorted(len(entry["personas"]) for entry in entries) == [2, 3]
    else:
        assert calls == [5, 5, 5] and not list(tmp_path.glob("*/*.json"))
