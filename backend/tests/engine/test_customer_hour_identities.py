"""A valid global customer label must still belong to its arrival-hour cohort."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import IncompleteOutputException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_generated_budget_bounds import PERSON


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
@pytest.mark.parametrize("batch_size", [1, 3])
def test_customer_labels_cannot_move_between_observed_hours(monkeypatch, tmp_path, mode, outcome, batch_size):
    original = llm_client.litellm.acompletion
    labels = {9: "student", 13: "retiree", 21: "night shift worker"}
    area = gen.TradeAreaProfile(keywords=[], identities=list(labels.values()), purposes=["groceries"])
    hours = [gen.HourlyProfile(hour=h, visitor_count=1, person_types=[label]) for h, label in labels.items()]
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    attempts = {}
    requests = []

    def respond(request):
        body = json.loads(request.content)
        prompt = next(m["content"] for m in body["messages"] if m["role"] == "user" and "페르소나" in m["content"])
        chunk = [h for h in labels if f"] {h}시," in prompt]
        key = tuple(chunk)
        attempts[key] = attempts.get(key, 0) + 1
        requests.append(body)
        bad = phase == "invalid" and (outcome != "corrected" or attempts[key] == 1)
        customers = [{**PERSON, "identity": labels[13 if h == 9 else 9] if bad else labels[h]} for h in chunk]
        return httpx.Response(200, request=request, json={"id": "offline-hours", "object": "chat.completion",
            "created": 0, "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({"personas": customers})}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-hours", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                return await gen.generate_personas_for_day(client, "offline", area, Weekday.MON, hours,
                    seed=4, batch_size=batch_size, max_concurrent=1)

            if outcome == "legacy_cache":
                assert len(await run()) == 3
                for path in tmp_path.rglob("*.json"):
                    saved = json.loads(path.read_text())
                    for person in saved["result"]["personas"]:
                        person["identity"] = "retiree" if person["identity"] == "student" else "student"
                    path.write_text(json.dumps(saved))
                phase = "invalid"
                attempts.clear()
            if outcome in {"repeated", "legacy_cache"}:
                assert await run() == []
                assert all(count == 3 for count in attempts.values())
                phase = "complete"
            people = await run()
            assert {person.arrival_hour: person.identity for person in people} == labels
            assert len(people) == 3 and not any(person.twin_of for person in people)
            if outcome == "corrected":
                assert all(count == 2 for count in attempts.values())
            before = len(requests)
            assert await run() == people and len(requests) == before

    asyncio.run(exercise())


@pytest.mark.parametrize("returned", [1, 2, 4])
@pytest.mark.parametrize("wrong_row", [None, 0, 1, 3])
def test_hour_validation_preserves_short_and_surplus_provider_handling(returned, wrong_row):
    labels = {9: "Student + 夜間 🛒", 21: "Worker"}

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            rows = [{**PERSON, "identity": "Other" if i == wrong_row else
                f" {list(labels.values())[i % 2].lower()} "} for i in range(returned)]
            return schema.model_validate({"personas": rows})

    area = gen.TradeAreaProfile(keywords=[], identities=[*labels.values(), "Other"], purposes=["groceries"])
    hours = [gen.HourlyProfile(hour=h, visitor_count=1, person_types=[label]) for h, label in labels.items()]
    tally = gen.BatchTally()
    people = asyncio.run(gen.generate_personas_for_day(Model(), "offline", area, Weekday.MON, hours,
        batch_size=2, tally=tally))
    invalid = wrong_row is not None and wrong_row < min(returned, 2)
    assert len(people) == (0 if invalid else min(returned, 2))
    assert tally.failed == int(invalid)
    assert all(person.identity == labels[person.arrival_hour] for person in people)


def test_interleaved_batches_keep_their_own_hour_constraints():
    labels = {9: "Student", 13: "Retiree", 21: "Worker"}

    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            hour = next(h for h in labels if f"] {h}시," in prompt)
            await asyncio.sleep(0)
            return schema.model_validate({"personas": [{**PERSON, "identity": labels[hour]}]})

    area = gen.TradeAreaProfile(keywords=[], identities=list(labels.values()), purposes=["groceries"])
    hours = [gen.HourlyProfile(hour=h, visitor_count=1, person_types=[label]) for h, label in labels.items()]
    people = asyncio.run(gen.generate_personas_for_day(Model(), "offline", area, Weekday.MON, hours,
        batch_size=1, max_concurrent=3))
    assert {person.arrival_hour: person.identity for person in people} == labels


@pytest.mark.parametrize("wrong_child", [False, True])
def test_truncated_batches_revalidate_each_child_against_its_original_hours(wrong_child):
    labels = {9: "Student", 13: "Retiree", 21: "Worker"}
    calls = []

    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            chunk = [h for h in labels if f"] {h}시," in prompt]
            calls.append(chunk)
            if len(chunk) > 1:
                raise IncompleteOutputException()
            identity = "Student" if wrong_child else labels[chunk[0]]
            return schema.model_validate({"personas": [{**PERSON, "identity": identity}]})

    area = gen.TradeAreaProfile(keywords=[], identities=list(labels.values()), purposes=["groceries"])
    hours = [gen.HourlyProfile(hour=h, visitor_count=1, person_types=[label]) for h, label in labels.items()]
    people = asyncio.run(gen.generate_personas_for_day(Model(), "offline", area, Weekday.MON, hours, batch_size=3))
    if wrong_child:
        assert people == []  # A failed child cannot leave an apparently complete partial batch.
    else:
        assert {person.arrival_hour: person.identity for person in people} == labels
    assert calls == ([[9, 13, 21], [9], [13, 21], [13]] + ([] if wrong_child else [[21]]))
