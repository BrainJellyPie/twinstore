"""Generated customers need usable descriptions and intents before reuse."""

import asyncio
import json

import httpx
import pytest

from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_generated_budget_bounds import PERSON

GOOD = {**PERSON, "identity": "Resident", "purpose": "Groceries"}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["description", "intent"])
@pytest.mark.parametrize("value", ["", "   ", "\t\n\u3000\u2003"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_blank_customer_narratives_are_corrected_before_reuse(monkeypatch, tmp_path, mode, field, value, outcome):
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "hourly_profiles" in system:
            kind, payload = "traffic", {"hourly_profiles": [{"visitor_count": 1, "person_types": ["Resident"]}]}
        elif "personas" in system:
            kind = "customers"
            bad = phase == "invalid" and not (outcome == "corrected" and calls.count("customers") > 0)
            payload = {"personas": [{**GOOD, field: value} if bad else GOOD]}
        else:
            kind, payload = "profile", dict(keywords=[], identities=["Resident"], purposes=["Groceries"])
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-narratives", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                return await gen.generate_batched(client, "offline", "동네 주민", [DaySchedule(day=1, open_hour=9, close_hour=10)],
                                                   batch_size=1, seed=42)

            if outcome == "legacy_cache":
                await run()
                batches = []
                for path in tmp_path.rglob("*.json"):
                    saved = json.loads(path.read_text())
                    if "personas" in saved["result"]:
                        saved["result"]["personas"][0][field] = value
                        path.write_text(json.dumps(saved))
                        batches.append(path)
                assert len(batches) == 1
                phase = "invalid"
            if outcome in {"repeated", "legacy_cache"}:
                before = calls.count("customers")
                with pytest.raises(gen.TooManyBatchesFailed):
                    await run()
                assert calls.count("customers") == before + 3
                phase = "complete"
            people = await run()
            assert len(people) == 1 and people[0].identity == "Resident" and people[0].purpose == "Groceries"
            assert people[0].arrival_hour == 9 and people[0].day == 1 and not people[0].twin_of
            assert people[0].description == GOOD["description"] and people[0].intent == GOOD["intent"]
            assert people[0].preferred_categories == [] and people[0].behavior_tendency == ""
            if outcome == "corrected":
                assert calls.count("customers") == 2
            before = len(calls)
            assert await run() == people and len(calls) == before
            batches = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            assert all(row["personas"][0][field] == GOOD[field] for row in batches if "personas" in row)

    asyncio.run(exercise())


@pytest.mark.parametrize("description,intent", [("Resident.", "Browse."), ("  동네 주민.\t", "\u3000구경만 한다.\n"),
                                               ("A hurried shopper.", "Do not buy anything today.")])
def test_short_negative_and_unicode_customer_narratives_remain_valid(description, intent):
    customer = gen.GeneratedPersona.model_validate({**GOOD, "description": description, "intent": intent,
                                                    "preferred_categories": None, "behavior_tendency": None})
    assert customer.description == description.strip() and customer.intent == intent.strip()
    assert customer.preferred_categories == [] and customer.behavior_tendency == ""


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["description", "intent"])
@pytest.mark.parametrize("position", [0, 2, 4])
@pytest.mark.parametrize("corrected", [False, True])
def test_one_blank_customer_cannot_shift_or_partially_cache_a_five_person_batch(
    monkeypatch, tmp_path, mode, field, position, corrected,
):
    original, requests = llm_client.litellm.acompletion, []
    phase = "invalid"
    people = [{**GOOD, "description": f"Nearby resident {i}", "intent": f"Browse aisle {i}"} for i in range(5)]

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        rows = [dict(person) for person in people]
        if phase == "invalid" and (not corrected or len(requests) == 1):
            rows[position][field] = "\t\u3000"
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"personas": rows})}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-narrative-batch",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            tally = gen.BatchTally()

            async def run():
                return await gen.generate_personas_for_day(client, "offline",
                    gen.TradeAreaProfile(keywords=[], identities=["Resident"], purposes=["Groceries"]), Weekday.SUN,
                    [gen.HourlyProfile(hour=9, visitor_count=2, person_types=["Resident"]),
                     gen.HourlyProfile(hour=23, visitor_count=3, person_types=["Resident"])],
                    batch_size=5, seed=42, tally=tally)

            if not corrected:
                assert await run() == [] and tally.failed == 1
                assert len(requests) == 3 and not list(tmp_path.rglob("*.json"))
                phase = "complete"
            result = await run()
            assert len(requests) == (2 if corrected else 4)
            assert [person.id for person in result] == [f"F7{i:03d}" for i in range(1, 6)]
            assert [person.arrival_hour for person in result] == [9, 9, 23, 23, 23]
            assert all(person.day == 7 and not person.twin_of for person in result)
            assert [(person.description, person.intent) for person in result] == [
                (person["description"], person["intent"]) for person in people]
            before = len(requests)
            assert await run() == result and len(requests) == before
            paths = list(tmp_path.rglob("*.json"))
            assert len(paths) == 1
            cached = json.loads(paths[0].read_text())["result"]["personas"]
            assert len(cached) == 5 and all(row[field].strip() for row in cached)

    asyncio.run(exercise())
