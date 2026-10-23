"""A captured run of facings must behave like the same layout after JSON storage."""

import pytest

from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.product_edits import ProductEdit
from store_emulator.domain.store import Store
from store_emulator.engine.marketing.variants import apply_changes
from store_emulator.engine.product_edits import apply_product_edits
from store_emulator.engine.shelf_lab.sim2real import twin_rack


def captured(facings):
    result = CaptureResult(image_size=(200, 200), dominant_category="soft_drinks", items=[CaptureItem(
        id="tea", band=0, level=1, order=0, sku="tea", name="Tea", price=100, facings=facings,
    )])
    rack, _ = twin_rack(result)
    return Store(id="capture", name="Capture", type="convenience", grid_size=(12, 12), racks=[rack])


def items(store):
    return [item for rack in store.racks for slot in rack.slots for item in slot.items]


@pytest.mark.parametrize("facings", [1, 2, 3, 4, 5, 7, 16, 33, 100])
@pytest.mark.parametrize("percent", [-50, -10, 10, 50])
def test_category_price_changes_apply_once_per_captured_facing(facings, percent):
    original = captured(facings)
    before = original.model_dump_json()
    change = VariantChange(kind="category_price", category="soft_drinks", percent=percent)
    updated, applied, warnings = apply_changes(original, [change])
    saved, _, _ = apply_changes(Store.model_validate_json(before), [change])
    assert applied and not warnings
    assert len(items(updated)) == min(facings, 32)
    assert all(item.price == 100 + percent and item.regular_price == 100 for item in items(updated))
    assert updated.model_dump() == saved.model_dump()
    assert original.model_dump_json() == before


@pytest.mark.parametrize("facings", [2, 3, 4, 5, 16, 32])
def test_editing_one_captured_facing_does_not_change_others(facings):
    layout = captured(facings)
    placed = items(layout)
    placed[-1].price = 700
    placed[-1].promo = "Only this facing"
    assert all(item.price == 100 and item.promo == "" for item in placed[:-1])
    assert placed[-1].price == 700


@pytest.mark.parametrize("facings", [1, 2, 4, 5, 32])
def test_bulk_product_edit_counts_every_captured_placement(facings):
    layout = captured(facings)
    updated, preview = apply_product_edits(layout, [ProductEdit(sku="tea", price=700)])
    assert preview.changed_placements == facings
    assert all(item.price == 700 for item in items(updated))
    assert all(item.price == 100 for item in items(layout))
