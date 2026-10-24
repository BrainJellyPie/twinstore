"""Model checkout instructions cannot break a supported layout with no counter."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.validation import validate
from tests.engine.test_llm_engine_offline import _context, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("counter", [False, True])
@pytest.mark.parametrize("target", [None, [0, 0], [-900, 900]])
def test_duplicate_misplaced_payments_keep_purchases_exit_and_cache(monkeypatch, tmp_path, mode, ordering, counter, target):
    store = generate_store("station_kiosk")
    if not counter:
        store.racks = [r for r in store.racks if r.type.value != "counter"]
    assert not [issue for issue in validate(store) if issue.severity == "error"]
    before = store.model_dump()
    item = store.product_racks[0].slots[0].items[0]
    code = next(code for code, offer in stage2_intent.catalog_records(store).items() if offer.sku == item.sku)
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            payload = {"pattern_id": "exploratory"}
        elif len(calls) == 2:
            # Includes a duplicated early checkout and a purchase with no location hint.
            payload = {"actions": [
                {"nav": "path", "action": "enter"},
                {"nav": "path", "action": "pay", "target": target, "dwell": 7},
                {"nav": "path", "action": "buy", "product_sku": code, "quantity": 2},
                {"nav": "path", "action": "pay", "target": target, "dwell": 19},
                {"nav": "leave"},
            ]}
        else:
            assert len(calls) == 3
            payload = {"actions": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/counterless-visit", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            pathfinder = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, pathfinder, SimulationConfig(route_ordering=ordering))
            context = _context(store, _persona(10000))
            decision = await engine.decide_actions(context)
            cached = await engine.decide_actions(context)
            assert cached.model_dump() == decision.model_dump() and len(calls) == 3
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, pathfinder, 1)
            assert [(p.product_sku, p.quantity) for p in result.purchases] == [(item.sku, 2)]
            assert result.total_spent == item.price * 2
            payments = [event for event in result.timeline if event.action == Action.PAY]
            assert len(payments) == int(counter)
            if counter:
                assert payments[0].duration == 19
                assert payments[0].elapsed_sec > result.purchases[0].elapsed_sec
            assert result.timeline[-1].action == Action.EXIT
            assert store.model_dump() == before

    asyncio.run(exercise())
