"""Generated customer labels must come from the profile supplied to the model."""

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
@pytest.mark.parametrize("field", ["identity", "purpose"])
@pytest.mark.parametrize("value", ["", " \t\u3000", "not a supplied label"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_unknown_customer_labels_are_corrected_before_persistence(monkeypatch, tmp_path, mode, field, value, outcome):
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-labels", api_base="http://127.0.0.1:8081/v1",
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
            assert people[0].arrival_hour == 9 and not people[0].twin_of
            if outcome == "corrected":
                assert calls.count("customers") == 2
            before = len(calls)
            assert await run() == people and len(calls) == before
            batches = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            assert all(row["personas"][0][field] == GOOD[field] for row in batches if "personas" in row)

    asyncio.run(exercise())


@pytest.mark.parametrize("labels,asked,expected", [
    (["Resident"], " resident ", "Resident"), (["동네 주민"], "\u3000동네 주민\t", "동네 주민"),
    (["Resident", "RESIDENT"], "Resident", "Resident"), (["Resident", "RESIDENT"], "RESIDENT", "RESIDENT"),
    (["Resident", "RESIDENT"], "resident", None), ([], "shopper", "shopper"),
])
def test_only_unambiguous_text_normalization_changes_a_generated_label(labels, asked, expected):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"personas": [{**GOOD, "identity": asked, "purpose": " groceries "}]})

    profile = gen.TradeAreaProfile(keywords=[], identities=labels, purposes=["Groceries"])
    tally = gen.BatchTally()
    result = asyncio.run(gen.generate_personas_for_day(Model(), "offline", profile, Weekday.MON,
        [gen.HourlyProfile(hour=9, visitor_count=1, person_types=labels or ["shopper"])], tally=tally))
    if expected is None:
        assert result == [] and tally.failed == 1
    else:
        assert len(result) == 1 and result[0].identity == expected and result[0].purpose == "Groceries"
