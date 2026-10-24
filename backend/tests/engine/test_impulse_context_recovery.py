"""An oversized exposure prompt must recover without losing the actual visit."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from instructor.core.exceptions import FailedAttempt, InstructorRetryException
from litellm.exceptions import BadRequestError

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
@pytest.mark.parametrize("repair", [False, True])
@pytest.mark.parametrize("intent_recovery", [False, True])
def test_context_recovery_considers_all_exposure_and_preserves_basket_cache_and_execution(monkeypatch, tmp_path, mode, ordering, repair, intent_recovery):
    store, intent = fixture()
    slot = store.racks[0].slots[0]
    slot.items = [SlotItem(sku=f"seen{i}", name=f"Visible tea {i}", price=100 + i * 10) for i in range(6)]
    records = stage2_intent.catalog_records(store)
    first_code = next(code for code, item in records.items() if item.sku == "seen0")
    selected_code = next(code for code, item in records.items() if item.sku == "seen5")
    original_store = store.model_dump()
    original, calls = llm_client.litellm.acompletion, []
    selection_attempts = 0

    def respond(request):
        nonlocal selection_attempts
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "## 행동 패턴 목록" in system:
            kind, payload = "pattern", {"pattern_id": "exploratory"}
        elif "## 후보 상품 선택" in system:
            kind, payload = "intent_selection", {"codes": [first_code]}
        elif "## 충동 후보 선택" in system:
            kind = "selection"
            selection_attempts += 1
            assert all(item.name in user for item in slot.items) and "unseen" not in user
            assert '"quantity":1' in user and '"line_total":100' in user
            payload = {"codes": ["unknown"] if repair and selection_attempts == 1 else [selected_code, selected_code]}
        elif "세렌디피티" in system:
            if "Context recovery candidates" not in user:
                calls.append("full")
                return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                    "message": "request (8500 tokens) exceeds the available context size (8192 tokens)"}})
            kind = "focused"
            exposure = user.split("## 경로상 노출되는 상품", 1)[1].split("## 고객 성향", 1)[0]
            assert "Visible tea 5" in exposure and "Visible tea 0" not in exposure and "unseen" not in exposure
            assert '"name":"Visible tea 0"' in user
            if mode == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                action = schema["$defs"][schema["properties"]["actions"]["items"]["$ref"].rsplit("/", 1)[1]]
                assert action["properties"]["product_sku"]["enum"] == ["", selected_code]
            payload = {"actions": [{"nav": "path", "action": "buy", "product_sku": selected_code,
                "quantity": 2, "target": [10, 2], "face": "S"}]}
        else:
            if intent_recovery and "## 후보 상품 범위" not in system:
                calls.append("intent_full")
                return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                    "message": "request (8500 tokens) exceeds the available context size (8192 tokens)"}})
            kind = "intent"
            payload = intent.model_dump(mode="json")
            payload["actions"].insert(-1, dict(nav="path", action="buy", product_sku=first_code, quantity=1))
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/impulse-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            pathfinder = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, pathfinder, SimulationConfig(route_ordering=ordering, max_quantity_per_line=2))
            context = _context(store, _persona(10000))
            first = await engine.decide_actions(context)
            second = await engine.decide_actions(context)
            assert first.model_dump() == second.model_dump()
            assert first.trace["impulse_catalog_recovery"] == {"selected_codes": [selected_code], "selected_skus": ["seen5"]}
            if intent_recovery:
                assert first.trace["catalog_recovery"] == {"selected_codes": [first_code], "selected_skus": ["seen0"]}
            assert set(first.trace["exposed_skus"]) == {item.sku for item in slot.items}
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", first, pathfinder, 1, max_quantity=2)
            assert {(p.product_sku, p.quantity, p.origin) for p in result.purchases} == {("seen0", 1, "planned"), ("seen5", 2, "impulse")}
            assert result.total_spent == 400 and result.timeline[-1].action == Action.EXIT
            assert sum(e.action == Action.PAY for e in result.timeline) == 1
            assert store.model_dump() == original_store

    asyncio.run(exercise())
    assert calls == ["pattern", *(["intent_full", "intent_selection"] if intent_recovery else []),
        "intent", "full", "selection", *(["selection"] if repair else []), "focused",
        *(["intent_full"] if intent_recovery else []), "full"]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("failure", ["unrelated", "unauthorized", "forbidden", "rate_limit", "validation", "truncated",
    "selection_context", "selection_invalid", "focused_context"])
def test_failed_recovery_is_bounded_and_other_failures_do_not_select(monkeypatch, mode, failure):
    store, intent = fixture()
    store.racks[0].slots[0].items = [SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=100) for i in range(6)]
    code = next(iter(stage2_intent.catalog_records(store)))
    original, calls = llm_client.litellm.acompletion, []
    context_message = "request (8500 tokens) exceeds the available context size (8192 tokens)"

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        kind = ("pattern" if "## 행동 패턴 목록" in system else "selection" if "## 충동 후보 선택" in system
                else "focused" if "Context recovery candidates" in user else "full" if "세렌디피티" in system else "intent")
        calls.append(kind)
        status, finish = 200, "stop"
        payload = {"pattern_id": "exploratory"}
        if kind == "intent":
            payload = intent.model_dump(mode="json")
        elif kind == "selection":
            payload = {"codes": ["unknown"] if failure == "selection_invalid" else [code]}
            if failure == "selection_context":
                status = 400
        elif kind == "focused":
            status = 400
        elif kind == "full":
            if failure == "validation":
                payload = {"actions": [{"action": context_message}]}
            elif failure == "truncated":
                payload, finish = {"actions": []}, "length"
            else:
                status = {"unauthorized": 401, "forbidden": 403, "rate_limit": 429}.get(failure, 400)
        if status != 200:
            return httpx.Response(status, request=request, json={"error": {"type": "invalid_request_error",
                "message": "Invalid request body" if failure == "unrelated" else context_message}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/impulse-context-errors", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode))
            with pytest.raises(InstructorRetryException):
                await PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig()).decide_actions(_context(store, _persona()))

    asyncio.run(exercise())
    expected = ["pattern", "intent", "full"]
    if failure.startswith("selection_"):
        expected += ["selection", "selection"]
    elif failure == "focused_context":
        expected += ["selection", "focused"]
    assert calls == expected


@pytest.mark.parametrize("kind", ["direct", "wrapped", "earlier_only", "last_only", "small_catalog", "timeout"])
def test_terminal_errors_and_empty_candidate_selection_preserve_the_planned_visit(kind):
    store, intent = fixture()
    store.racks[0].slots[0].items = [SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=100)
                                   for i in range(4 if kind == "small_catalog" else 6)]
    payload = intent.model_dump(mode="json")
    payload["actions"].insert(-1, dict(nav="path", action="buy", product_sku="seen0"))
    context_error = BadRequestError("request (8500 tokens) exceeds the available context size (8192 tokens)",
                                   model="local", llm_provider="openai")
    other = ValueError("invalid response")
    attempts = {"wrapped": [context_error], "earlier_only": [context_error, other], "last_only": [other, context_error]}
    error = InstructorRetryException("failed", n_attempts=len(attempts[kind]), total_usage=0,
        failed_attempts=[FailedAttempt(i + 1, exc) for i, exc in enumerate(attempts[kind])]) if kind in attempts else (
            TimeoutError("offline timeout") if kind == "timeout" else context_error)

    class Model:
        calls = []

        async def generate_structured_async(self, schema, system, user, **kwargs):
            self.calls.append(schema.__name__)
            if "## 행동 패턴 목록" in system:
                return schema.model_validate({"pattern_id": "exploratory"})
            if "## 충동 후보 선택" in system:
                return schema.model_validate({"codes": []})
            if "세렌디피티" in system:
                raise error
            return schema.model_validate(payload)

    model, pathfinder = Model(), AStarPathFinder()
    engine = PatternIntentImpulseEngine(model, pathfinder, SimulationConfig())
    if kind in {"earlier_only", "small_catalog", "timeout"}:
        with pytest.raises(type(error)) as caught:
            asyncio.run(engine.decide_actions(_context(store, _persona())))
        assert caught.value is error and len(model.calls) == 3
    else:
        decision = asyncio.run(engine.decide_actions(_context(store, _persona())))
        assert decision.trace["impulse_catalog_recovery"] == {"selected_codes": [], "selected_skus": []}
        assert model.calls == ["PatternSelectionResponse", "IntentResponse", "ImpulseResponse", "BoundedCatalogSelection"]
        result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, pathfinder, 1)
        assert result.total_spent == 100 and result.purchases[0].origin == "planned"
        assert result.timeline[-1].action == Action.EXIT


@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("with_visibility", [False, True])
def test_compact_candidate_rows_preserve_exact_text_prices_levels_and_visibility(currency, with_visibility):
    store, intent = fixture()
    rack, slot = store.racks[0], store.racks[0].slots[0]
    item = slot.items[0]
    item.name, item.promo = '차 "Leaf"\t500 ml\nFresh', 'Two\tfor "one"\n오늘'
    records = stage2_intent.catalog_records(store)
    code = next(code for code, offer in records.items() if offer is item)
    before = store.model_dump()
    prompt = stage3_impulse.build_user_prompt(_persona(), intent, [(rack, slot, item.sku)],
        store=store, grid_size=store.grid_size, records=records, currency=currency, selection=True,
        visibility={item.sku: .37} if with_visibility else None)
    row = next(line for line in prompt.splitlines() if line.startswith(code + "\t")).split("\t")
    assert row[:4] == [code, json.dumps(item.name, ensure_ascii=False), str(item.price), str(slot.level)]
    assert row[4:] == (["0.37"] if with_visibility else []) + [json.dumps(item.promo, ensure_ascii=False)]
    assert json.loads(row[1]) == item.name and json.loads(row[-1]) == item.promo
    assert "unseen" not in prompt and "접근타일" not in prompt
    assert store.model_dump() == before
