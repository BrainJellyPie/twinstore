"""Owner-supplied store facts must reach every stage and separate generation caches."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application import generation_async as ga
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field,values", [
    ("store_type", ["Cafe", "Pharmacy"]),
    ("description", ['차와 간식을 파는 "동네 가게"', "Medicines and health supplies"]),
    ("name", ["Corner Tea", "Community Pharmacy"]),
])
@pytest.mark.parametrize("neighborhood", ["", "Neighborhood model: residents and students."])
def test_store_metadata_reaches_all_generation_stages_and_cache_keys(monkeypatch, tmp_path, mode, field, values, neighborhood):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ga, "neighborhood_text", lambda pid: neighborhood)
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        system = body["messages"][0]["content"]
        if "hourly_profiles" in system:
            payload = {"hourly_profiles": [{"visitor_count": 1, "person_types": ["resident"]}]}
        elif "personas" in system:
            payload = {"personas": [dict(identity="resident", age_group="30s", gender="Female",
                description="Nearby resident", intent="Shop", purpose="shopping", preferred_categories=[])]}
        else:
            # Deliberately identical labels: later stages must still receive changed store facts.
            payload = dict(keywords=["local"], identities=["resident"], purposes=["shopping"])
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/store-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path / "cache")))
            monkeypatch.setattr(ga, "assistive_client", lambda *args, **kwargs: client)
            for revision, value in enumerate(values):
                pid = f"proj_context{revision}"
                meta = dict(address="Same street", customer_profile="동네 주민", currency="USD",
                    supplemental_summary="Receipt evidence: afternoon visits.", **{field: value})
                write_json(metadata_path(pid), meta)

                async def generate():
                    return await ga._run_async_pipeline(config=SimulationConfig(), project_id=pid, meta=meta,
                        schedules=[DaySchedule(day=1, open_hour=9, close_hour=10)], custom_instruction="No invented brands.",
                        supplemental_bytes=None, supplemental_filename="")

                people = await generate()
                assert len(people) == 1
                assert await generate() == people
                assert len(requests) == 3 * (revision + 1), "Changed store facts reused another store's generated customers"
                stored = read_json(metadata_path(pid))
                assert stored["supplemental_summary"] == meta["supplemental_summary"]
                assert stored["customer_profile"] == meta["customer_profile"]
                assert stored[field] == value

            for revision, value in enumerate(values):
                for body in requests[revision * 3:(revision + 1) * 3]:
                    prompt = next(m["content"] for m in body["messages"] if m["role"] == "user")
                    assert json.dumps(value, ensure_ascii=False) in prompt
                    assert f'"{field}"' in prompt
                    assert "동네 주민" in prompt and "Receipt evidence: afternoon visits." in prompt
                    assert "No invented brands." in prompt
                    assert prompt.count("Store details (owner-provided):") == 1
                    if neighborhood:
                        assert neighborhood in prompt

    asyncio.run(exercise())


@pytest.mark.parametrize("fields", [{}, {"name": None, "store_type": None, "description": None},
    {"name": " \t", "store_type": "", "description": "\u3000"}])
def test_absent_legacy_store_facts_leave_existing_evidence_intact(monkeypatch, tmp_path, fields):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ga, "neighborhood_text", lambda pid: "Neighborhood model: residents.")
    monkeypatch.setattr(ga, "assistive_client", lambda *args, **kwargs: object())
    seen = []

    async def generate(**kwargs):
        seen.append(kwargs)
        return []

    monkeypatch.setattr(ga, "_generate_personas_impl", generate)
    asyncio.run(ga._run_async_pipeline(config=SimulationConfig(), project_id="project",
        meta={**fields, "supplemental_summary": "Existing evidence.", "customer_profile": "Customers"},
        schedules=[], custom_instruction="Original instruction", supplemental_bytes=None, supplemental_filename=""))
    assert seen[0]["supplemental_summary"] == "Existing evidence.\nNeighborhood model: residents."
    assert seen[0]["customer_profile"] == "Customers" and seen[0]["custom_instruction"] == "Original instruction"
