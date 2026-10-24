"""An absent optional reaction must not discard an already valid planned visit."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.rack import SlotItem
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
@pytest.mark.parametrize("shape", ["null", "empty", "omitted"])
def test_no_extra_reaction_preserves_planned_purchases_and_cache(monkeypatch, tmp_path, mode, ordering, recovery, shape):
    store, intent = fixture()
    store.racks[0].slots[0].items = [SlotItem(sku=f"seen{i}", name=f"Visible tea {i}", price=100 + 10 * i)
                                   for i in range(6)]
    records = stage2_intent.catalog_records(store)
    code = next(code for code, item in records.items() if item.sku == "seen0")
    original_store = store.model_dump()
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "## 행동 패턴 목록" in system:
            kind, payload = "pattern", {"pattern_id": "exploratory"}
        elif "## 충동 후보 선택" in system:
            kind, payload = "selection", {"codes": [code]}
        elif "세렌디피티" in system:
            if recovery and "Context recovery candidates" not in user:
                calls.append("full")
                return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                    "message": "request (8500 tokens) exceeds the available context size (8192 tokens)"}})
            kind, payload = "impulse", {"reasoning": "No extra reaction."}
            if shape != "omitted":
                payload["actions"] = None if shape == "null" else []
        else:
            kind, payload = "intent", intent.model_dump(mode="json")
            payload["actions"].insert(-1, dict(nav="path", action="buy", product_sku=code, quantity=2))
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/optional-impulse", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            pathfinder = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, pathfinder, SimulationConfig(route_ordering=ordering))
            context = _context(store, _persona(10000))
            first = await engine.decide_actions(context)
            # A legacy cached null must pass through the same model boundary.
            if shape == "null":
                found = 0
                for path in tmp_path.glob("*/*.json"):
                    saved = json.loads(path.read_text())
                    if saved["result"].get("reasoning") == "No extra reaction.":
                        saved["result"]["actions"] = None
                        path.write_text(json.dumps(saved))
                        found += 1
                assert found == 1
            second = await engine.decide_actions(context)
            assert first == second
            assert client.get_usage().cached_requests == (4 if recovery else 3)
            assert first.trace["stage3"]["actions"] == []
            assert first.trace["stage3"]["reasoning"] == "No extra reaction."
            if recovery:
                assert first.trace["impulse_catalog_recovery"] == {"selected_codes": [code], "selected_skus": ["seen0"]}
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", first, pathfinder, 1)
            assert [(p.product_sku, p.quantity, p.origin) for p in result.purchases] == [("seen0", 2, "planned")]
            assert result.total_spent == 200
            assert result.timeline[-1].action == Action.EXIT
            assert sum(e.action == Action.PAY for e in result.timeline) == 1
            assert store.model_dump() == original_store

    asyncio.run(exercise())
    assert calls == ["pattern", "intent", *(["full", "selection"] if recovery else []), "impulse",
                     *(["full"] if recovery else [])]


@pytest.mark.parametrize("bad", [{}, "", False, 0, [None], ["buy"]])
@pytest.mark.parametrize("constrained", [False, True])
def test_nonnull_malformed_impulse_lists_stay_strict(bad, constrained):
    schema = (stage2_intent.catalog_response_model(stage3_impulse.ImpulseResponse, {})
              if constrained else stage3_impulse.ImpulseResponse)
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({"actions": bad}), strict=True)


@pytest.mark.parametrize("constrained", [False, True])
def test_null_planned_actions_are_still_rejected(constrained):
    schema = (stage2_intent.catalog_response_model(stage2_intent.IntentResponse, {})
              if constrained else stage2_intent.IntentResponse)
    with pytest.raises(ValidationError):
        schema.model_validate_json('{"actions":null}', strict=True)
