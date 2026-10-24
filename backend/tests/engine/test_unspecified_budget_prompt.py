"""An unspecified budget must not tell the language model the shopper has zero money."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.prompting import format_budget, format_price
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _intent, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("minimum", [0, 300])
def test_http_pattern_and_intent_prompts_keep_unspecified_budget_meaning(monkeypatch, tmp_path, collision_store,
                                                                       mode, currency, minimum):
    original = llm_client.litellm.acompletion
    calls, budget_lines = [], []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) <= 2:
            user = body["messages"][1]["content"]
            budget = next(line for line in user.splitlines() if line.startswith("- 예산:"))
            budget_lines.append(budget)
            assert "미지정" in budget and "~" not in budget
            if minimum:
                assert format_price(minimum, currency) in budget
        answer = {"pattern_id": "exploratory"} if len(calls) == 1 else _intent().model_dump(mode="json") if len(calls) == 2 else {"actions": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/unspecified-budget", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig(currency=currency))
            context = _context(collision_store, _persona(0).model_copy(update={"budget_min": minimum}))
            decision = await engine.decide_actions(context)
            result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
            assert result.total_spent == 300 and len(result.purchases) == 1 and result.purchases[0].quantity == 3
            assert decision.dropped_over_budget == 0 and result.timeline[-1].action == Action.EXIT
            assert await engine.decide_actions(context) == decision and len(calls) == 3
            assert len(budget_lines) == 2 and budget_lines[0] == budget_lines[1]

    asyncio.run(exercise())


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY", "EUR", "vnd"])
@pytest.mark.parametrize("minimum,maximum", [(0, 1), (0, 1000), (300, 1000), (1000, 1000), (0, 9_007_199_254_740_991)])
def test_explicit_positive_budgets_keep_their_existing_exact_units(currency, minimum, maximum):
    assert format_budget(minimum, maximum, currency) == f"{format_price(minimum, currency)}~{format_price(maximum, currency)}"
