"""An explicit model walk-out survives an unused null shopping list."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import entry_decision_model
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("image", [False, True])
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("items", ["null", "empty", "omitted"])
def test_walkout_keeps_its_decision_without_failure_or_rule_fallback(monkeypatch, tmp_path, mode, image, warm, items):
    store, _ = fixture()
    before = store.model_dump_json()
    context = _context(store, _persona(1000))
    context.behavior_patterns = [p for p in context.behavior_patterns if p.id == "purposeful"]
    config = SimulationConfig()
    config.engines.vlm_glance.max_glances = 0
    config.engines.vlm_glance.entrance_image = image
    original, calls = llm_client.litellm.acompletion, []
    answer = {"enter": False, "mission": "turn away", "reason": "already stocked at home"}
    if items != "omitted":
        answer["items"] = None if items == "null" else []
    priming = warm

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = {"enter": True, "items": [{"product": "seen", "qty": 1}]} if priming else answer
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal priming
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/walkout-null-items", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            finder = AStarPathFinder()
            engine = VLMGlanceEngine(client, finder, config)
            if warm:
                prior = context.model_copy(update={"persona": context.persona.model_copy(update={"description": "Previous shopper"})})
                previous = await engine.decide_actions(prior)
                assert any(a.action == Action.BUY for a in previous.actions)
                priming = False
            decision = await engine.decide_actions(context)
            assert decision.trace["plan_source"] == "vlm" and decision.trace["entered"] is False
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, finder, 1)
            assert not result.purchases and result.total_spent == 0
            assert not any(e.action in (Action.BUY, Action.BROWSE, Action.PAY) for e in result.timeline)
            assert result.timeline[-1].action == Action.EXIT
            assert result.timeline[0].description == "turns away: already stocked at home"
            if items == "null":
                for path in tmp_path.rglob("*.json"):
                    entry = json.loads(path.read_text())
                    if entry["result"].get("enter") is False:
                        entry["result"]["items"] = None  # Legacy cache follows the same boundary.
                        path.write_text(json.dumps(entry))
            assert await engine.decide_actions(context) == decision
            assert len(calls) == 1 + int(warm) and client.get_usage().cached_requests == 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("enter", [True, False])
@pytest.mark.parametrize("items", [7, "none", {}, [None]])
def test_other_malformed_lists_remain_invalid(enter, items):
    with pytest.raises(ValidationError):
        entry_decision_model(3).model_validate_json(json.dumps({"enter": enter, "items": items}), strict=True)


@pytest.mark.parametrize("enter", [True, None, "false", 0])
def test_null_items_cannot_guess_a_missing_or_malformed_entry_decision(enter):
    with pytest.raises(ValidationError):
        entry_decision_model(3).model_validate_json(json.dumps({"enter": enter, "items": None}), strict=True)
