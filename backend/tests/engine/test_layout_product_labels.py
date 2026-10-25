"""Copied display labels resolve only when the actual store identifies one SKU."""

import pytest

from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.layout_edit import _EditDraft, apply_layout_edit, to_edit


def _store():
    return Store(id="s", name="Store", type="convenience", grid_size=(8, 8), racks=[
        Rack(id="drinks", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
            Slot(block=0, face="N", level=1, items=[SlotItem(sku="tea", name="Green Tea", price=5000)])])])


@pytest.mark.parametrize("label", ["Green Tea", "Green Tea 5,000원", "Green Tea 5,000원 (Drinks, level 1)"])
def test_exact_product_or_display_label_edits_the_same_product(label):
    store = _store()
    draft = to_edit(_EditDraft.model_validate({"name": "Price", "changes": [
        {"kind": "price", "product": label, "price": 3000}]}), store, "KRW")
    edited, _, warnings = apply_layout_edit(store, draft.changes, "KRW")
    assert edited.racks[0].slots[0].items[0].price == 3000 and not warnings
    assert store.racks[0].slots[0].items[0].price == 5000


@pytest.mark.parametrize("label", ["Green Tea 4,000원", "Green Tea 5,000원 (Snacks, level 1)",
                                   "Green Tea 5,000원 (Drinks, level 2)", "Green Tea and Water"])
def test_invented_prices_locations_or_combined_names_are_not_stripped(label):
    with pytest.raises(ValueError, match="no unique product"):
        to_edit(_EditDraft.model_validate({"name": "Price", "changes": [
            {"kind": "price", "product": label, "price": 3000}]}), _store(), "KRW")


def test_display_label_that_is_also_another_products_name_remains_ambiguous():
    store = _store()
    store.racks[0].slots[0].items.append(SlotItem(sku="other", name="Green Tea 5,000원", price=2000))
    with pytest.raises(ValueError, match="no unique product"):
        to_edit(_EditDraft.model_validate({"name": "Price", "changes": [
            {"kind": "price", "product": "Green Tea 5,000원", "price": 3000}]}), store, "KRW")
