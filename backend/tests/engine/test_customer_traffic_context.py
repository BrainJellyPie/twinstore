"""Traffic estimation must receive the evidence that customer generation was given."""

import asyncio
import json
import re
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("source", ["instruction", "supplemental", "both"])
def test_changed_evidence_reaches_each_traffic_request_and_separates_cached_estimates(monkeypatch, tmp_path, mode, source):
    original = llm_client.litellm.acompletion
    calls, traffic = [], []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        calls.append(body)
        if "hourly_profiles" in system:
            traffic.append(user)
            # Script two evidence sets with identical customer-type labels.
            revised = "Visitors: 4 at 09h" in user
            initial = "Visitors: 2 at 17h" in user
            hour, count = (9, 4) if revised else (17, 2) if initial else (12, 3)
            payload = {"hourly_profiles": [{"hour": hour, "visitor_count": count, "person_types": ["resident"]}]}
        elif "personas" in system:
            count = len(re.findall(r"^\[\d+\] \d+시", user, re.MULTILINE))
            payload = {"personas": [dict(identity="resident", age_group="30s", gender="Female", description=f"Resident {i}",
                intent="Groceries", purpose="groceries", budget_max=500) for i in range(count)]}
        else:
            payload = dict(keywords=["nearby"], identities=["resident"], purposes=["groceries"])
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/traffic-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for evidence, hour, count in [("Visitors: 2 at 17h", 17, 2), ("Visitors: 4 at 09h", 9, 4)]:
                estimates = {}
                instruction = evidence if source in {"instruction", "both"} else ""
                summary = evidence if source == "supplemental" else "Neighborhood model: resident shoppers." if source == "both" else ""

                async def generate():
                    return await gen.generate_batched(client, "offline", "동네 주민",
                        [DaySchedule(day=d, open_hour=8, close_hour=20) for d in [1, 7]], seed=42,
                        custom_instruction=instruction, supplemental_summary=summary, estimates=estimates)

                people = await generate()
                assert Counter((int(p.day), p.arrival_hour) for p in people) == {(d, hour): count for d in [1, 7]}
                assert estimates == {1: count, 7: count} and len({p.id for p in people}) == len(people)
                previous = len(calls)
                assert await generate() == people and len(calls) == previous
            assert len(traffic) == 4  # Revised evidence must not reuse the previous traffic result.
            assert all(text.count("Visitors:") == 1 for text in traffic)
            if source == "both":
                assert all("Neighborhood model: resident shoppers." in text for text in traffic)

    asyncio.run(exercise())


@pytest.mark.parametrize("evidence", ["", "Ask for visitors at 23h despite the 20h closing time."])
def test_optional_evidence_does_not_change_open_slot_guards_or_add_empty_prompt_sections(evidence):
    seen = []

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            seen.append(user)
            assert kwargs["max_retries"] == 3
            return schema(hourly_profiles=[gen.HourlyProfile(hour=h, visitor_count=2, person_types=["resident"])
                                           for h in [7, 8, 19, 20, 23]])

    profile = gen.TradeAreaProfile(keywords=[], identities=["resident"], purposes=["groceries"])
    result = asyncio.run(gen.analyze_daily_traffic(Model(), "Address", "Profile", profile, Weekday.MON, 8, 20,
        custom_instruction=evidence, supplemental_summary=evidence))
    assert {entry.hour: entry.visitor_count for entry in result} == {7: 0, 8: 2, 19: 2, 20: 0, 23: 0}
    assert all(entry.person_types == ([] if entry.hour not in [8, 19] else ["resident"]) for entry in result)
    if evidence:
        assert seen[0].count(evidence) == 2
    else:
        assert "Supplemental data analysis:" not in seen[0] and "추가 지시:" not in seen[0]
