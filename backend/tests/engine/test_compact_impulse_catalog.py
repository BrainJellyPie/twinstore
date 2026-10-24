"""Compact impulse prompts retain exposure order, offer metadata and real purchases."""

import asyncio
import json
import re

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.prompting import format_price
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent, stage3_impulse
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("exposure", ["adjacency", "visibility"])
@pytest.mark.parametrize("sku", ["opaque_0123456789abcdef0123456789abcdef", "@P1"])
def test_impulse_reference_decodes_after_cache_before_trace_and_purchase(monkeypatch, tmp_path, mode, ordering, exposure, sku):
    store, intent = fixture()
    store.racks[0].slots[0].items[0].sku = sku
    store.racks[0].slots[0].items[0].name = "Visible tea"
    before = store.model_dump()
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            answer = {"pattern_id": "exploratory"}
        elif len(calls) == 2:
            answer = intent.model_dump(mode="json")
        else:
            assert len(calls) == 3
            user = body["messages"][1]["content"]
            found = re.search(r"(@+P\d+): Visible tea ", user)
            assert found is not None
            code = found.group(1)
            assert code != sku and f"({sku})" not in user and "unseen" not in user
            if mode == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                action = schema["$defs"][schema["properties"]["actions"]["items"]["$ref"].rsplit("/", 1)[-1]]
                assert action["properties"]["product_sku"]["enum"] == ["", code]
            answer = {"actions": [{"action": "buy", "nav": "path", "product_sku": code, "quantity": 2,
                "target": [2, 2], "face": "S"}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/compact-impulse", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig(route_ordering=ordering,
                exposure_model=exposure, budget_tolerance=None))
            first = await engine.decide_actions(_context(store, _persona()))
            second = await engine.decide_actions(_context(store, _persona()))
            assert first == second and client.get_usage().cached_requests == 3
            assert first.trace["stage3"]["actions"][0]["product_sku"] == sku
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", first, AStarPathFinder(), 1)
            assert result.total_spent == 200 and result.purchases[0].product_sku == sku
            assert result.purchases[0].origin == "impulse" and result.purchases[0].quantity == 2
            assert result.timeline[-1].action == Action.EXIT
            assert sum(e.action == Action.PAY for e in result.timeline) == 1

    asyncio.run(exercise())
    assert len(calls) == 3 and store.model_dump() == before


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("concurrent", [False, True])
def test_identical_visible_stores_do_not_share_decoded_impulse_purchases(monkeypatch, tmp_path, mode, concurrent):
    stores = []
    for sku in ["opaque-first", "opaque-second"]:
        store, intent = fixture()
        store.racks[0].slots[0].items[0].sku = sku
        stores.append(store)
    original = llm_client.litellm.acompletion
    calls = []
    impulse_prompts = []

    async def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        await asyncio.sleep(0)
        system = body["messages"][0]["content"]
        if "## 행동 패턴 목록" in system:
            answer = {"pattern_id": "exploratory"}
        elif "세렌디피티" in system:
            impulse_prompts.append(body["messages"][1]["content"])
            answer = {"actions": [{"action": "buy", "nav": "path", "product_sku": "@P1",
                "target": [2, 2], "face": "S"}]}
        else:
            answer = intent.model_dump(mode="json")
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/impulse-cache", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            engine = PatternIntentImpulseEngine(client, AStarPathFinder(), SimulationConfig())
            contexts = [_context(store, _persona()) for store in stores]
            if concurrent:
                first = await asyncio.gather(*(engine.decide_actions(context) for context in contexts))
            else:
                first = [await engine.decide_actions(context) for context in contexts]
            before = len(calls), client.get_usage().cached_requests
            second = [await engine.decide_actions(context) for context in contexts]
            assert first == second
            assert len(calls) == before[0] and client.get_usage().cached_requests == before[1] + 6
            assert [next(a.product_sku for a in d.actions if a.action == Action.BUY) for d in first] == ["opaque-first", "opaque-second"]
            assert len(impulse_prompts) == 2 and impulse_prompts[0] == impulse_prompts[1]

    asyncio.run(exercise())


@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("with_visibility", [False, True])
def test_compact_table_preserves_offer_metadata_and_exposure_order(collision_store, currency, with_visibility):
    first, second = collision_store.racks[:2]
    first.rack_decoration_desc = "Distinct shelf promotion"
    item = first.slots[0].items[0]
    item.promo = "Two for one"
    variant = first.slots[0].model_copy(deep=True, update={"level": 4})
    variant.items[0].name = "Premium tea"
    variant.items[0].price = 900
    first.slots.append(variant)
    exposed = [(first, first.slots[0], item.sku), (second, second.slots[0], second.slots[0].items[0].sku),
               (first, variant, item.sku)]
    records = stage2_intent.catalog_records(collision_store)
    visibility = {item.sku: 0.83, second.slots[0].items[0].sku: 0.41} if with_visibility else None
    before = collision_store.model_dump()
    prompt = stage3_impulse.build_user_prompt(_persona(), stage2_intent.IntentResponse(), exposed,
        grid_size=collision_store.grid_size, visibility=visibility, currency=currency, records=records)
    assert prompt.count("Distinct shelf promotion") == 1
    assert prompt.count("  R1:") == prompt.count("  R2:") == 1
    positions = []
    for rack, slot, sku in exposed:
        offer = next(i for i in slot.items if i.sku == sku)
        code = next(code for code, value in records.items() if value is offer)
        positions.append(prompt.index(f"{code}: {offer.name} {format_price(offer.price, currency)}"))
        assert f"level={slot.level}" in prompt
        if visibility is not None:
            assert f"시인성={visibility[sku]:.2f}" in prompt
        assert str(sorted(rack.access_tiles(collision_store.grid_size))[:3]) in prompt
    assert positions == sorted(positions) and "Two for one" in prompt
    assert collision_store.model_dump() == before
