"""Missing model label pools must not ask later stages to choose from an empty list."""

import asyncio
import json
import re
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("provider", ["json", "schema", "schema_non_enforcing"])
@pytest.mark.parametrize("missing", ["identities", "purposes", "both"])
def test_empty_pools_keep_coherent_labels_through_traffic_customers_and_cache(monkeypatch, tmp_path, provider, missing):
    original = llm_client.litellm.acompletion
    calls, identity, purpose = [], "", ""

    def respond(request):
        nonlocal identity, purpose
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "hourly_profiles" in system:
            labels = re.findall(r"^  - (.+)$", user, re.MULTILINE)
            payload = {"hourly_profiles": [{"hour": 9, "visitor_count": 3, "person_types": labels[:1]}]}
        elif "personas" in system:
            identity_section, purpose_section = user.split("## purpose 목록", 1)
            ids = re.findall(r"^  - (.+)$", identity_section, re.MULTILINE)
            purposes = re.findall(r"^  - (.+)$", purpose_section, re.MULTILINE)
            count = len(re.findall(r"^\[\d+\] \d+시", user, re.MULTILINE))
            payload = {"personas": [dict(identity=ids[0] if ids else "", purpose=purposes[0] if purposes else "",
                age_group="30s", gender="Female", description=f"Shopper {i}", intent="Groceries") for i in range(count)]}
        else:
            bounds = body["response_format"]["json_schema"]["schema"]["properties"] if provider != "json" else {}
            if provider != "json":
                assert bounds["identities"]["minItems"] == bounds["purposes"]["minItems"] == 1
            identity = "resident" if missing == "purposes" or provider == "schema" else ""
            purpose = "groceries" if missing == "identities" or provider == "schema" else ""
            payload = {"keywords": [], "identities": [identity] if identity else [], "purposes": [purpose] if purpose else []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/empty-label-pools", api_base="http://127.0.0.1:8081/v1",
                structured_output="json" if provider == "json" else "json_schema", cache_dir=str(tmp_path)))

            async def generate():
                return await gen.generate_batched(client, "offline", "동네 주민",
                    [DaySchedule(day=d, open_hour=9, close_hour=10) for d in [1, 7]], seed=42)

            people = await generate()
            assert {p.identity for p in people} == {identity or "shopper"}
            assert {p.purpose for p in people} == {purpose or "shopping"}
            assert Counter((int(p.day), p.arrival_hour) for p in people) == {(1, 9): 3, (7, 9): 3}
            assert len({p.id for p in people}) == 6 and not any(p.twin_of for p in people)
            assert await generate() == people and len(calls) == 5
            traffic_users = [next(m["content"] for m in b["messages"] if m["role"] == "user")
                             for b in calls if "hourly_profiles" in b["messages"][0]["content"]]
            assert all(f"  - {identity or 'shopper'}" in prompt for prompt in traffic_users)

    asyncio.run(exercise())


def test_runtime_still_accepts_empty_lists_and_keeps_invalid_structures_strict():
    from pydantic import ValidationError

    assert gen.TradeAreaProfile(keywords=[], identities=[], purposes=[]).identities == []
    for field in ["identities", "purposes"]:
        with pytest.raises(ValidationError):
            gen.TradeAreaProfile.model_validate({"keywords": [], "identities": [], "purposes": [], field: None})
