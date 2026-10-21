"""Visitor-oriented shops and evening dining retain usable customizable floor plans."""

import pytest

from store_emulator.domain.layout_options import DiningTableMix, LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate

FORMATS = ["airport_shopping_gallery", "hospital_convenience", "museum_gift_shop", "evening_food_court"]


@pytest.mark.parametrize("template,grid,theme,counters,tables,hours,closed,categories", [
    ("airport_shopping_gallery", (30, 24), "luxury", 4, 0, (0, 24), [], {"travel_gear", "fragrances", "jewelry", "electronics", "souvenirs"}),
    ("hospital_convenience", (18, 16), "minimal", 2, 0, (0, 24), [], {"care_supplies", "baby_supplies", "pharmacy_care", "flowers", "fresh_meals"}),
    ("museum_gift_shop", (16, 14), "nordic", 2, 0, (10, 18), [1], {"books", "art_craft", "souvenirs", "stationery", "home_design"}),
    ("evening_food_court", (32, 26), "terracotta", 6, 12, (16, 24), [], {"restaurant_menu", "korean_menu", "burger_menu", "salad_menu", "juice_menu"}),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_distinct_defaults_stock_hours_currency_and_repeatability(template, grid, theme, counters, tables, hours, closed, categories, currency):
    store = generate_store(template, currency=currency)
    assert store.grid_size == grid and store.design_theme == theme
    assert store.currency == currency
    assert len(store.counters) == counters
    assert sum(rack.type == "table" for rack in store.racks) == tables
    assert categories <= {rack.rack_desc for rack in store.product_racks}
    assert {day.day for day in store.weekly_schedule if not day.is_open} == set(closed)
    assert all((day.open_hour, day.close_hour) == hours for day in store.weekly_schedule if day.is_open)
    assert validate(store) == [] and store == generate_store(template, currency=currency)


@pytest.mark.parametrize("template", FORMATS)
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("dimensions", [(8, 6), (8, 40), (40, 6), (40, 40)])
def test_size_extremes_with_separate_gates_and_minimal_assortment(template, style, dimensions):
    store = generate_store(template, options=LayoutOptions(width=dimensions[0], height=dimensions[1], style=style,
        dining_tables=0, checkouts=1, checkout_wall="left", checkout_clearance=3, gate_wall="back", entrance="center",
        exit_wall="right", exit_position="center", products_per_category=1, open_hour=23, close_hour=24, closed_days=[1, 2, 3, 4, 5, 6]))
    assert validate(store) == [] and store.product_racks
    assert len(store.open_days) == 1 and store.open_days[0].day == 7
    for category in {rack.rack_desc for rack in store.product_racks}:
        assert len({item.sku for rack in store.product_racks if rack.rack_desc == category for slot in rack.slots for item in slot.items}) == 1


@pytest.mark.parametrize("template", FORMATS)
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("rotation", [0, 90])
def test_mixed_seating_spaced_counters_and_reserved_areas_can_be_combined(template, wall, rotation):
    options = LayoutOptions(width=32, height=28, checkout_wall=wall, checkout_clearance=2, checkouts=3,
        table_mix=DiningTableMix(two_seat=2, four_seat=1, six_seat=1), table_rotation=rotation, table_clearance=2,
        reserved_areas=[ReservedArea(label="Visitor information", x=24, y=21, width=4, height=3)],
        design_theme="retro", closed_days=[])
    store = generate_store(template, options=options)
    assert validate(store) == []
    assert sorted(len(rack.occupied_positions) for rack in store.racks if rack.type == "table") == [2, 2, 4, 6]
    assert store.design_theme == "retro" and len(store.counters) == 3
    assert all(day.is_open for day in store.weekly_schedule)
