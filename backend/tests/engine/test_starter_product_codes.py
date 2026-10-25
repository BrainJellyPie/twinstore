"""Short local-model codes must bind to the current catalog, including cached fallback answers."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client, starter_selection
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("fallback", [False, True])
def test_short_codes_preserve_identity_when_only_catalog_skus_change(monkeypatch, tmp_path, mode, currency, fallback):
    category = "home_coffee_tea"
    calls, revisions = [], []
    original = llm_client.litellm.acompletion
    store = empty_store(currency)
    before = store.model_dump()
    racks = [StarterRack(id="section_0", name="Tea (20 racks)", type="shelf", available_slots=4)]

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        context = json.loads(next(message["content"] for message in body["messages"] if message["role"] == "user"))
        if "racks" in context:
            answer = {"groups": [{"category": category, "rack_ids": ["section_0"]}]}
        else:
            products = context["categories"][category]
            codes = [product["sku"] for product in products][:2]
            assert all(code.startswith("@P") and len(code) < 8 for code in codes)
            assert len(set(codes)) == 2
            assert "g_" not in json.dumps(products), "The model need not copy hashed catalog IDs"
            revisions.append(context["catalog_revision"])
            if "Choose products for the ONE supplied category." in body["messages"][0]["content"]:
                answer = {"choices": codes}
            else:
                answer = {"groups": [{"category": category, "skus": ["invented"] if fallback else codes}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/short-codes", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def select():
                return await starter_selection.select_starter_products(client, store, racks, "Tea for local residents",
                    allowed_categories={category}, product_limits={category: 2})

            first = await select()
            skus = [catalog_slot_item(item, currency).sku for item in CATALOG[category]][:2]
            assert first[0].skus == skus
            initial_calls = len(calls)
            assert await select() == first and len(calls) == initial_calls

            def changed_identity(item, currency):
                product = catalog_slot_item(item, currency)
                return product.model_copy(update={"sku": product.sku + "-revision2"})

            monkeypatch.setattr(starter_selection, "catalog_slot_item", changed_identity)
            second = await select()
            assert second[0].skus == [sku + "-revision2" for sku in skus]
            assert len(calls) > initial_calls and len(set(revisions)) == 2
            updated_calls = len(calls)
            assert await select() == second and len(calls) == updated_calls
            assert store.model_dump() == before

    asyncio.run(exercise())
