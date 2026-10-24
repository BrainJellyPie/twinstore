"""Missing primary candidate selection is not evidence of an empty shopping goal."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("outcome", ["repeated", "corrected", "legacy_cache", "explicit_empty", "optional_impulse"])
def test_candidate_selection_distinguishes_missing_from_empty(monkeypatch, tmp_path, mode, ordering, outcome):
    store, intent = fixture()
    store.racks[0].slots[0].items = [SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=100) for i in range(6)]
    code = next(code for code, item in stage2_intent.catalog_records(store).items() if item.sku == "seen0")
    good = intent.model_dump(mode="json")
    good["actions"].insert(-1, {"nav": "path", "action": "buy", "product_sku": code, "quantity": 2})
    original, calls = llm_client.litellm.acompletion, []
    phase = "prime" if outcome == "legacy_cache" else "missing"

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        is_impulse = "세렌디피티" in system
        overflow = (is_impulse if outcome == "optional_impulse" else
                    "## 행동 패턴 목록" not in system and "## 후보 상품 선택" not in system
                    and not is_impulse and "## 후보 상품 범위" not in system)
        if overflow:
            calls.append("full")
            return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                "message": "request (8500 tokens) exceeds the available context size (8192 tokens)"}})
        if "## 행동 패턴 목록" in system:
            kind, answer = "pattern", {"pattern_id": "exploratory"}
        elif "## 충동 후보 선택" in system:
            kind, answer = "optional_selection", {}
        elif "## 후보 상품 선택" in system:
            kind = "selection"
            if outcome == "explicit_empty":
                answer = {"codes": []}
            elif phase == "missing" and not (outcome == "corrected" and calls.count("selection") > 0):
                answer = {} if calls.count("selection") % 2 == 0 else {"reasoning": "Still considering"}
            else:
                answer = {"codes": [code]}
        elif is_impulse:
            kind, answer = "impulse", {}
        else:
            kind = "intent"
            answer = {"actions": []} if outcome == "explicit_empty" or phase == "missing" and outcome != "corrected" and outcome != "optional_impulse" else good
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/required-candidates", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            finder = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, finder, SimulationConfig(route_ordering=ordering))
            context = _context(store, _persona(10000))
            before = store.model_dump_json()
            if outcome == "legacy_cache":
                await engine.decide_actions(context)
                matches = []
                for path in tmp_path.rglob("*.json"):
                    saved = json.loads(path.read_text())
                    if saved["result"].get("codes") == [code]:
                        saved["result"] = {}
                        path.write_text(json.dumps(saved))
                        matches.append(path)
                assert len(matches) == 1
                phase = "missing"
            if outcome in {"repeated", "legacy_cache"}:
                before_intent, before_selection = calls.count("intent"), calls.count("selection")
                with pytest.raises(InstructorRetryException):
                    await engine.decide_actions(context)
                assert calls.count("intent") == before_intent
                assert calls.count("selection") == before_selection + 2
                phase = "complete"
            decision = await engine.decide_actions(context)
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, finder, 1)
            assert result.timeline[-1].action == Action.EXIT
            if outcome == "explicit_empty":
                assert result.total_spent == 0 and result.purchases == []
                assert decision.trace["catalog_recovery"] == {"selected_codes": [], "selected_skus": []}
            else:
                assert result.total_spent == 200
                assert [(p.product_sku, p.quantity, p.origin) for p in result.purchases] == [("seen0", 2, "planned")]
                assert sum(e.action == Action.PAY for e in result.timeline) == 1
                if outcome == "optional_impulse":
                    assert decision.trace["impulse_catalog_recovery"] == {"selected_codes": [], "selected_skus": []}
                else:
                    assert decision.trace["catalog_recovery"] == {"selected_codes": [code], "selected_skus": ["seen0"]}
            if outcome == "corrected":
                assert calls.count("selection") == 2
            selections = calls.count("selection") + calls.count("optional_selection")
            assert await engine.decide_actions(context) == decision
            assert calls.count("selection") + calls.count("optional_selection") == selections
            assert store.model_dump_json() == before

    asyncio.run(exercise())


def test_primary_selection_grammar_requires_codes_without_changing_optional_selection():
    records = {"@P1": SlotItem(sku="tea", name="Tea", price=100)}
    primary = stage2_intent.catalog_selection_model(records, 4, required=True)
    schema = primary.model_json_schema()
    assert "codes" in schema["required"]
    assert schema["properties"]["codes"]["maxItems"] == 1
    assert schema["properties"]["codes"]["items"]["enum"] == ["@P1"]
    for payload in ({}, {"codes": None}, {"codes": ["unknown"]}):
        with pytest.raises(ValidationError):
            primary.model_validate_json(json.dumps(payload), strict=True)
    assert primary.model_validate_json('{"codes": []}', strict=True).codes == []
    assert stage2_intent.catalog_selection_model(records, 4).model_validate_json('{}', strict=True).codes == []
