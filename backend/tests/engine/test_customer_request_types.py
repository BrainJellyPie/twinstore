"""An individual request's type cannot drift to another type from the same hour."""

import asyncio
import json
import re

import httpx
import pytest
from instructor.core.exceptions import IncompleteOutputException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_generated_budget_bounds import PERSON


def requested_rows(prompt, labels):
    start = int(re.search(r"daily customer positions=(\d+)-", prompt)[1])
    lines = re.findall(r"^\[\d+\].*", prompt, re.MULTILINE)
    return [(start + i, [label for label in labels if label in line]) for i, line in enumerate(lines)]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
@pytest.mark.parametrize("batch_size", [1, 3])
@pytest.mark.parametrize("offset", [0, 37])
@pytest.mark.parametrize("labels", [["Student", "Retiree", "Worker"], ["学生 + 夜間, 🛒", "Retired reader", "Night nurse"]])
def test_same_hour_requests_reask_before_cache_and_preserve_exact_labels(monkeypatch, tmp_path, mode, outcome, batch_size, offset, labels):
    original = llm_client.litellm.acompletion
    area = gen.TradeAreaProfile(keywords=[], identities=labels, purposes=["groceries"])
    hours = [gen.HourlyProfile(hour=23, visitor_count=3, person_types=labels)]
    source = area.model_dump_json(), hours[0].model_dump_json()
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    attempts, allowed_by_position, calls = {}, {}, []

    def respond(request):
        body = json.loads(request.content)
        prompt = next(m["content"] for m in body["messages"] if m["role"] == "user" and "페르소나" in m["content"])
        rows = requested_rows(prompt, labels)
        key = tuple(position for position, _ in rows)
        attempts[key] = attempts.get(key, 0) + 1
        calls.append(body)
        bad = phase == "invalid" and (outcome != "corrected" or attempts[key] == 1)
        people = []
        for position, allowed in rows:
            assert 1 <= len(allowed) <= 2
            allowed_by_position[position] = allowed
            identity = next(label for label in labels if label not in allowed) if bad else allowed[0]
            people.append({**PERSON, "identity": f" {identity.swapcase()} ", "description": f"Customer position {position}"})
        return httpx.Response(200, request=request, json={"id": "offline-request-types", "object": "chat.completion",
            "created": 0, "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({"personas": people})}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/request-types", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                return await gen.generate_personas_for_day(client, "offline", area, Weekday.MON, hours,
                    seed=4, batch_size=batch_size, max_concurrent=3, sample_offset=offset)

            if outcome == "legacy_cache":
                assert len(await run()) == 3
                for path in tmp_path.rglob("*.json"):
                    saved = json.loads(path.read_text())
                    for person in saved["result"]["personas"]:
                        position = int(person["description"].rsplit(" ", 1)[1])
                        person["identity"] = next(label for label in labels if label not in allowed_by_position[position])
                    path.write_text(json.dumps(saved))
                phase = "invalid"
                attempts.clear()
            if outcome in {"repeated", "legacy_cache"}:
                assert await run() == []
                assert all(n == 3 for n in attempts.values())
                phase = "complete"
            people = await run()
            assert len(people) == len({person.id for person in people}) == 3
            assert all(person.identity in allowed_by_position[int(person.description.rsplit(" ", 1)[1])] for person in people)
            assert all(person.arrival_hour == 23 and person.day == Weekday.MON and not person.twin_of for person in people)
            if outcome == "corrected":
                assert all(n == 2 for n in attempts.values())
            before = len(calls)
            assert await run() == people and len(calls) == before
            assert source == (area.model_dump_json(), hours[0].model_dump_json())

    asyncio.run(exercise())


@pytest.mark.parametrize("invalid_child", [False, True])
@pytest.mark.parametrize("offset", [0, 91])
def test_recursive_split_preserves_each_original_request_type(invalid_child, offset):
    labels = ["Student", "Retiree", "Worker"]
    original_rows = {}

    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            rows = requested_rows(prompt, labels)
            if not original_rows:
                original_rows.update(rows)
            assert all(original_rows[position] == allowed for position, allowed in rows)
            if len(rows) > 1:
                raise IncompleteOutputException()
            position, allowed = rows[0]
            identity = next(label for label in labels if label not in allowed) if invalid_child else allowed[-1]
            return schema.model_validate({"personas": [{**PERSON, "identity": identity,
                "description": f"Customer position {position}"}]})

    area = gen.TradeAreaProfile(keywords=[], identities=labels, purposes=["groceries"])
    hours = [gen.HourlyProfile(hour=23, visitor_count=3, person_types=labels)]
    people = asyncio.run(gen.generate_personas_for_day(Model(), "offline", area, Weekday.MON, hours,
        seed=4, batch_size=3, sample_offset=offset))
    if invalid_child:
        assert people == []
    else:
        assert len(people) == 3
        assert all(person.identity in original_rows[int(person.description.rsplit(" ", 1)[1])] for person in people)


def test_correction_lists_the_complete_returned_row_order():
    labels = ["Student", "Retiree", "Worker"]
    requested = []

    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            requested.extend(requested_rows(prompt, labels))
            people = [{**PERSON, "identity": next(label for label in labels if label not in allowed)
                       if i == 0 else allowed[0]} for i, (_, allowed) in enumerate(requested)]
            return schema.model_validate({"personas": people})

    area = gen.TradeAreaProfile(keywords=[], identities=labels, purposes=["groceries"])
    hours = [gen.HourlyProfile(hour=23, visitor_count=3, person_types=labels)]
    tally = gen.BatchTally()
    assert asyncio.run(gen.generate_personas_for_day(Model(), "offline", area, Weekday.MON, hours,
        seed=4, batch_size=3, tally=tally)) == []
    message = str(tally.first_error)
    assert "request rows [0]" in message
    for index, (_, allowed) in enumerate(requested):
        assert f"row {index} (23:00): {allowed}" in message
