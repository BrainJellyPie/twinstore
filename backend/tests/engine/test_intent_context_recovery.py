"""An oversized intent catalog can recover through a bounded full-catalog selection."""

import asyncio
import json
import re

import httpx
import pytest
from openai import AsyncOpenAI
from instructor.core.exceptions import FailedAttempt, InstructorRetryException
from litellm.exceptions import BadRequestError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.layout_gen.templates import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("correct_selection", [False, True])
def test_full_catalog_is_considered_before_focused_intent_and_cached_recovery(monkeypatch, tmp_path, mode, ordering, correct_selection):
    store = generate_store("urban_cvs")
    original_store = store.model_dump()
    records = stage2_intent.catalog_records(store)
    selected = list(records)[:2]
    original = llm_client.litellm.acompletion
    calls = []
    selection_attempts = 0

    def respond(request):
        nonlocal selection_attempts
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "## 행동 패턴 목록" not in system and "## 후보 상품 선택" not in system:
            assert "1~6 사이의 정수" in system
            if mode == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                name = schema["properties"]["actions"]["items"]["$ref"].rsplit("/", 1)[-1]
                quantity = schema["$defs"][name]["properties"]["quantity"]
                assert quantity["minimum"] == 1 and quantity["maximum"] == 6
        if "## 행동 패턴 목록" in system:
            kind, answer = "pattern", {"pattern_id": "exploratory"}
        elif "## 후보 상품 선택" in system:
            kind = "selection"
            selection_attempts += 1
            assert all(item.name in system for item in records.values())
            answer = {"codes": ["unknown-product-code"] if correct_selection and selection_attempts == 1 else selected}
        elif "세렌디피티" in system:
            kind, answer = "impulse", {"actions": []}
        elif "## 후보 상품 범위" in system:
            kind = "focused"
            shown = set(re.findall(r"^\s*(@+P\d+): ", system, re.MULTILINE))
            assert shown == set(selected)
            assert all(rack.id in system for rack in store.racks if rack.type.value not in {"entrance", "exit"})
            answer = {"actions": [{"nav": "path", "action": "enter"},
                {"nav": "path", "action": "buy", "product_sku": selected[0], "quantity": 2},
                {"nav": "path", "action": "pay"}, {"nav": "leave", "action": "exit"}]}
        else:
            calls.append("full")
            return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                "message": "request (10000 tokens) exceeds the available context size (8192 tokens)"}})
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/intent-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig(route_ordering=ordering))
            first = await engine.decide_actions(_context(store, _persona()))
            second = await engine.decide_actions(_context(store, _persona()))
            assert first == second and client.get_usage().cached_requests == 4
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", first, AStarPathFinder(), 1)
            expected = records[selected[0]]
            assert result.total_spent == 2 * expected.price and result.purchases[0].product_sku == expected.sku
            assert result.timeline[-1].action == Action.EXIT
            assert first.trace["catalog_recovery"]["selected_skus"] == [records[code].sku for code in selected]
            assert first.trace["stage1"]["pattern_id"] == "exploratory"

    asyncio.run(exercise())
    assert calls == ["pattern", "full", "selection", *(["selection"] if correct_selection else []), "focused", "impulse", "full"]
    assert store.model_dump() == original_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("failure", ["unrelated", "forbidden", "rate_limit", "validation", "truncated",
    "selection_context", "selection_invalid", "focused_context"])
