"""Category preferences remain evidence in shelf glances and their response-cache identity."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Face
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("categories", [
    ["caffeine-free tea", "fresh fruit"], [], ["차", "豆乳", "café"], ["tea", "tea", "fruit"],
])
def test_glance_receives_changed_or_cleared_category_preferences(monkeypatch, tmp_path, mode, categories):
    store, _ = fixture()
    cfg = SimulationConfig(budget_tolerance=None)
    cfg.engines.vlm_glance.plan_policy = "rule"
    cfg.engines.vlm_glance.glance_policy = "all"
    cfg.engines.vlm_glance.image_width = 256
    cfg.engines.vlm_glance.max_glances = 1
    context = _context(store, _persona())
    context.behavior_patterns = [BehaviorPattern(id="purposeful", name="Shop", description="", grammar="",
        browse_required_before_buy=False, max_products=4)]
    revised = context.model_copy(update={"persona": context.persona.model_copy(update={"preferred_categories": categories})})
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"number": 0, "product": "", "interest": 0})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/glance-preferences", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = VLMGlanceEngine(client, AStarPathFinder(), cfg)

            def plan(trip):
                prepared, middle = engine._begin_plan(trip)
                middle.append(CustomerAction(nav="path", action=Action.BROWSE, target=(2, 2), face=Face.S))
                return engine.close_plan(store, prepared, middle)

            monkeypatch.setattr(engine, "_plan", plan)
            initial = await engine.decide_actions(context)
            assert initial.trace["vlm_calls"] == 1 and len(calls) == 1
            assert await engine.decide_actions(context) == initial and len(calls) == 1
            changed = await engine.decide_actions(revised)
            assert len(calls) == 2, "Changed preferences reused the previous shelf answer"
            user = next(m["content"][0]["text"] for m in calls[-1]["messages"] if m["role"] == "user")
            assert all(category in user for category in categories)
            assert "snacks" not in user
            assert "Already in basket: nothing yet." in user and "Came for: snack" in user
            assert await engine.decide_actions(revised) == changed and len(calls) == 2
            assert client.get_usage().cached_requests == 2

    asyncio.run(exercise())
