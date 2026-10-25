"""Real SDK parsing of keyed replies must keep complete rack/product identity and recover invalid maps."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("fault", ["none", "missing_rack", "unknown_rack", "aliased_duplicate_rack", "null_category",
    "unknown_category", "missing_products", "extra_products", "null_products", "wrong_category_sku", "duplicate_sku"])
def test_keyed_replies_recover_without_losing_rows_and_cache_canonical_skus(monkeypatch, tmp_path, mode, fault):
    original, calls = llm_client.litellm.acompletion, []
    counts = {"assignments": 0, "selections": 0}
    racks = [StarterRack(id="Shelf A", name="Milk", type="fridge", available_slots=4),
             StarterRack(id="선반/B", name="Tea", type="shelf", available_slots=4)]
    keys = ["dairy", "home_coffee_tea"]
    store = empty_store("KRW")
    before = store.model_dump()

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        context = json.loads(next(message["content"] for message in body["messages"] if message["role"] == "user"))
        stage = "assignments" if "racks" in context else "selections"
        counts[stage] += 1
        if stage == "assignments":
            value = {rack.id: key for rack, key in zip(racks, keys)}
            if counts[stage] == 1:
                if fault == "missing_rack": value.pop(racks[1].id)
                elif fault == "unknown_rack": value["invented"] = value.pop(racks[1].id)
                elif fault == "aliased_duplicate_rack": value[" SHELF A "] = keys[0]
                elif fault == "null_category": value[racks[0].id] = None
                elif fault == "unknown_category": value[racks[0].id] = "invented"
        else:
            value = {key: [context["categories"][key][0]["sku"]] for key in keys}
            if counts[stage] == 1:
                if fault == "missing_products": value.pop(keys[1])
                elif fault == "extra_products": value["invented"] = value[keys[0]]
                elif fault == "null_products": value[keys[0]] = None
                elif fault == "wrong_category_sku": value[keys[0]] = value[keys[1]]
                elif fault == "duplicate_sku": value[keys[0]] *= 2
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({stage: value})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/keyed-replies", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def select():
                return await select_starter_products(client, store, racks, "동네 주민", allowed_categories=set(keys))

            result = await select()
            assert len(calls) == (2 if fault == "none" else 3)
            assert [(row.rack_id, row.category) for row in result] == [(rack.id, key) for rack, key in zip(racks, keys)]
            assert [row.skus for row in result] == [[catalog_slot_item(CATALOG[key][0], "KRW").sku] for key in keys]
            successful_calls = len(calls)
            assert await select() == result and len(calls) == successful_calls
            assert store.model_dump() == before

    asyncio.run(exercise())
