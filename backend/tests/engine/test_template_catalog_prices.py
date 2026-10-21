"""Generated products retain their catalog identity even when display names coincide."""
import pytest

from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG, localized


@pytest.mark.parametrize("template_id", [template.id for template in TEMPLATES])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_generated_prices_match_the_display_category_catalog(template_id, currency):
    store = generate_store(template_id, currency=currency)
    for rack in store.product_racks:
        expected = dict(localized(item, currency) for item in CATALOG[rack.rack_desc])
        for slot in rack.slots:
            for item in slot.items:
                assert item.price == expected[item.name], (template_id, currency, rack.rack_desc, item.name)


@pytest.mark.parametrize("template_id", ["food_hall", "community_pharmacy", "artisan_bakery"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_repeated_facings_keep_the_same_sku_for_the_same_product(template_id, currency):
    store = generate_store(template_id, currency=currency)
    identities = {}
    appearances = 0
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                appearances += 1
                identity = (item.name, item.price)
                assert identities.setdefault(identity, item.sku) == item.sku
    assert appearances > len(identities)
    assert len(set(identities.values())) == len(identities)


@pytest.mark.parametrize("currency,prices", [("USD", {449, 899}), ("JPY", {670, 1350})])
def test_distinct_garden_salads_do_not_share_a_sku_or_overwrite_each_others_price(currency, prices):
    store = generate_store("food_hall", currency=currency)
    salads = {(item.sku, item.price) for rack in store.product_racks for slot in rack.slots
              for item in slot.items if item.name == "Garden Salad"}
    assert {price for _, price in salads} == prices
    assert len({sku for sku, _ in salads}) == 2
