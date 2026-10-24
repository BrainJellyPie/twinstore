"""A local model's compact offer reference must retain its exact shelf price."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ConfigDict, create_model

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.rack import BlockFace, Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _persona


def offers(placement, reverse=False):
    low = Slot(block=0, face=Face.N, level=1, items=[SlotItem(sku="tea", name="Tea", price=100)])
    high = Slot(block=1 if placement == "block" else 0, face=Face.N, level=4 if placement == "level" else 1,
                items=[SlotItem(sku="tea", name="Selected tea", price=700, promo="Selected sign")])
    first = Rack(id="first", type="shelf", position=(3, 2), shape=[[1, 1]], slots=[low])
    if placement == "rack":
        products = [first, Rack(id="selected", type="shelf", position=(6, 2), shape=[[1]], slots=[high])]
    else:
        first.slots.append(high)
        products = [first]
    if reverse:
        products.reverse()
        for rack in products:
            rack.slots.reverse()
    return Store(id="offers", name="Offers", type="shop", grid_size=(10, 10), racks=[*products,
        Rack(id="in", type="entrance", position=(0, 0), shape=[[1]]),
        Rack(id="out", type="exit", position=(9, 0), shape=[[1]]),
        Rack(id="till", type="counter", position=(8, 4), shape=[[1]])])


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("placement", ["level", "block", "rack"])
@pytest.mark.parametrize("reverse", [False, True])
def test_selected_offer_survives_http_cache_route_and_checkout(monkeypatch, tmp_path, mode, ordering, placement, reverse):
    store = offers(placement, reverse)
    before = store.model_dump()
    code = next(code for code, item in stage2_intent.catalog_records(store).items() if item.price == 700)
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            answer = {"pattern_id": "exploratory"}
        elif len(calls) == 2:
            answer = {"actions": [
                {"action": "buy", "nav": "path", "product_sku": code, "quantity": 2,
                 "target": [3, 1], "face": "N", "product_block": 0, "product_level": 1},
                {"action": "pay", "nav": "path"}, {"action": "exit", "nav": "leave"}]}
        else:
            assert len(calls) == 3
            answer = {"actions": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/catalog-offers", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig(route_ordering=ordering,
                                                                                          budget_tolerance=None))
            decision = await engine.decide_actions(_context(store, _persona()))
            assert await engine.decide_actions(_context(store, _persona())) == decision and len(calls) == 3
            assert next(a for a in decision.actions if a.action == Action.BUY).product_sku == "tea"
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
            assert result.total_spent == 1400
            assert len(result.purchases) == 1 and result.purchases[0].price == 700
            assert result.purchases[0].product_name == "Selected tea" and result.purchases[0].quantity == 2
            assert sum(event.action == Action.PAY for event in result.timeline) == 1
            assert result.timeline[-1].action == Action.EXIT
            actual, report = resolve_shared_store(store, [result], OperationsConfig(
                stock_overrides={"tea": 0}, restock_every_min=None, substitute_share=0), seed=1)
            assert actual[0].total_spent == 0 and report.lost_units == 2 and report.lost_revenue == 1400

    asyncio.run(exercise())
    assert store.model_dump() == before


@pytest.mark.parametrize("placement", ["level", "block", "rack"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("budget", [500, 1400, 0])
def test_impulse_budget_uses_the_selected_offer_not_another_price(placement, ordering, budget):
    store = offers(placement, reverse=True)  # The selected offer is the SKU's first exposed placement.
    code = next(code for code, item in stage2_intent.catalog_records(store).items() if item.price == 700)

    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if "## 행동 패턴 목록" in system:
                return schema(pattern_id="exploratory")
            if "세렌디피티" in system:
                assert code + ": Selected tea" in prompt
                return schema.model_validate({"actions": [{"nav": "path", "action": "buy", "product_sku": code,
                    "quantity": 2, "target": [3, 1], "face": "N", "product_level": 1}]})
            return schema.model_validate({"actions": [{"nav": "path", "action": "browse", "target": [6, 1], "face": "N"},
                {"nav": "path", "action": "browse", "target": [3, 1], "face": "N"}, {"nav": "leave", "action": "exit"}]})

    engine = PatternIntentImpulseEngine(Model(), AStarPathFinder(), SimulationConfig(route_ordering=ordering, budget_tolerance=1))
    decision = asyncio.run(engine.decide_actions(_context(store, _persona(budget))))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert result.total_spent == (0 if budget == 500 else 1400)
    assert decision.dropped_over_budget == (1 if budget == 500 else 0)
    assert sum(e.action == Action.PAY for e in result.timeline) == (0 if budget == 500 else 1)
    if result.purchases:
        assert result.purchases[0].origin == "impulse" and result.purchases[0].product_name == "Selected tea"


@pytest.mark.parametrize("unavailable", ["locked", "blocked", "off_grid", "duplicate_in_slot"])
def test_an_unavailable_selected_offer_never_falls_back_to_a_different_price(unavailable):
    store = offers("rack")
    selected = store.racks[1]
    if unavailable == "locked":
        selected.locked_faces = [BlockFace(block=0, face=Face.N)]
    elif unavailable == "blocked":
        store.racks.append(Rack(id="wall", type="shelf", position=(6, 1), shape=[[1]]))
    elif unavailable == "off_grid":
        selected.position = (6, 0)
    else:
        selected.slots[0].items.insert(0, store.racks[0].slots[0].items[0].model_copy())
    records = stage2_intent.catalog_records(store)
    code = next(code for code, item in records.items() if item.price == 700)
    schema = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records)
    response = schema.model_validate({"actions": [{"nav": "path", "action": "buy", "product_sku": code}]})
    decoded = stage2_intent.decode_catalog_response(stage2_intent.IntentResponse, response, records, store)
    from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import drop_invalid_buys
    actions, dropped = drop_invalid_buys(decoded.actions, store)
    assert actions == [] and dropped == 1


def test_identical_repeated_offers_honor_the_existing_target_and_strip_injected_hints():
    store = offers("rack")
    store.racks[1].slots[0].items = [store.racks[0].slots[0].items[0].model_copy()]
    records = stage2_intent.catalog_records(store)
    assert list(records) == ["@P1"]
    schema = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records)
    response = schema.model_validate({"actions": [{"nav": "path", "action": "buy", "product_sku": "@P1",
        "target": [6, 1], "face": "N", "product_block": 90, "product_level": 4}]})
    decoded = stage2_intent.decode_catalog_response(stage2_intent.IntentResponse, response, records, store)
    action = decoded.actions[0]
    assert (action.target, action.face, action.product_block, action.product_level) == ((6, 1), Face.N, 0, 1)
    assert response.actions[0].product_sku == "@P1" and response.actions[0].product_block is None


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_old_cache_without_offer_identity_is_bypassed(monkeypatch, tmp_path, mode):
    store = offers("level")
    records = stage2_intent.catalog_records(store)
    schema = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records)
    old_comment = schema.model_json_schema()["$comment"].replace("catalog-offer-codes-v2:", "catalog-sku-map:")
    legacy = create_model("IntentResponse", __base__=schema, __config__=ConfigDict(json_schema_extra={"$comment": old_comment}))
    assert legacy.model_json_schema() == {**schema.model_json_schema(), "$comment": old_comment}
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"actions":[{"nav":"path","action":"buy","product_sku":"@P2"}]}'}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/catalog-offers", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            messages, _ = client._messages("Choose", "Buy @P2")
            old = client._cache_path(legacy, messages, None)
            old.parent.mkdir(parents=True)
            old.write_text(json.dumps({"result": {"actions": [{"nav": "path", "action": "buy", "product_sku": "tea"}]}}))
            first = await client.generate_structured_async(schema, "Choose", "Buy @P2")
            second = await client.generate_structured_async(schema, "Choose", "Buy @P2")
            assert first.model_dump() == second.model_dump() and first.actions[0].product_sku == "@P2"
            decoded = stage2_intent.decode_catalog_response(stage2_intent.IntentResponse, second, records, store)
            assert decoded.actions[0].product_level == 4 and old.exists() and len(calls) == 1

    asyncio.run(exercise())
