"""Null purchase-only fields on non-buy actions must not discard a valid visit."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _context, _intent, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("stage", ["intent", "impulse"])
@pytest.mark.parametrize("fields", [("product_sku",), ("quantity",), ("product_sku", "quantity")])
def test_unused_nulls_preserve_valid_purchases_checkout_exit_and_cache(monkeypatch, tmp_path, collision_store, mode, stage, fields):
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            answer = {"pattern_id": "exploratory"}
        elif len(calls) == 2:
            answer = _intent().model_dump(mode="json")
            if stage == "intent":
                for action in answer["actions"]:
                    if action["action"] != "buy":
                        action.update(dict.fromkeys(fields))
        else:
            assert len(calls) == 3
            answer = {"actions": [
                {"nav": "path", "action": "browse", "target": [1, 0], "face": "W"},
                {"nav": "path", "action": "buy", "target": [1, 0], "face": "W", "product_sku": "sku-b"}]}
            if stage == "impulse":
                answer["actions"][0].update(dict.fromkeys(fields))
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/unused-action-fields", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig())
            decision = await engine.decide_actions(_context(collision_store, _persona()))
            result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
            assert result.total_spent == 500 and len(result.purchases) == 2
            assert {event.product_sku: event.quantity for event in result.purchases} == {"sku-a": 3, "sku-b": 1}
            assert sum(event.action == Action.PAY for event in result.timeline) == 1
            assert result.timeline[-1].action == Action.EXIT
            assert await engine.decide_actions(_context(collision_store, _persona())) == decision and len(calls) == 3

    asyncio.run(exercise())


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("action", [None, "enter", "move", "browse", "pay", "wander", "exit"])
def test_unused_null_defaults_do_not_mutate_the_supplied_response(schema, action):
    raw = {"actions": [{"nav": "path", "action": action, "product_sku": None, "quantity": None}]}
    result = schema.model_validate_json(json.dumps(raw), strict=True)
    assert result.actions[0].product_sku == "" and result.actions[0].quantity == 1
    assert raw["actions"][0]["product_sku"] is None and raw["actions"][0]["quantity"] is None


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("action", ["buy", "not-an-action"])
@pytest.mark.parametrize("field", ["product_sku", "quantity"])
def test_buy_values_and_invalid_actions_are_not_repaired_by_defaulting(schema, action, field):
    raw = {"actions": [{"nav": "path", "action": action, "product_sku": "tea", "quantity": 1, field: None}]}
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps(raw), strict=True)


@pytest.mark.parametrize("field,value", [("product_sku", []), ("product_sku", {}), ("product_sku", 1),
    ("quantity", []), ("quantity", {}), ("quantity", "several")])
def test_non_null_wrong_types_still_fail(field, value):
    with pytest.raises(ValidationError):
        IntentResponse.model_validate_json(json.dumps({"actions": [{"nav": "path", "action": "move", field: value}]}), strict=True)


@pytest.mark.parametrize("field", ["product_sku", "quantity"])
def test_authored_domain_actions_keep_their_original_validation(field):
    with pytest.raises(ValidationError):
        CustomerAction.model_validate({"nav": "path", "action": "pay", field: None})
