"""Local action grammars must share the executor's per-line quantity ceiling."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _intent, _persona


@pytest.mark.parametrize("maximum", [1, 2, 6, 12])
@pytest.mark.parametrize("obeys", [False, True])
def test_http_quantity_grammar_matches_execution_while_non_enforcing_responses_still_clamp(monkeypatch, tmp_path,
                                                                                       collision_store, maximum, obeys):
    original = llm_client.litellm.acompletion
    calls = []
    active_maximum = maximum

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        if "## 행동 패턴 목록" in system:
            answer = {"pattern_id": "exploratory"}
        else:
            schema = body["response_format"]["json_schema"]["schema"]
            name = schema["properties"]["actions"]["items"]["$ref"].rsplit("/", 1)[-1]
            quantity = schema["$defs"][name]["properties"]["quantity"]
            assert quantity["minimum"] == 1 and quantity["maximum"] == active_maximum
            assert f"1~{active_maximum} 사이의 정수" in system
            if "세렌디피티" not in system:
                answer = _intent().model_dump(mode="json")
                answer["actions"][2]["quantity"] = active_maximum if obeys else 10**100
            else:
                answer = {"actions": [{"nav": "path", "action": "buy", "target": [1, 0], "face": "W",
                    "product_sku": "sku-b", "quantity": active_maximum if obeys else 10**100}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal active_maximum
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/quantity-grammar", api_base="http://127.0.0.1:8081/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))
            context = _context(collision_store, _persona(0))
            for active_maximum in (maximum, maximum + 1):
                engine = PatternIntentImpulseEngine(client, AStarPathFinder(),
                    SimulationConfig(max_quantity_per_line=active_maximum))
                decision = await engine.decide_actions(context)
                result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1,
                                          max_quantity=active_maximum)
                assert result.total_spent == active_maximum * 300 and len(result.purchases) == 2
                assert all(event.quantity == active_maximum for event in result.purchases)
                assert result.timeline[-1].action == Action.EXIT
                assert await engine.decide_actions(context) == decision
                assert len(calls) == (3 if active_maximum == maximum else 5)

    asyncio.run(exercise())
