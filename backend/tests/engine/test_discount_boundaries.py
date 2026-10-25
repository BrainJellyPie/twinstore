"""Regular discounts and free offers preserve each placement's reference price."""

import pytest

from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.layout_edit import _EditDraft, apply_layout_edit, to_edit
from store_emulator.engine.online.catalog import site_from_store
from store_emulator.engine.online.store_changes import apply_store_changes


@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("percent", [-10, -100])
def test_regular_discounts_and_free_offers_across_physical_and_online_prices(currency, percent):
    store = Store(id="s", name="Store", type="convenience", currency=currency, grid_size=(8, 8), racks=[
        Rack(id="drinks", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
            Slot(block=0, face="N", level=1, items=[SlotItem(sku="tea", name="Tea", price=400, regular_price=500)]),
            Slot(block=0, face="N", level=2, items=[SlotItem(sku="tea", name="Tea", price=300, regular_price=400)]),
            Slot(block=0, face="N", level=3, items=[SlotItem(sku="water", name="Water", price=100, regular_price=150)])])])
    original = store.model_dump()
    raw = {"name": "Discount", "changes": [{"kind": "discount", "product": "Tea", "percent": percent}]}
    draft = to_edit(_EditDraft.model_validate(raw), store, currency)
    edited, applied, warnings = apply_layout_edit(store, draft.changes, currency)
    tea = [slot.items[0] for slot in edited.racks[0].slots[:2]]
    bases = [500, 400]
    assert [item.price for item in tea] == [round(base * (1 + percent / 100)) for base in bases]
    assert [item.regular_price for item in tea] == [500, 400]
    assert edited.racks[0].slots[2] == store.racks[0].slots[2]
    assert bool(applied) and not warnings and not draft.warnings
    assert VariantChange.model_validate_json(draft.changes[0].model_dump_json()) == draft.changes[0]
    site = site_from_store(store, site_id="web", name="Store", currency=currency)
    products, applied, skipped = apply_store_changes(site, draft.changes, minor_per_major=1 if currency == "KRW" else 100)
    web_tea = next(p for p in products if p.sku == "tea")
    assert web_tea.price == tea[0].price and web_tea.list_price == 500
    assert bool(applied) and not skipped and store.model_dump() == original


def test_legacy_discounts_still_use_the_regular_price_and_over_100_percent_is_rejected():
    change = VariantChange.model_validate({"kind": "discount", "sku": "tea", "percent": -20})
    assert change.percent == -20
    with pytest.raises(ValueError):
        VariantChange(kind="discount", sku="tea", percent=-100.01)
