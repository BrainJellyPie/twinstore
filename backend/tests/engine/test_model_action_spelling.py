"""Canonicalize action vocabulary before action-dependent optional-field handling."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _context, _intent, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("stage", ["intent", "impulse"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("field", ["action", "nav", "face", "all"])
def test_spelling_variants_preserve_purchase_execution_and_cache(monkeypatch, tmp_path, collision_store, mode, stage, ordering, field):
    original, calls = llm_client.litellm.acompletion, []

    def vary(payload):
        for action in payload["actions"]:
            for key in ("action", "nav", "face") if field == "all" else (field,):
                if isinstance(action.get(key), str):
                    action[key] = f"\u3000{action[key].swapcase()}\t"
        return payload

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "## 행동 패턴 목록" in system:
            kind, payload = "pattern", {"pattern_id": "exploratory"}
        elif "세렌디피티" in system:
            kind, payload = "impulse", {"actions": [
                {"nav": "path", "action": "browse", "target": [1, 0], "face": "W", "quantity": None, "product_sku": None},
                {"nav": "path", "action": "buy", "target": [1, 0], "face": "W", "product_sku": "sku-b", "quantity": 1}]}
        else:
            kind, payload = "intent", _intent().model_dump(mode="json")
            for action in payload["actions"]:
                if action["action"] != "buy":
                    action.update(quantity=None, product_sku=None)
        calls.append(kind)
        if kind == stage:
            payload = vary(payload)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/action-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            paths = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, paths, SimulationConfig(route_ordering=ordering))
            before = collision_store.model_dump_json()
            decision = await engine.decide_actions(_context(collision_store, _persona()))
            result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, paths, 1)
            assert result.total_spent == 500
            assert {p.product_sku: p.quantity for p in result.purchases} == {"sku-a": 3, "sku-b": 1}
            assert sum(e.action == Action.PAY for e in result.timeline) == 1 and result.timeline[-1].action == Action.EXIT
            assert calls == ["pattern", "intent", "impulse"] and collision_store.model_dump_json() == before
            for path in tmp_path.rglob("*.json"):
                saved = json.loads(path.read_text())
                if "actions" in saved["result"]:
                    for action in saved["result"]["actions"]:
                        assert action["nav"] in {"path", "area", "leave"}
                        assert action["action"] in {a.value for a in Action} | {None}
                        assert action["face"] in {f.value for f in Face} | {None}
                    saved["result"] = vary(saved["result"])
                    path.write_text(json.dumps(saved))
            assert await engine.decide_actions(_context(collision_store, _persona())) == decision
            assert len(calls) == 3 and client.get_usage().cached_requests == 3

    asyncio.run(exercise())


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("action", ["BUY", "Buy", "\u3000buy\t"])
@pytest.mark.parametrize("field", ["product_sku", "quantity"])
def test_buy_spelling_is_resolved_before_nonpurchase_null_defaults(schema, action, field):
    raw = {"actions": [{"nav": "PATH", "action": action, "product_sku": "Sku-A", "quantity": 2, field: None}]}
    with pytest.raises(ValidationError) as caught:
        schema.model_validate_json(json.dumps(raw), strict=True)
    assert any(e["loc"][-1] == field for e in caught.value.errors())


@pytest.mark.parametrize("action", list(Action))
@pytest.mark.parametrize("face", list(Face))
def test_each_known_action_and_face_keeps_its_exact_meaning_without_mutation(action, face):
    raw = {"actions": [{"nav": "AREA", "action": action.value.upper(), "face": face.value.lower(),
                        "area": [0, 0, 2, 2], "product_sku": "Case-Sensitive-SKU", "quantity": 2}]}
    before = json.dumps(raw)
    result = IntentResponse.model_validate_json(before, strict=True).actions[0]
    assert result.action == action and result.face == face and result.nav == "area"
    assert result.product_sku == "Case-Sensitive-SKU" and result.quantity == 2 and result.area == (0, 0, 2, 2)
    assert json.dumps(raw) == before


@pytest.mark.parametrize("schema", [IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("field,value", [("nav", "walk"), ("nav", None), ("action", "purchase"),
                                        ("action", 1), ("face", "north"), ("face", [])])
def test_unknown_vocabulary_remains_invalid(schema, field, value):
    raw = {"actions": [{"nav": "path", "action": "buy", "face": "N", "product_sku": "sku", field: value}]}
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps(raw), strict=True)


def test_authored_domain_action_validation_does_not_change():
    with pytest.raises(ValidationError):
        CustomerAction.model_validate({"nav": "PATH", "action": "BUY", "face": "n"})
