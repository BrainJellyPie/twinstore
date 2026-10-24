"""An omitted primary action list must not become a successful empty visit."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.rack import Slot, SlotItem
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent, stage3_impulse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("recovery", [False, True])
@pytest.mark.parametrize("payload", [{}, {"reasoning": "Considering this visit"}])
@pytest.mark.parametrize("legacy_cache", [False, True])
def test_primary_actions_are_required_on_full_and_focused_requests(monkeypatch, tmp_path, mode, ordering,
                                                                recovery, payload, legacy_cache):
    store, intent = fixture()
    store.racks[0].slots[0].items = [SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=100) for i in range(4)]
    store.racks[0].slots.append(Slot(block=0, face="S", level=2, items=[
        SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=100) for i in range(4, 6)]))
    before = store.model_dump_json()
    code = next(code for code, item in stage2_intent.catalog_records(store).items() if item.sku == "seen0")
    good = intent.model_dump(mode="json")
    good["reasoning"] = "Complete primary plan"
    good["actions"].insert(-1, {"nav": "path", "action": "buy", "product_sku": code, "quantity": 2})
    calls, phase = [], "prime" if legacy_cache else "missing"
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "## 행동 패턴 목록" in system:
            kind, answer = "pattern", {"pattern_id": "exploratory"}
        elif "## 후보 상품 선택" in system:
            kind, answer = "selection", {"codes": [code]}
        elif "세렌디피티" in system:
            kind, answer = "impulse", {"reasoning": "No additional reaction"}
        elif recovery and "## 후보 상품 범위" not in system:
            calls.append("full")
            return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                "message": "request (8500 tokens) exceeds the available context size (8192 tokens)"}})
        else:
            kind, answer = "intent", payload if phase == "missing" else good
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/required-intent", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            finder = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, finder, SimulationConfig(route_ordering=ordering))
            context = _context(store, _persona(10000))
            pattern = next(p for p in context.behavior_patterns if p.id == "exploratory")
            context.behavior_patterns = [pattern.model_copy(update={"max_products": 2})]
            if legacy_cache:
                await engine.decide_actions(context)
                matches = []
                for path in tmp_path.rglob("*.json"):
                    cached = json.loads(path.read_text())
                    if cached["result"].get("reasoning") == "Complete primary plan":
                        matches.append(path)
                        cached["result"].pop("actions")
                        path.write_text(json.dumps(cached))
                assert len(matches) == 1
                phase = "missing"
            impulses_before = calls.count("impulse")
            with pytest.raises(InstructorRetryException):
                await engine.decide_actions(context)
            assert calls.count("impulse") == impulses_before
            phase = "complete"
            decision = await engine.decide_actions(context)
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, finder, 1)
            assert [(p.product_sku, p.quantity) for p in result.purchases] == [("seen0", 2)]
            assert result.total_spent == 200 and result.timeline[-1].action == Action.EXIT
            assert sum(event.action == Action.PAY for event in result.timeline) == 1
            assert decision.trace["stage3"]["actions"] == []
            assert await engine.decide_actions(context) == decision
            assert calls.count("intent") == 2 + int(legacy_cache)
            assert store.model_dump_json() == before

    asyncio.run(exercise())


def test_primary_model_grammar_requires_actions_but_explicit_empty_and_optional_reactions_remain_valid():
    primary = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, {})
    assert "actions" in primary.model_json_schema().get("required", [])
    with pytest.raises(ValidationError):
        primary.model_validate_json('{}', strict=True)
    assert primary.model_validate_json('{"actions": []}', strict=True).actions == []
    assert stage2_intent.IntentResponse().actions == []
    optional = stage2_intent.catalog_response_model(stage3_impulse.ImpulseResponse, {})
    for payload in [{}, {"actions": []}, {"actions": None}]:
        assert optional.model_validate_json(json.dumps(payload), strict=True).actions == []
