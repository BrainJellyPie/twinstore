"""Experiment drafts retain the actual placements and prices of a repeated product."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import Slot
from store_emulator.domain.types import Face
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import MAX_LISTED, _listing, design_experiment
from store_emulator.engine.prompting import display_price
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("reverse", [False, True])
def test_repeated_sku_preserves_each_offer_and_nonfirst_changes_invalidate_cache(monkeypatch, tmp_path, mode, currency, reverse):
    store, _ = fixture()
    store.currency = currency
    first = store.racks[0]
    first.rack_name = "Ordinary shelf"
    first.slots[0].level = 1
    item = first.slots[0].items[0]
    item.name, item.price = "Tea", 199
    first.slots[0].items.append(item.model_copy())
    first.slots.append(Slot(block=0, face=Face.S, level=2, items=[item.model_copy(update={"price": 299})]))
    other = first.model_copy(deep=True, update={"id": "other", "rack_name": "Promo shelf"})
    other.slots = [other.slots[0]]
    for product in other.slots[0].items:
        product.price = 99
    store.racks = [other, first] if reverse else [first, other]
    calls = []
    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        answer = {"name": "Tea discount", "variants": [{"name": "Discount", "changes": [
            {"kind": "discount", "product": "Tea", "percent": -20}]}], "engine": "rule"}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model="openai/experiment-offers", api_base="http://127.0.0.1:8081/v1",
        api_key="offline", structured_output=mode, cache_dir=str(tmp_path)))
    async def exercise():
        for index, amount in enumerate([299, 399], 1):
            first.slots[1].items[0].price = amount
            before = store.model_dump_json()
            result = await design_experiment(client, "Would a twenty percent tea discount help?", store, currency, [], {item.sku: 10})
            assert await design_experiment(client, "Would a twenty percent tea discount help?", store, currency, [], {item.sku: 10}) == result
            assert len(calls) == index and client.get_usage().cached_requests == index
            user = next(m["content"] for m in calls[-1]["messages"] if m["role"] == "user")
            for price, shelf, level in [(199, "Ordinary shelf", 1), (amount, "Ordinary shelf", 2), (99, "Promo shelf", 1)]:
                assert user.count(f"Tea {display_price(price, currency)} ({shelf}, level {level}") == 1
            assert "10 sold in the last run" in user
            assert "Sales figures are totals per SKU across all shelves" in user
            assert result.variants[0].changes[0].sku == item.sku
            assert store.model_dump_json() == before
    asyncio.run(exercise())


def test_offer_listing_keeps_its_existing_cap_and_query_priority():
    store, _ = fixture()
    base = store.racks[0]
    item = base.slots[0].items[0]
    store.racks = []
    for index in range(190):
        rack = base.model_copy(deep=True, update={"id": f"s{index}", "rack_name": f"Display{index}"})
        product = item.model_copy(update={"sku": f"sku{index}", "name": "Backcorner tea" if index == 189 else f"Other{index}"})
        rack.slots[0].items = [product, product.model_copy()]
        store.racks.append(rack)
    listing = _listing(store, "USD", [], "Change Backcorner tea")
    assert "Backcorner tea" in listing
    assert listing.count(", level ") == MAX_LISTED
