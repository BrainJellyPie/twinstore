"""Generated facings must behave like the same layout after saving and loading."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.marketing.variants import apply_changes


@pytest.mark.parametrize("template", ["urban_cvs", "hypermarket"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("assortment", [None, 1])
def test_category_price_changes_apply_once_per_facing_before_or_after_save(template, currency, assortment):
    control = generate_store(template, currency=currency, options=LayoutOptions(products_per_category=assortment))
    original = control.model_dump_json()
    reloaded = Store.model_validate_json(original)
    changes = [VariantChange(kind="category_price", category="soft_drinks", percent=10),
               VariantChange(kind="category_price", category="soft_drinks", percent=-25)]
    generated, applied, warnings = apply_changes(control, changes)
    saved, saved_applied, saved_warnings = apply_changes(reloaded, changes)
    assert not warnings and not saved_warnings
    assert applied == saved_applied
    for source_rack, changed_rack in zip(control.racks, generated.racks, strict=True):
        for source_slot, changed_slot in zip(source_rack.slots, changed_rack.slots, strict=True):
            for old, new in zip(source_slot.items, changed_slot.items, strict=True):
                expected = round(round(old.price * 1.1) * 0.75) if source_rack.rack_desc == "soft_drinks" else old.price
                assert new.price == expected, (old.name, old.price, new.price, expected)
                assert new.sku == old.sku
    assert generated == saved
    assert control.model_dump_json() == original
