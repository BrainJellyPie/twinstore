"""Generated SKU identity belongs to the catalog product, across layouts and currencies."""
import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG, localized


def test_all_templates_and_currencies_share_only_identical_catalog_product_skus():
    product_skus = {}
    sku_products = {}
    for currency in ("USD", "KRW", "JPY"):
        catalog = {category: {localized(item, currency): item for item in products}
                   for category, products in CATALOG.items()}
        for template in TEMPLATES:
            store = generate_store(template.id, currency=currency)
            for rack in store.product_racks:
                for slot in rack.slots:
                    for item in slot.items:
                        product = catalog[rack.rack_desc][(item.name, item.price)]
                        assert product_skus.setdefault(product, item.sku) == item.sku
                        assert sku_products.setdefault(item.sku, product) == product


@pytest.mark.parametrize("options", [
    LayoutOptions(excluded_categories=["checkout_impulse"]),
    LayoutOptions(checkout_wall="back"),
    LayoutOptions(width=24, height=20, style="cross", shelf_direction="vertical"),
    LayoutOptions(density="dense", max_shelf_run=8, entrance="right"),
])
def test_changing_layout_options_keeps_each_shared_products_sku(options):
    original = generate_store("urban_cvs")
    revised = generate_store("urban_cvs", options=options)
    before = {(item.name, item.price): item.sku for rack in original.racks for slot in rack.slots for item in slot.items}
    after = {(item.name, item.price): item.sku for rack in revised.racks for slot in rack.slots for item in slot.items}
    shared = before.keys() & after.keys()
    assert shared
    assert all(before[product] == after[product] for product in shared)
