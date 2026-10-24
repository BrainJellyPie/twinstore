"""An empty hour's absent customer types cannot invalidate a whole day's traffic."""

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


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("explicit_hours", [False, True])
@pytest.mark.parametrize("opening,counts", [(0, [0, 2, 1]), (9, [2, 0, 1]), (21, [2, 1, 0])])
def test_zero_hour_null_types_preserve_population_hours_and_cache(monkeypatch, tmp_path, mode, explicit_hours, opening, counts):
    original, calls = llm_client.litellm.acompletion, []
    hours = list(range(opening, opening + len(counts)))

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "hourly_profiles" in system:
            payload = {"hourly_profiles": [dict(visitor_count=n, person_types=["resident"] if n else None,
                **({"hour": h} if explicit_hours else {})) for h, n in zip(hours, counts, strict=True)]}
        elif "personas" in system:
            requested = re.findall(r"^\[\d+\] (\d+)시", user, re.MULTILINE)
            payload = {"personas": [dict(identity="resident", purpose="groceries", age_group="30s", gender="Female",
                description=f"Arrived at {h}", intent="Groceries") for h in requested]}
        else:
            payload = dict(keywords=[], identities=["resident"], purposes=["groceries"])
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/zero-traffic-types", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            estimates = {}

            async def generate():
                return await gen.generate_batched(client, "offline", "동네 주민", [DaySchedule(day=d,
                    open_hour=opening, close_hour=opening + len(counts)) for d in [1, 7]], seed=42, estimates=estimates)

            people = await generate()
            assert estimates == {1: 3, 7: 3}
            assert Counter((int(p.day), p.arrival_hour) for p in people) == {
                (d, h): n for d in [1, 7] for h, n in zip(hours, counts, strict=True) if n}
            assert all(p.description == f"Arrived at {p.arrival_hour}" and not p.twin_of for p in people)
            assert len({p.id for p in people}) == 6
            assert await generate() == people and len(calls) == 5 and client.get_usage().cached_requests == 5
            saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            for value in saved:
                if "hourly_profiles" in value:
                    empty = [row for row in value["hourly_profiles"] if row["visitor_count"] == 0]
                    assert len(empty) == 1 and empty[0]["person_types"] == []

    asyncio.run(exercise())


@pytest.mark.parametrize("count,types", [
    (1, None), (-1, None), (True, None), (False, None), (None, None), ("0", None),
    (0, "resident"), (0, [None]), (0, [123]), (0, {}),
])
def test_null_normalization_does_not_hide_invalid_counts_or_nonempty_hour_types(count, types):
    with pytest.raises(ValidationError):
        gen.HourlyProfile.model_validate(dict(hour=9, visitor_count=count, person_types=types))
