"""Compact model references must retain canonical SKUs, offers and cache identity."""

import asyncio
import json
import re

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from tests.engine.test_llm_engine_offline import _context, _intent, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("sku", ["g_0123456789abcdef0123456789abcdef", "@P1", "상품/코드\"🛒"])
def test_http_catalog_references_restore_real_skus_before_execution_after_cache(monkeypatch, tmp_path, collision_store, mode, ordering, sku):
    collision_store.racks[0].slots[0].items[0].sku = sku
    original_store = collision_store.model_dump()
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            answer = {"pattern_id": "exploratory"}
        elif len(calls) == 2:
            system = body["messages"][0]["content"]
            ref = re.search(r"^\s*(@+P\d+): A item ", system, re.MULTILINE)
            assert ref is not None
            code = ref.group(1)
            assert code != sku  # A real SKU that resembles a reference cannot be reinterpreted.
            if mode == "json_schema":
                data = body["response_format"]["json_schema"]["schema"]
                variants = data["$defs"][data["properties"]["actions"]["items"]["$ref"].rsplit("/", 1)[-1]]["anyOf"]
                action = next(row["properties"] for row in variants if row["properties"]["action"]["const"] == "buy")
                assert code in action["product_sku"]["enum"] and "" not in action["product_sku"]["enum"]
                assert "product_level" not in action
            answer = _intent().model_dump(mode="json")
            answer["actions"][2]["product_sku"] = code
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/compact-catalog", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig(route_ordering=ordering))
            first = await engine.decide_actions(_context(collision_store, _persona()))
            second = await engine.decide_actions(_context(collision_store, _persona()))
            assert first == second and client.get_usage().cached_requests == 3
            assert next(a for a in first.actions if a.action == Action.BUY).product_sku == sku
            result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", first, AStarPathFinder(), 1)
            assert result.total_spent == 300 and result.purchases[0].product_sku == sku
            assert result.timeline[-1].action == Action.EXIT

    asyncio.run(exercise())
    assert len(calls) == 3 and collision_store.model_dump() == original_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("concurrent", [False, True])
def test_identical_visible_catalogs_keep_distinct_sku_mappings_in_cache_and_concurrent_calls(monkeypatch, tmp_path, collision_store, mode, concurrent):
    original = llm_client.litellm.acompletion
    calls = []
    stores, schemas, prompts = [], [], []
    expected = [f"opaque-original-{i}" for i in range(6)]
    for sku in expected:
        store = collision_store.model_copy(deep=True)
        store.racks[0].slots[0].items[0].sku = sku
        records = stage2_intent.catalog_records(store)
        stores.append(store)
        schemas.append(stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records))
        prompts.append(stage2_intent.build_system_prompt(store, records=records))
    assert len(set(prompts)) == 1
    assert len({schema.model_json_schema()["$comment"] for schema in schemas}) == len(expected)

    async def respond(request):
        calls.append(json.loads(request.content))
        await asyncio.sleep(0)
        answer = {"actions": [{"nav": "path", "action": "buy", "product_sku": "@P1",
                                "target": [1, 0], "face": "E", "quantity": 3}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/catalog-cache", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def request(index):
                raw = await client.generate_structured_async(schemas[index], prompts[index], "Buy A item")
                return stage2_intent.decode_catalog_response(stage2_intent.IntentResponse, raw,
                    stage2_intent.catalog_records(stores[index]), stores[index])

            if concurrent:
                first = await asyncio.gather(*(request(i) for i in range(6)))
            else:
                first = [await request(i) for i in range(6)]
            second = [await request(i) for i in range(6)]
            assert [reply.actions[0].product_sku for reply in first] == expected
            assert [reply.model_dump() for reply in first] == [reply.model_dump() for reply in second]
            assert len(calls) == client.get_usage().cached_requests == 6
            saved = [json.loads(path.read_text())["result"]["actions"][0]["product_sku"] for path in tmp_path.glob("*/*.json")]
            assert saved == ["@P1"] * len(expected)  # Cache preserves the selected offer; mapping stays request-local.

    asyncio.run(exercise())


def test_offer_table_keeps_price_name_promotion_and_every_repeated_placement(collision_store):
    from store_emulator.domain.rack import Slot

    rack = collision_store.racks[0]
    rack.shape = [[1], [1]]
    original = rack.slots[0]
    item = original.items[0]
    rack.slots.extend([
        original.model_copy(deep=True, update={"level": 2}),
        Slot(block=0, face=original.face, level=3, items=[item.model_copy(update={"price": 900})]),
        Slot(block=0, face=original.face, level=4, items=[item.model_copy(update={"promo": "Two for one"})]),
        Slot(block=1, face=original.face, level=1, items=[item.model_copy(update={"name": "Alternative label"})]),
    ])
    before = collision_store.model_dump()
    records = stage2_intent.catalog_records(collision_store)
    assert len(records) == 5  # Four distinct offers of A, plus B; repeated A shares a record.
    prompt = stage2_intent.build_system_prompt(collision_store, records=records)
    assert "b0/E L1, b0/E L2: @P1" in prompt
    assert "b0/E L3: @P2" in prompt and "b0/E L4: @P3" in prompt and "b1/E L1: @P4" in prompt
    assert "Two for one" in prompt and "Alternative label" in prompt and "900¢" in prompt
    schema = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records)
    response = schema.model_validate_json(json.dumps({"actions": [
        {"nav": "path", "action": "buy", "product_sku": code, "target": [1, 0], "face": "E"} for code in records]}), strict=True)
    assert [action.product_sku for action in response.actions] == list(records)
    decoded = stage2_intent.decode_catalog_response(stage2_intent.IntentResponse, response, records, collision_store)
    assert [action.product_sku for action in decoded.actions] == [item.sku for item in records.values()]
    assert collision_store.model_dump() == before


def test_empty_catalog_has_a_valid_empty_reference_grammar(collision_store):
    for rack in collision_store.racks:
        rack.slots = []
    records = stage2_intent.catalog_records(collision_store)
    assert records == {}
    schema = stage2_intent.catalog_response_model(stage2_intent.IntentResponse, records)
    reply = schema.model_validate_json('{"actions":[{"nav":"leave","action":"exit"}]}', strict=True)
    assert reply.actions[0].product_sku == ""
    assert "@P1:" not in stage2_intent.build_system_prompt(collision_store, records=records)