def test_http_recovery_is_bounded_and_only_for_input_context(monkeypatch, mode, failure):
    store = generate_store("urban_cvs")
    code = next(iter(stage2_intent.catalog_records(store)))
    original = llm_client.litellm.acompletion
    calls = []
    context_message = "request (10000 tokens) exceeds the available context size (8192 tokens)"

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        kind = ("pattern" if "## 행동 패턴 목록" in system else "selection" if "## 후보 상품 선택" in system
                else "focused" if "## 후보 상품 범위" in system else "full")
        calls.append(kind)
        status, finish = 200, "stop"
        answer = {"pattern_id": "exploratory"}
        if kind == "selection":
            answer = {"codes": ["unknown"] if failure == "selection_invalid" else [code]}
            if failure == "selection_context":
                status = 400
        elif kind == "focused":
            status = 400
        elif kind == "full":
            if failure == "validation":
                answer = {"actions": [{"action": context_message}]}
            elif failure == "truncated":
                answer, finish = {"actions": []}, "length"
            else:
                status = {"forbidden": 403, "rate_limit": 429}.get(failure, 400)
        if status != 200:
            return httpx.Response(status, request=request, json={"error": {"type": "invalid_request_error",
                "message": "Invalid request body" if failure == "unrelated" else context_message}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/intent-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig())
            with pytest.raises(InstructorRetryException):
                await engine.decide_actions(_context(store, _persona()))

    asyncio.run(exercise())
    expected = ["pattern", "full"]
    if failure.startswith("selection_"):
        expected += ["selection", "selection"]
    elif failure == "focused_context":
        expected += ["selection", "focused"]
    assert calls == expected


@pytest.mark.parametrize("kind", ["direct", "wrapped", "earlier_only", "last_only", "small_catalog", "pattern"])
def test_terminal_context_error_and_catalog_size_control_recovery(collision_store, kind):
    context_error = BadRequestError("request (10000 tokens) exceeds the available context size (8192 tokens)",
                                   model="local", llm_provider="openai")
    other = ValueError("invalid response")
    errors = {"wrapped": [context_error], "earlier_only": [context_error, other], "last_only": [other, context_error]}
    error = InstructorRetryException("failed", n_attempts=len(errors[kind]), total_usage=0,
        failed_attempts=[FailedAttempt(i + 1, exc) for i, exc in enumerate(errors[kind])]) if kind in errors else context_error
    store = collision_store if kind == "small_catalog" else generate_store("urban_cvs")

    class Model:
        calls = []

        async def generate_structured_async(self, schema, system, user, **kwargs):
            self.calls.append(schema.__name__)
            if "## 행동 패턴 목록" in system:
                if kind == "pattern":
                    raise error
                return schema.model_validate({"pattern_id": "exploratory"})
            if len(self.calls) == 2:
                raise error
            if "## 후보 상품 선택" in system:
                return schema.model_validate({"codes": []})
            return schema.model_validate({"actions": [{"action": "exit", "nav": "leave"}]})

    model = Model()
    engine = PatternIntentImpulseEngine(model, AStarPathFinder(), SimulationConfig())
    if kind in {"earlier_only", "small_catalog", "pattern"}:
        with pytest.raises(type(error)) as caught:
            asyncio.run(engine.decide_actions(_context(store, _persona())))
        assert caught.value is error
        assert len(model.calls) == (1 if kind == "pattern" else 2)
    else:
        result = asyncio.run(engine.decide_actions(_context(store, _persona())))
        assert result.trace["catalog_recovery"] == {"selected_codes": [], "selected_skus": []}
        assert not any(a.action == Action.BUY for a in result.actions)
        assert result.actions[-1].action == Action.EXIT
        assert model.calls[:4] == ["PatternSelectionResponse", "IntentResponse", "BoundedCatalogSelection", "IntentResponse"]


@pytest.mark.parametrize("maximum", [1, 4, 10])
def test_customer_purchase_breadth_and_duplicate_candidates(maximum):
    store = generate_store("urban_cvs")
    records = stage2_intent.catalog_records(store)
    selected = list(records)[:max(4, maximum)]
    context = _context(store, _persona())
    context.behavior_patterns = [p.model_copy(update={"max_products": maximum}) for p in context.behavior_patterns]

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if "## 행동 패턴 목록" in system:
                return schema.model_validate({"pattern_id": "exploratory"})
            if "## 후보 상품 선택" in system:
                assert schema.model_json_schema()["properties"]["codes"]["maxItems"] == max(4, maximum)
                return schema.model_validate({"codes": selected})
            if "## 후보 상품 범위" in system:
                assert set(re.findall(r"^\s*(@+P\d+): ", system, re.MULTILINE)) == set(selected)
                return schema.model_validate({"actions": [{"action": "exit", "nav": "leave"}]})
            raise BadRequestError("request (10000 tokens) exceeds the available context size (8192 tokens)",
                                  model="local", llm_provider="openai")

    result = asyncio.run(PatternIntentImpulseEngine(Model(), AStarPathFinder(), SimulationConfig()).decide_actions(context))
    assert result.trace["catalog_recovery"]["selected_codes"] == selected
    schema = stage2_intent.catalog_selection_model(records, 4)
    assert schema.model_validate_json(json.dumps({"codes": [selected[0], selected[0]]}), strict=True).codes == [selected[0]]
