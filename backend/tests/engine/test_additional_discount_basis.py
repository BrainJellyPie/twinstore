"""Additional discounts use each selling price while retaining the original reference."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.layout_edit import apply_layout_edit, draft_layout_edit
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import design_experiment
from store_emulator.engine.marketing.variants import apply_changes
from store_emulator.engine.online.catalog import site_from_store
from store_emulator.engine.online.store_changes import apply_store_changes


def fixture(currency="USD", prices=(400, 300, 0), regular=500):
    return Store(id="s", name="Shop", type="convenience", currency=currency, grid_size=(8, 8), racks=[
        Rack(id="drinks", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
            *[Slot(block=0, face="N", level=index + 1,
                items=[SlotItem(sku="tea", name="Tea", price=price, regular_price=regular)])
                for index, price in enumerate(prices)],
            Slot(block=0, face="N", level=4, items=[SlotItem(sku="water", name="Water", price=99)])])])


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("basis,percent,expected", [
    ("current", -10, [360, 270, 0]), ("current", -100, [0, 0, 0]),
    ("regular", -10, [450, 450, 450]), (None, -10, [450, 450, 450]),
])
def test_each_placement_and_online_offer_uses_the_selected_basis(currency, basis, percent, expected):
    data = {"kind": "discount", "sku": "tea", "percent": percent}
    if basis is not None:
        data["discount_basis"] = basis
    change = VariantChange.model_validate(data)
    change = VariantChange.model_validate_json(change.model_dump_json())
    store = fixture(currency)
    before = store.model_dump_json()
    physical, applied, warnings = apply_changes(store, [change])
    items = [item for rack in physical.racks for slot in rack.slots for item in slot.items]
    assert [item.price for item in items if item.sku == "tea"] == expected
    assert all(item.regular_price == 500 for item in items if item.sku == "tea")
    assert next(item for item in items if item.sku == "water").price == 99
    assert applied and not warnings and store.model_dump_json() == before
    # A web catalog has one price per SKU. Check each physical offer separately.
    for price, wanted in zip((400, 300, 0), expected):
        site = site_from_store(fixture(currency, (price,)), site_id="web", name="Web", currency=currency)
        original = site.model_dump_json()
        products, applied, skipped = apply_store_changes(site, [change], minor_per_major=100 if currency == "USD" else 1)
        tea = next(product for product in products if product.sku == "tea")
        assert (tea.price, tea.list_price) == (wanted, 500)
        assert applied and not skipped and site.model_dump_json() == original


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("price,regular,basis,percent,expected", [
    (81, 101, "regular", -50, 50), (81, 101, "current", -50, 40),
    (83, 103, "regular", -50, 52), (83, 103, "current", -50, 42),
    (81, 101, "current", -37.5, 51), (81, 101, "regular", -100, 0),
    (0, 101, "current", -50, 0), (1, 0, "regular", -50, 0),
])
def test_discount_minor_unit_rounding_agrees_in_physical_and_online_stores(currency, price, regular, basis, percent, expected):
    store = fixture(currency, (price,), regular)
    change = VariantChange(kind="discount", sku="tea", percent=percent, discount_basis=basis)
    physical, _, warnings = apply_changes(store, [change])
    assert not warnings
    assert physical.racks[0].slots[0].items[0].price == expected
    site = site_from_store(store, site_id="web", name="Web", currency=currency)
    products, _, skipped = apply_store_changes(site, [change], minor_per_major=100 if currency == "USD" else 1)
    assert not skipped
    assert next(product for product in products if product.sku == "tea").price == expected
    assert store.racks[0].slots[0].items[0].price == price


def test_current_basis_without_a_reference_starts_one_and_keeps_it_across_sequential_cuts():
    store = fixture(prices=(400,), regular=0)
    change = VariantChange(kind="discount", sku="tea", percent=-10, discount_basis="current")
    edited, _, warnings = apply_layout_edit(store, [change, change], "USD")
    tea = edited.racks[0].slots[0].items[0]
    assert (tea.price, tea.regular_price) == (324, 400) and not warnings
    assert store.racks[0].slots[0].items[0].price == 400


@pytest.mark.parametrize("kind", ["layout", "experiment"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_model_basis_survives_resolution_cache_and_real_price_application(monkeypatch, tmp_path, kind, mode):
    store = fixture()
    before = store.model_dump_json()
    calls = []
    change = {"kind": "discount", "product": "Tea", "percent": -10, "discount_basis": "current"}
    payload = {"name": "Extra tea discount", **({"changes": [change]} if kind == "layout" else {
        "variants": [{"name": "Extra", "changes": [change]}]})}

    async def send(self, request, *args, **kwargs):
        calls.append(json.loads(request.content))
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion",
            "created": 0, "model": "local", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    client = LiteLLMClient(LLMConfig(model="openai/discount-basis", api_base="http://127.0.0.1:8081/v1",
        api_key="offline", structured_output=mode, cache_dir=str(tmp_path), seed=0))

    async def ask():
        if kind == "layout":
            return await draft_layout_edit(client, "Take an additional 10 percent off Tea", store, "USD")
        return await design_experiment(client, "Test an additional 10 percent off Tea", store, "USD", [])

    async def exercise():
        result = await ask()
        assert await ask() == result
        changes = result.changes if kind == "layout" else result.variants[0].changes
        edited, _, warnings = apply_layout_edit(store, changes, "USD")
        assert not warnings
        assert [slot.items[0].price for slot in edited.racks[0].slots[:3]] == [360, 270, 0]

    asyncio.run(exercise())
    assert len(calls) == 1 and client.get_usage().cached_requests == 1
    assert store.model_dump_json() == before
