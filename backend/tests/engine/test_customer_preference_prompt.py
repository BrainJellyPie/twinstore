"""Default customer generation must not instruct models to erase shopping preferences."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application.generation_async import _generate_personas_impl
from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine
from tests.engine.test_llm_engine_offline import _context
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("path", ["application", "empty_list", "listed"])
@pytest.mark.parametrize("preferences", [["tea"], []])
def test_customer_preferences_survive_default_generation_and_reach_the_planner(monkeypatch, tmp_path, mode, currency, path, preferences):
    original, requests, customer_requests = llm_client.litellm.acompletion, [], []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        system = body["messages"][0]["content"]
        if "hourly_profiles" in system:
            payload = {"hourly_profiles": [{"visitor_count": 1, "person_types": ["resident"]}]}
        elif "personas" in system:
            customer_requests.append(body)
            payload = {"personas": [dict(identity="resident", age_group="30s", gender="Female",
                description="Nearby resident", intent="Buy tea", purpose="shopping", budget_max=1000,
                preferred_categories=preferences)]}
        else:
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/preference-prompt", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def generate():
                schedules = [DaySchedule(day=1, open_hour=9, close_hour=10)]
                if path == "application":
                    return await _generate_personas_impl(client, "offline", "Residents buying tea", schedules, currency=currency)
                return await gen.generate_batched(client, "offline", "Residents buying tea", schedules, currency=currency,
                    categories=["tea", "snacks"] if path == "listed" else [])

            people = await generate()
            assert len(people) == 1 and people[0].preferred_categories == preferences
            assert len(requests) == 3 and len(customer_requests) == 1
            system = customer_requests[0]["messages"][0]["content"]
            user = next(m["content"] for m in customer_requests[0]["messages"] if m["role"] == "user")
            if path == "listed":
                assert "반드시 아래 제공된 카테고리 목록 중에서만 선택" in system
                assert "## 카테고리 목록" in user and "  - tea\n  - snacks" in user
                assert "Infer short English category labels" not in system
            else:
                assert "Infer short English category labels" in system
                assert "## 카테고리 목록" not in user
                assert "반드시 아래 제공된 카테고리 목록 중에서만 선택" not in system
                assert "제공된 목록이 없거나" not in system
            assert await generate() == people and len(requests) == 3

            store, _ = fixture()
            store.racks[0].slots[0].items[0].name = "Tea"
            config = SimulationConfig(budget_tolerance=None)
            config.engines.rule_based.planned_hit_prob = 1
            context = _context(store, people[0])
            context.seed = 0
            context.behavior_patterns = [BehaviorPattern(id="purposeful", name="Shop", description="", grammar="",
                browse_required_before_buy=False, max_products=1, allow_no_purchase=False)]
            plan = RuleBasedEngine(AStarPathFinder(), config)._plan(context)
            assert [action.product_sku for action in plan.buys] == (["seen"] if preferences else [])

    asyncio.run(exercise())
