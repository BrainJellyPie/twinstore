"""Shopper searches must receive named products beyond the first 200 catalog entries."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.customer import TimelineEvent
from store_emulator.domain.types import Action
from store_emulator.engine import llm_client
from store_emulator.engine.shopper_filter import _listing, find_shoppers
from tests.engine.test_prompt_catalog_specificity import crowded_store
from tests.engine.test_shopper_filter_boundaries import customer


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["bought_products", "skipped_products"])
@pytest.mark.parametrize("plural", [False, True])
def test_http_search_matches_the_named_late_catalog_product(monkeypatch, tmp_path, mode, field, plural):
    store = crowded_store("teas" if plural else "tea", "Saffron tea")
    customers = {pid: customer(pid, spent=100).model_copy(update={"timeline": [
        TimelineEvent(elapsed_sec=10, x=0, y=0, action=Action.BUY, target_rack="r1", product_sku=sku, price=100)]})
        for pid, sku in [("wanted", "requested"), ("other", "common-0")]}
    customers["empty"] = customer("empty")
    before = [entry.model_dump() for entry in [store, *customers.values()]]
    query = f"Find shoppers who {'bought' if field == 'bought_products' else 'did not buy'} Saffron {'teas' if plural else 'tea'}"
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        user = next(message["content"] for message in body["messages"] if message["role"] == "user")
        listing = user.split("\n\n", 1)[0]
        assert "Saffron tea" in listing and "Everyday" in listing
        products = listing.split("Products: ", 1)[1].split("\n", 1)[0].split("; ")
        assert len(products) == len(set(products)) == 200
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({"label": "Requested shoppers", field: ["Saffron tea"]})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shopper-catalog", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                result = await find_shoppers(client, query, customers, {}, store, "USD")
                assert result.persona_ids == (["wanted"] if field == "bought_products" else ["other", "empty"])
                assert result.criteria == [f"{'Bought' if field == 'bought_products' else 'Did not buy'} Saffron tea"]
                assert result.total == 3 and not result.warnings
                assert [entry.model_dump() for entry in [store, *customers.values()]] == before
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


def test_unnamed_search_shares_catalog_space_between_shelves_without_duplicates():
    store = crowded_store("tea", "Saffron tea")
    second = store.racks[0].model_copy(deep=True, update={"id": "r2", "rack_name": "Cold drinks", "position": (1, 5)})
    second.slots = [second.slots[-1]]
    second.slots[0].items[0].name = "Cold water"
    second.slots[0].items[0].sku = "water"
    second.slots[0].items.append(store.racks[0].slots[0].items[0].model_copy())
    store.racks.append(second)
    listing = _listing(store, "USD")
    assert "Cold water" in listing
    assert listing.count("Everyday tea 0;") == 1
    assert "Shelves: Drinks, Cold drinks" in listing


def test_empty_catalog_keeps_the_currency_and_empty_lists():
    store = crowded_store("tea", "Saffron tea").model_copy(update={"racks": []})
    assert _listing(store, "KRW").startswith("Shelves: \nProducts: \nPrices are in KRW")
