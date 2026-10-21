"""Focused assortments change products without changing fixtures or product identities."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("template_id", [template.id for template in TEMPLATES])
@pytest.mark.parametrize("limit", [1, 4, 8, 16])
def test_each_format_limits_unique_products_per_category_without_moving_fixtures(template_id, limit):
    full = generate_store(template_id, seed=7)
    focused = generate_store(template_id, seed=7, options=LayoutOptions(products_per_category=limit))
    assert [rack.model_dump(exclude={"slots"}) for rack in focused.racks] == [rack.model_dump(exclude={"slots"}) for rack in full.racks]
    assert validate(focused) == []
    original = {item.sku: (item.name, item.price) for rack in full.racks for slot in rack.slots for item in slot.items}
    categories = {rack.rack_desc for rack in focused.product_racks}
    for category in categories:
        items = {item.sku: (item.name, item.price) for rack in focused.product_racks if rack.rack_desc == category
                 for slot in rack.slots for item in slot.items}
        assert len(items) == min(limit, len(CATALOG[category]))
        assert all(original[sku] == product for sku, product in items.items())
    if limit == 16:
        assert focused == full


def test_seeds_choose_reproducible_subsets_independent_of_currency_and_floor_geometry():
    baseline = generate_store("pizzeria", seed=8, options=LayoutOptions(products_per_category=4))
    menu = {item.sku for rack in baseline.product_racks if rack.rack_desc == "pizza_menu"
            for slot in rack.slots for item in slot.items}
    assert baseline == generate_store("pizzeria", seed=8, options=LayoutOptions(products_per_category=4))
    for currency in ("USD", "KRW", "JPY"):
        changed = generate_store("pizzeria", seed=8, currency=currency, options=LayoutOptions(
            products_per_category=4, width=28, height=22, style="cross", shelf_direction="vertical",
            checkout_wall="back", excluded_categories=["desserts"], dining_tables=2))
        assert menu == {item.sku for rack in changed.product_racks if rack.rack_desc == "pizza_menu"
                        for slot in rack.slots for item in slot.items}
        assert not any(rack.rack_desc == "desserts" for rack in changed.product_racks)
        assert validate(changed) == []
    shuffled = generate_store("pizzeria", seed=9, options=LayoutOptions(products_per_category=4))
    assert menu != {item.sku for rack in shuffled.product_racks if rack.rack_desc == "pizza_menu"
                    for slot in rack.slots for item in slot.items}
