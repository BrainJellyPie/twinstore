"""Model-written everyday prices must not inherit A/B-test reference prices."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine import llm_client
from store_emulator.engine.layout_edit import apply_layout_edit, draft_layout_edit
from store_emulator.engine.marketing.experiment_design import design_experiment
from store_emulator.engine.marketing.variants import apply_changes


def store_with_prices(reference):
    return Store(id="s", name="Store", type="convenience", grid_size=(8, 8), racks=[
        Rack(id="tea", rack_name="Tea shelf", rack_desc="Tea", type="shelf", shape=[[1]], position=(3, 3), slots=[
            Slot(block=0, face="N", level=level, items=[
                SlotItem(sku="tea", name="Tea", price=199, regular_price=reference, promo="LOCAL"),
                SlotItem(sku="water", name="Water", price=99, regular_price=129),
            ]) for level in (1, 2)])])


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("reference", [0, 399])
@pytest.mark.parametrize("sequence", ["lower", "higher", "same", "price_discount", "discount_price", "category"])
def test_model_price_edits_apply_the_requested_basis_and_preview(monkeypatch, tmp_path, mode, currency, reference, sequence):
    store = store_with_prices(reference)
    before = store.model_dump_json()
    amount = {"higher": 349, "same": 199}.get(sequence, 149)
    price = {"kind": "price", "product": "Tea", "price": amount / (100 if currency == "USD" else 1)}
    discount = {"kind": "discount", "product": "Tea", "percent": -10}
    steps = ([price, discount] if sequence == "price_discount" else
             [discount, price] if sequence == "discount_price" else
             [{"kind": "category_price", "category": "Tea shelf", "percent": -10}] if sequence == "category" else [price])
    payload = {"name": "New everyday prices", "changes": steps}
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/layout-everyday-prices",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))

            async def draft():
                return await draft_layout_edit(client, "Set the new everyday price, then any requested discount", store, currency)

            result = await draft()
            edited, applied, warnings = apply_layout_edit(store, result.changes, currency)
            expected_price = 134 if sequence == "price_discount" else 179 if sequence == "category" else amount
            expected_reference = 149 if sequence == "price_discount" else 0
            tea = [i for r in edited.racks for s in r.slots for i in s.items if i.sku == "tea"]
            assert len(tea) == 2
            assert [(i.price, i.regular_price, i.promo) for i in tea] == [(expected_price, expected_reference, "LOCAL")] * 2
            water = [i for r in edited.racks for s in r.slots for i in s.items if i.sku == "water"]
            assert [(i.price, i.regular_price) for i in water] == ([(89, 0)] * 2 if sequence == "category" else [(99, 129)] * 2)
            assert all(not c.keep_reference for c in result.changes if c.kind == "price")
            assert result.applied == applied and "remember" not in " ".join(applied)
            assert not warnings and not result.warnings
            assert await draft() == result and len(calls) == 1 and client.get_usage().cached_requests == 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("reference", [0, 399])
def test_explicit_manual_reference_and_discounts_are_preserved(reference):
    store = store_with_prices(reference)
    for kind, changes, expected in [
        ("remember", [VariantChange(kind="price", sku="tea", price=149, keep_reference=True)], (149, reference or 199)),
        ("discount", [VariantChange(kind="discount", sku="tea", percent=-10)], (round((reference or 199) * .9), reference or 199)),
    ]:
        edited, applied, warnings = apply_layout_edit(store, changes, "USD")
        item = edited.racks[0].slots[0].items[0]
        assert (item.price, item.regular_price) == expected, kind
        assert applied and not warnings


@pytest.mark.parametrize("reference", [0, 399])
def test_model_written_ab_prices_still_remember_the_control(reference):
    class Model:
        async def generate_structured_async(self, response_model, *args, **kwargs):
            return response_model.model_validate({"name": "Test", "variants": [{"name": "Price", "changes": [
                {"kind": "price", "product": "Tea", "price": 1.49}]}]})

    store = store_with_prices(reference)
    result = asyncio.run(design_experiment(Model(), "Test the price cut", store, "USD", []))
    changes = result.variants[0].changes
    assert changes[0].keep_reference
    tested, applied, warnings = apply_changes(store, changes)
    item = tested.racks[0].slots[0].items[0]
    assert (item.price, item.regular_price) == (149, reference or 199)
    assert "remember" in " ".join(applied) and not warnings
