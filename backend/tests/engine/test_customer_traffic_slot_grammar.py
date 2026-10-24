"""Opening-hour slots belong to the harness, not repeated model-written IDs."""

import asyncio
import json
from collections import Counter

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("fault", ["repeated", "empty"])
@pytest.mark.parametrize("window", [(0, 1), (23, 24), (9, 18), (0, 24)])
def test_slot_grammar_prevents_repeated_or_missing_hours_through_population_and_cache(monkeypatch, tmp_path, mode, fault, window):
    original, calls = llm_client.litellm.acompletion, []
    opening, closing = window
    hours = list(range(opening, closing))
    counts = [2 if i == 0 else 1 if i == len(hours) - 1 else 0 for i in range(len(hours))]

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if mode == "json_schema":
            schema = body["response_format"]["json_schema"]["schema"]
        else:
            system = next(m["content"] for m in reversed(body["messages"]) if m["role"] == "system")
            schema = json.JSONDecoder().raw_decode(system[system.index('{'):])[0]
        props = schema["properties"]
        if "identities" in props:
            payload = dict(keywords=[], identities=["resident"], purposes=["groceries"])
        elif "hourly_profiles" in props:
            rows = props["hourly_profiles"]
            row = rows["items"]
            if "$ref" in row:
                row = schema["$defs"][row["$ref"].rsplit("/", 1)[1]]
            if "hour" in row["properties"]:
                # Script a legal old grammar output which failed semantic validation,
                # or an empty estimate that silently invoked the generic-day fallback.
                payload = {"hourly_profiles": [dict(hour=opening, visitor_count=2, person_types=["resident"])] * 2
                           if fault == "repeated" else []}
            else:
                assert rows["minItems"] == rows["maxItems"] == len(hours)
                payload = {"hourly_profiles": [dict(visitor_count=n, person_types=["resident"] if n else []) for n in counts]}
                Draft202012Validator.check_schema(schema)
                validator = Draft202012Validator(schema)
                assert validator.is_valid(payload)
                assert not validator.is_valid({"hourly_profiles": []})
                assert not validator.is_valid({"hourly_profiles": payload["hourly_profiles"] * 2})
        else:
            payload = {"personas": [dict(identity="resident", purpose="groceries", age_group="30s", gender="Female",
                description=f"Customer {i}", intent="Groceries") for i in range(props["personas"]["minItems"])]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/traffic-slots", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            estimates = {}

            async def generate():
                return await gen.generate_batched(client, "offline", "동네 주민", [DaySchedule(day=7,
                    open_hour=opening, close_hour=closing)], seed=42, estimates=estimates)

            people = await generate()
            expected = {h: n for h, n in zip(hours, counts) if n}
            assert Counter(p.arrival_hour for p in people) == expected
            assert estimates == {7: sum(counts)} and len({p.id for p in people}) == len(people)
            assert all(int(p.day) == 7 and not p.twin_of for p in people)
            assert len(calls) == 3
            assert await generate() == people and len(calls) == 3

    asyncio.run(exercise())


@pytest.mark.parametrize("window", [(0, 1), (23, 24), (9, 18), (0, 24)])
def test_ambiguous_positional_counts_are_rejected_and_legacy_rows_keep_their_hours(window):
    opening, closing = window
    schema = gen.traffic_response_model(opening, closing)
    values = [dict(visitor_count=i + 1, person_types=["resident"]) for i in range(closing - opening)]
    original = json.dumps(values)
    assigned = schema.model_validate({"hourly_profiles": values})
    assert [row.hour for row in assigned.hourly_profiles] == list(range(opening, closing))
    assert [row.visitor_count for row in assigned.hourly_profiles] == list(range(1, len(values) + 1))
    assert json.dumps(values) == original
    assert schema.model_validate_json(assigned.model_dump_json()) == assigned
    for rows in [values + [values[0]], values[:-1] if len(values) > 1 else [values[0], values[0]]]:
        with pytest.raises(ValidationError, match="one row for each opening-hour slot"):
            schema.model_validate({"hourly_profiles": rows})
    if len(values) > 1:
        with pytest.raises(ValidationError, match="Do not mix"):
            schema.model_validate({"hourly_profiles": [{**values[0], "hour": opening}, *values[1:]]})
    legacy = [{"hour": 23, "visitor_count": 2, "person_types": ["resident"]},
              {"hour": 0, "visitor_count": 1, "person_types": ["resident"]}]
    assert [row.hour for row in schema.model_validate({"hourly_profiles": legacy}).hourly_profiles] == [23, 0]
    assert schema.model_validate({"hourly_profiles": []}).hourly_profiles == []
    with pytest.raises(ValidationError, match="repeated hours"):
        schema.model_validate({"hourly_profiles": [legacy[0], legacy[0]]})


@pytest.mark.parametrize("window", [(0, 1), (23, 24), (9, 18), (0, 24)])
def test_slot_grammar_keeps_traffic_value_limits_and_has_no_generated_hour(window):
    schema = gen.traffic_response_model(*window).model_json_schema()
    validator = Draft202012Validator(schema)
    rows = [dict(visitor_count=0, person_types=[]) for _ in range(window[1] - window[0])]
    assert validator.is_valid({"hourly_profiles": rows})
    for invalid in [dict(visitor_count=-1, person_types=[]), dict(visitor_count=True, person_types=[]),
                    dict(visitor_count=1.5, person_types=[]), dict(visitor_count=1, person_types=["r"] * 11),
                    dict(visitor_count=1, person_types=["r" * 121]), dict(visitor_count=1, person_types=None),
                    dict(visitor_count=1, person_types=[], hour=window[0])]:
        assert not validator.is_valid({"hourly_profiles": [invalid, *rows[1:]]})


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("fault", ["short", "long", "mixed", "negative", "null", "duplicate_clocks"])
def test_non_enforcing_response_is_repaired_and_cached_clocks_follow_each_window(monkeypatch, tmp_path, mode, fault):
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        rows = [dict(visitor_count=i + 1, person_types=["resident"]) for i in range(3)]
        if len(calls) == 1:
            if fault == "short":
                rows = rows[:-1]
            elif fault == "long":
                rows.append(rows[0].copy())
            elif fault == "mixed":
                rows[0]["hour"] = 9
            elif fault == "negative":
                rows[0]["visitor_count"] = -1
            elif fault == "null":
                rows[0]["visitor_count"] = None
            else:
                rows = [{**row, "hour": 9} for row in rows]
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({"hourly_profiles": rows})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/traffic-slot-repair", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            profile = gen.TradeAreaProfile(keywords=[], identities=["resident"], purposes=["groceries"])
            for start, expected_calls in [(9, 2), (10, 3)]:
                for _ in range(2):
                    result = await gen.analyze_daily_traffic(client, "offline", "동네 주민", profile,
                        gen.Weekday.MON, start, start + 3)
                    assert [(p.hour, p.visitor_count) for p in result] == [(start + i, i + 1) for i in range(3)]
                    assert len(calls) == expected_calls

    asyncio.run(exercise())
