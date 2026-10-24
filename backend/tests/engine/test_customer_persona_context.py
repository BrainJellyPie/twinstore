"""The actual customer writer must retain profile/evidence, including its cache key."""

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


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("source", ["profile", "supplemental", "both"])
@pytest.mark.parametrize("workflow", ["all", "probe", "context", "truncated"])
def test_customer_evidence_survives_labels_cache_probe_and_batch_recovery(monkeypatch, tmp_path, mode, source, workflow):
    original = llm_client.litellm.acompletion
    calls, writing = [], []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        calls.append(body)
        finish = "stop"
        if "hourly_profiles" in system:
            payload = {"hourly_profiles": [{"hour": h, "visitor_count": n, "person_types": ["resident"]}
                                            for h, n in [(9, 2), (17, 3)]]}
        elif "personas" in system:
            writing.append(user)
            hours = [int(h) for h in re.findall(r"^\[\d+\] (\d+)시", user, re.MULTILINE)]
            if len(hours) > 3 and workflow == "context":
                return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                    "message": "request (9000 tokens) exceeds the available context size (8192 tokens)"}})
            if len(hours) > 3 and workflow == "truncated":
                finish = "length"
            budgets = re.findall(r"Budget: (\d+)", user)
            budget = int(budgets[-1]) if budgets else 100
            preference = "tea" if "Preference: tea" in user else "snacks" if "Preference: snacks" in user else ""
            payload = {"personas": [dict(identity="resident", age_group="30s", gender="Female",
                description=f"Resident at {hour}", intent="Groceries", purpose="groceries", budget_max=budget,
                preferred_categories=[preference] if preference else []) for hour in hours]}
        else:
            # Both revisions deliberately produce identical labels and traffic.
            payload = dict(keywords=["nearby"], identities=["resident"], purposes=["groceries"])
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/persona-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def decide(plan):
                assert plan.probe_customers == 3
                return plan.all.per_day

            for budget, preference in [(500, "tea"), (900, "snacks")]:
                evidence = f"Budget: {budget}; Preference: {preference}."
                profile = f"동네 주민. {evidence}" if source in {"profile", "both"} else "동네 주민"
                summary = evidence if source == "supplemental" else "Resident survey: no brand preference." if source == "both" else ""

                async def generate():
                    return await gen.generate_batched(client, "offline", profile,
                        [DaySchedule(day=d, open_hour=8, close_hour=20) for d in [1, 7]], seed=42, batch_size=5,
                        categories=["tea", "snacks"], supplemental_summary=summary,
                        decide=decide if workflow == "probe" else None)

                before_writing = len(writing)
                people = await generate()
                assert {p.budget_max for p in people} == {budget}
                assert all(p.preferred_categories == [preference] and not p.twin_of for p in people)
                assert Counter((int(p.day), p.arrival_hour) for p in people) == {(d, h): n for d in [1, 7] for h, n in [(9, 2), (17, 3)]}
                assert len({p.id for p in people}) == 10
                prompts = writing[before_writing:]
                assert prompts and all(text.count(evidence) == 1 for text in prompts)
                assert all(profile in text and (not summary or summary in text) for text in prompts)
                previous, hits = len(calls), client.get_usage().cached_requests
                assert await generate() == people
                assert client.get_usage().cached_requests > hits
                if workflow in {"all", "probe"}:
                    assert len(calls) == previous

    asyncio.run(exercise())
