"""Local persona grammars keep the shared customer-type and purpose vocabulary."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("labels", [
    (["resident", "worker", "resident"], ["groceries", "snack", "snack"]),
    (["동네 주민", "近隣の住民", "résident"], ["장보기", "買い物", "café"]),
    (['Resident "A"', 'Visitor \\ local'], ['Shop\nnearby', 'Buy "tea"']),
    (["r" * 120], ["p" * 120]),
    ([], []),
])
def test_generated_population_uses_actual_labels_and_keeps_cache_separate(monkeypatch, tmp_path, mode, labels):
    original, requests = llm_client.litellm.acompletion, []
    identities, purposes = labels

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if mode == "json_schema":
            schema = body["response_format"]["json_schema"]["schema"]
        else:
            system = next(m["content"] for m in reversed(body["messages"]) if m["role"] == "system")
            schema = json.JSONDecoder().raw_decode(system[system.index('{'):])[0]
        fields = schema["properties"]
        if "identities" in fields:
            payload = dict(keywords=[], identities=identities, purposes=purposes)
        elif "hourly_profiles" in fields:
            payload = {"hourly_profiles": [dict(hour=9, visitor_count=4, person_types=identities[:1] or ["shopper"])]}
        else:
            person_schema = fields["personas"]["items"]
            if "$ref" in person_schema:
                person_schema = schema["$defs"][person_schema["$ref"].rsplit("/", 1)[1]]
            props = person_schema["properties"]
            for field in ["identity", "purpose"]:
                bounds = props[field]
                assert "$ref" not in bounds and bounds["type"] == "string" and bounds["maxLength"] == 120
            ids = props["identity"].get("enum", ["Invented customer type"])
            goals = props["purpose"].get("enum", ["Invented purpose"])
            payload = {"personas": [dict(identity=ids[i % len(ids)], purpose=goals[i % len(goals)],
                age_group="30s", gender="Female", description=f"Customer {i}", intent="Shop nearby")
                for i in range(fields["personas"]["minItems"])]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal identities, purposes
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-labels", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for revision in range(2):
                if revision:
                    identities, purposes = ["Revised residents"], ["Revised mission"]

                async def generate():
                    return await gen.generate_batched(client, "offline", f"Population revision {revision}",
                        [DaySchedule(day=1, open_hour=9, close_hour=10)], seed=42)

                people = await generate()
                assert len(people) == len({p.id for p in people}) == 4 and not any(p.twin_of for p in people)
                expected_ids, expected_goals = list(dict.fromkeys(identities or ["shopper"])), list(dict.fromkeys(purposes or ["shopping"]))
                assert [p.identity for p in people] == [expected_ids[i % len(expected_ids)] for i in range(4)]
                assert [p.purpose for p in people] == [expected_goals[i % len(expected_goals)] for i in range(4)]
                assert await generate() == people and len(requests) == 3 * (revision + 1)

    asyncio.run(exercise())


def test_non_enforcing_provider_labels_retain_existing_runtime_behavior():
    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            return schema(personas=[dict(identity="Provider label", purpose="Provider purpose", age_group="30s",
                                        gender="Female", description="Shopper", intent="Shop")])

    people = asyncio.run(gen.generate_personas_for_day(Model(), "offline",
        gen.TradeAreaProfile(keywords=[], identities=["resident"], purposes=["groceries"]), gen.Weekday.MON,
        [gen.HourlyProfile(hour=9, visitor_count=1, person_types=["resident"])]))
    assert len(people) == 1 and people[0].identity == "Provider label" and people[0].purpose == "Provider purpose"
