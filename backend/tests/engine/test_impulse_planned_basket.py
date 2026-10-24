"""Impulse decisions must see the exact planned basket, even without narration."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("change", ["product", "quantity", "offer"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
def test_changed_planned_basket_does_not_reuse_another_impulse_answer(monkeypatch, tmp_path, mode, change, ordering):
    store, _ = fixture()
    slot = store.racks[0].slots[0]
    slot.items[0].name = "Base tea"
    second = SlotItem(sku="seen" if change == "offer" else "second", name="Premium tea", price=700)
    if change == "offer":
        store.racks[0].slots.append(slot.model_copy(deep=True, update={"level": 4, "items": [second]}))
    else:
        slot.items.append(second)
    records = stage2_intent.catalog_records(store)
    first_code = next(code for code, offer in records.items() if offer.name == "Base tea")
    second_code = next(code for code, offer in records.items() if offer.name == "Premium tea")
    original, calls, impulse_prompts = llm_client.litellm.acompletion, [], []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "## 행동 패턴 목록" in system:
            payload = {"pattern_id": "exploratory"}
        elif "세렌디피티" in system:
            impulse_prompts.append(user)
            payload = {"reasoning": f"Basket review {len(impulse_prompts)}", "actions": []}
        else:
            revised = "Basket revision 1" in user
            payload = {"actions": [
                {"nav": "path", "action": "enter"},
                {"nav": "path", "action": "browse", "target": [2, 2], "face": "S"},
                {"nav": "path", "action": "buy", "product_sku": second_code if revised and change != "quantity" else first_code,
                 "quantity": 3 if revised and change == "quantity" else 1, "target": [2, 2], "face": "S"},
                {"nav": "path", "action": "pay"}, {"nav": "leave"},
            ]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/planned-basket", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            pathfinder = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, pathfinder, SimulationConfig(route_ordering=ordering))
            for revision in range(2):
                context = _context(store, _persona(10000))
                context.behavior_patterns = [p.model_copy(update={"grammar": f"Basket revision {revision}"})
                                             for p in context.behavior_patterns]
                decision = await engine.decide_actions(context)
                cached = await engine.decide_actions(context)
                assert cached.model_dump() == decision.model_dump()
                result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, pathfinder, 1)
                assert result.total_spent == (100 if not revision else 300 if change == "quantity" else 700)
                assert result.timeline[-1].action == Action.EXIT
                assert decision.trace["stage3"]["reasoning"] == f"Basket review {revision + 1}"
            assert len(calls) == 5 and len(impulse_prompts) == 2
            assert impulse_prompts[0] != impulse_prompts[1]
            for revision, prompt in enumerate(impulse_prompts):
                buy = next(line.split("buy: ", 1)[1] for line in prompt.splitlines() if "buy: " in line)
                basket = json.loads(buy)
                premium = bool(revision and change != "quantity")
                quantity = 3 if revision and change == "quantity" else 1
                assert basket == {"sku": second.sku if premium else "seen", "quantity": quantity,
                    "name": "Premium tea" if premium else "Base tea", "unit_price": 700 if premium else 100,
                    "line_total": (700 if premium else 100) * quantity, "currency": "USD"}

    asyncio.run(exercise())


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("quantity", [0, 1, 99])
@pytest.mark.parametrize("maximum", [1, 2, 6])
def test_basket_facts_match_executed_quantity_and_keep_names_promotions(currency, quantity, maximum):
    store, intent = fixture()
    store.currency = currency
    item = store.racks[0].slots[0].items[0]
    item.name, item.promo = '동네 "Tea"', 'Tea \\ special'
    intent = stage2_intent.IntentResponse.model_validate({"actions": [
        *intent.model_dump(mode="json")["actions"],
        {"nav": "path", "action": "buy", "product_sku": item.sku, "target": [2, 2], "face": "S",
         "quantity": quantity, "description": "A short model note"},
    ]})
    original = store.model_dump()
    model = _ScriptedLLM(intent, ImpulseResponse())
    pathfinder = AStarPathFinder()
    engine = PatternIntentImpulseEngine(model, pathfinder, SimulationConfig(currency=currency, max_quantity_per_line=maximum))
    decision = asyncio.run(engine.decide_actions(_context(store, _persona())))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, pathfinder, 1, max_quantity=maximum)
    prompt = next(user for name, _, user, _ in model.calls if name == "ImpulseResponse")
    line = next(line.split("buy: ", 1)[1] for line in prompt.splitlines() if "buy: " in line)
    basket, end = json.JSONDecoder().raw_decode(line)
    assert line[end:].strip() == "A short model note"
    assert basket == {"sku": item.sku, "quantity": result.purchases[0].quantity, "name": item.name,
        "unit_price": item.price, "line_total": result.total_spent, "currency": currency, "promotion": item.promo}
    assert basket["quantity"] == max(1, min(quantity, maximum))
    assert store.model_dump() == original
