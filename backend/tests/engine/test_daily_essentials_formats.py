"""Specialty formats retain stock, routes and schedule at option boundaries."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import generate_store, get_template
from store_emulator.engine.validation import validate

FORMATS = [
    ("refill_market", "refill_goods", "botanical", 4, 0),
    ("care_supply_store", "care_supplies", "minimal", 3, 0),
    ("fragrance_boutique", "fragrances", "luxury", 2, 0),
    ("bubble_tea_cafe", "bubble_tea_menu", "coastal", 2, 4),
]


@pytest.mark.parametrize("template_id,category,theme,counters,tables", FORMATS)
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_new_defaults_have_complete_specialty_products_and_independent_facings(template_id, category, theme, counters, tables, currency):
    store = generate_store(template_id, currency=currency)
    items = [item for rack in store.product_racks if rack.rack_desc == category for slot in rack.slots for item in slot.items]
    assert len({item.sku for item in items}) == 12
    assert len({item.name for item in items}) == 12
    assert all(item.price > 0 for item in items)
    assert len(store.counters) == counters
    assert sum(rack.type == "table" for rack in store.racks) == tables
    assert store.design_theme == theme
    assert validate(store) == []
    repeated = next(item for item in items[1:] if item.sku == items[0].sku)
    original = repeated.price
    items[0].price += 100
    assert repeated.price == original


@pytest.mark.parametrize("template_id,category,_theme,_counters,_tables", FORMATS)
@pytest.mark.parametrize("dimensions", [(8, 6), (9, 7), (40, 40)])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("limit", [1, 16])
def test_only_specialty_category_survives_small_large_and_assortment_limits(template_id, category, _theme, _counters, _tables, dimensions, direction, limit):
    template = get_template(template_id)
    assert template is not None
    categories = set(template.fridges + template.freezers + template.wall_shelves + template.gondolas + template.near_counter)
    options = LayoutOptions(width=dimensions[0], height=dimensions[1], dining_tables=0,
                            shelf_direction=direction, products_per_category=limit,
                            excluded_categories=sorted(categories - {category}),
                            entrance="center", exit_position="center", gate_wall="left", exit_wall="right",
                            checkouts=1, open_hour=23, close_hour=24, closed_days=[1, 2, 3, 4, 5, 6])
    store = generate_store(template_id, seed=45, options=options)
    assert validate(store) == []
    assert {rack.rack_desc for rack in store.product_racks} == {category}
    skus = {item.sku for rack in store.product_racks for slot in rack.slots for item in slot.items}
    assert len(skus) == min(limit, 12)
    assert [int(day.day) for day in store.open_days] == [7]
    assert not any(rack.type == "table" for rack in store.racks)
    assert generate_store(template_id, seed=45, options=options) == store


@pytest.mark.parametrize("template_id,category,_theme,_counters,_tables", FORMATS)
def test_excluding_specialty_and_all_categories_is_explicit(template_id, category, _theme, _counters, _tables):
    store = generate_store(template_id, options=LayoutOptions(excluded_categories=[category]))
    assert category not in {rack.rack_desc for rack in store.product_racks}
    assert validate(store) == []
    template = get_template(template_id)
    assert template is not None
    categories = set(template.fridges + template.freezers + template.wall_shelves + template.gondolas + template.near_counter)
    with pytest.raises(ValueError, match="at least one product category"):
        generate_store(template_id, options=LayoutOptions(excluded_categories=sorted(categories)))
