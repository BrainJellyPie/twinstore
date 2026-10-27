"""An omitted routing field must not discard otherwise usable local-model actions."""
import asyncio
import copy
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
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent as stage
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _persona


@pytest.mark.parametrize("base", [stage.IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("kind,nav", [
    ("enter", "path"), ("move", "path"), ("browse", "path"),
    ("buy", "path"), ("pay", "path"), ("exit", "leave"),
])
@pytest.mark.parametrize("spelling", ["exact", "padded"])
@pytest.mark.parametrize("target", [None, [1, 2]])
def test_missing_navigation_follows_the_explicit_action_without_mutating_input(base, kind, nav, spelling, target):
    raw = {"actions": [{"action": kind if spelling == "exact" else f" {kind.upper()} ",
                        "target": target, "face": "N", "product_sku": "sku-a", "quantity": 2}]}
    original = copy.deepcopy(raw)
    parsed = base.model_validate_json(json.dumps(raw), strict=True)
    action = parsed.actions[0]
    assert action.nav == nav and action.action == kind
    assert action.target == (tuple(target) if target else None)
    assert action.product_sku == "sku-a" and action.quantity == 2
    assert base.model_validate_json(parsed.model_dump_json(), strict=True) == parsed
    assert raw == original


@pytest.mark.parametrize("base", [stage.IntentResponse, ImpulseResponse])
@pytest.mark.parametrize("row", [
    {"target": [1, 2]}, {"action": None}, {"action": "unknown"}, {"action": "wander"},
    {"action": "wander", "area": [0, 0, 3, 3]},
    {"action": "move", "area": [0, 0, 3, 3]},
    {"action": "browse", "area": [0, 0, 3, 3], "target": [1, 2]},
    {"action": "buy", "nav": None}, {"action": "buy", "nav": ""},
    {"action": "buy", "nav": "sideways"}, {"action": "buy", "target": [1]},
    {"action": "buy", "target": [True, 2]},
])
def test_ambiguous_or_explicitly_invalid_routing_still_needs_correction(base, row):
    with pytest.raises(ValidationError):
        base.model_validate_json(json.dumps({"actions": [row]}), strict=True)


@pytest.mark.parametrize("kind", ["enter", "move", "browse", "buy", "pay", "exit", "wander"])
@pytest.mark.parametrize("nav", ["path", "area", "leave"])
def test_an_explicit_navigation_mode_is_not_rewritten(kind, nav):
    result = stage.IntentResponse.model_validate_json(json.dumps({"actions": [
        {"action": kind, "nav": nav, "target": [1, 2], "area": [0, 0, 3, 3]}]}), strict=True)
    assert result.actions[0].nav == nav


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("base", [stage.IntentResponse, ImpulseResponse])
def test_sdk_accepts_omitted_navigation_and_caches_canonical_actions(monkeypatch, tmp_path, mode, base):
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        calls.append(json.loads(request.content))
        data = {"actions": [{"action": "buy", "product_sku": "sku-a", "quantity": 2, "target": [1, 0]},
                            {"action": "exit"}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(data)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/action-navigation", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            first = await client.generate_structured_async(base, "Visit the shop", "Buy two", max_retries=2)
            second = await client.generate_structured_async(base, "Visit the shop", "Buy two", max_retries=2)
            assert first.model_dump() == second.model_dump()
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            assert [action.nav for action in first.actions] == ["path", "leave"]
            cached = json.loads(next(tmp_path.rglob("*.json")).read_text())["result"]
            assert [action["nav"] for action in cached["actions"]] == ["path", "leave"]

    asyncio.run(exercise())


@pytest.mark.parametrize("with_payment", [False, True])
@pytest.mark.parametrize("with_targets", [False, True])
def test_inferred_navigation_keeps_the_requested_purchase_through_checkout(collision_store, with_payment, with_targets):
    raw = {"actions": [
        {"action": "enter", "target": [0, 2]},
        {"action": "browse", "target": [1, 0], "face": "E"},
        {"action": "buy", "target": [1, 0], "face": "E", "product_sku": "sku-a", "quantity": 2},
        {"action": "pay", "target": [4, 1]},
        {"action": "exit"},
    ]}
    if not with_payment:
        raw["actions"] = [row for row in raw["actions"] if row["action"] != "pay"]
    if not with_targets:
        for row in raw["actions"]:
            if row["action"] in {"enter", "browse"}:
                row["target"] = None
    llm = _ScriptedLLM(stage.IntentResponse.model_validate_json(json.dumps(raw), strict=True), ImpulseResponse())
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(_context(collision_store, _persona())))
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert [(item.product_sku, item.quantity) for item in result.purchases] == [("sku-a", 2)]
    assert result.total_spent == 200 and result.dropped_invalid_buys == 0
    assert len([action for action in decision.actions if action.action == Action.PAY]) == 1
