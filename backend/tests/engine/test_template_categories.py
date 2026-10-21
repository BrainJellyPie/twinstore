"""Assortment exclusions cover every fixture zone without changing shared defaults."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG, localized
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_exclusions_remove_cold_wall_island_and_checkout_products(currency):
    excluded = ["beer_alcohol", "ice_cream", "household", "chips", "checkout_impulse"]
    original = generate_store("urban_cvs", seed=7, currency=currency)
    assert set(excluded) <= {rack.rack_desc for rack in original.product_racks}
    options = LayoutOptions(excluded_categories=excluded, dining_tables=1, width=20, height=16)
    store = generate_store("urban_cvs", seed=7, currency=currency, options=options)
    assert validate(store) == []
    assert not set(excluded) & {rack.rack_desc for rack in store.product_racks}
    alcohol = {localized(item, currency)[0] for item in CATALOG["beer_alcohol"]}
    assert not alcohol & {item.name for rack in store.product_racks for slot in rack.slots for item in slot.items}
    assert store.entrances and store.exits and store.counters and store.product_racks
    assert sum(rack.type.value == "table" for rack in store.racks) == 1
    assert generate_store("urban_cvs", seed=7, currency=currency, options=options) == store
    assert generate_store("urban_cvs", seed=7, currency=currency) == original


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.id)
def test_each_format_can_limit_its_assortment_or_reports_its_only_category(template):
    categories = sorted(set(template.fridges + template.freezers + template.wall_shelves + template.gondolas + template.near_counter))
    options = LayoutOptions(excluded_categories=[categories[0]])
    if len(categories) == 1:
        with pytest.raises(ValueError, match="Keep at least one product category"):
            generate_store(template.id, options=options)
    else:
        store = generate_store(template.id, options=options)
        assert validate(store) == []
        assert store.product_racks
        assert categories[0] not in {rack.rack_desc for rack in store.product_racks}


def test_unknown_categories_fail_and_unrelated_exclusions_keep_the_same_floor():
    with pytest.raises(ValueError, match="Unknown product categories: imaginary"):
        generate_store("urban_cvs", options=LayoutOptions(excluded_categories=["imaginary"]))
    assert generate_store("community_pharmacy") == generate_store(
        "community_pharmacy", options=LayoutOptions(excluded_categories=["beer_alcohol"]))
