"""Weekday, weekend, commuter and leisure formats keep their distinct requirements."""

import pytest

from store_emulator.domain.layout_options import DiningTableMix, LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate

FORMATS = ["weekend_farmers_market", "station_food_market", "cinema_snack_shop", "office_cafeteria"]


@pytest.mark.parametrize("template,grid,theme,counters,tables,hours,closed,categories", [
    ("weekend_farmers_market", (28, 22), "botanical", 4, 0, (8, 16), [1, 2, 3, 4, 5], {"fresh_produce", "bakery", "pantry", "flowers", "refill_goods"}),
    ("station_food_market", (20, 14), "coastal", 3, 2, (5, 24), [], {"fresh_meals", "salad_menu", "bakery", "travel_gear", "coffee_station"}),
    ("cinema_snack_shop", (18, 12), "industrial", 3, 0, (10, 24), [], {"chips", "sweets", "soft_drinks", "ice_cream", "scoop_menu"}),
    ("office_cafeteria", (28, 24), "minimal", 4, 16, (7, 19), [6, 7], {"restaurant_menu", "korean_menu", "salad_menu", "cafe_menu", "juice_menu"}),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_defaults_assortment_schedules_and_reproducibility(template, grid, theme, counters, tables, hours, closed, categories, currency):
    store = generate_store(template, currency=currency)
    assert store.grid_size == grid and store.design_theme == theme
    assert store.currency == currency and len(store.counters) == counters
    assert sum(rack.type == "table" for rack in store.racks) == tables
    assert categories <= {rack.rack_desc for rack in store.product_racks}
    assert {day.day for day in store.weekly_schedule if not day.is_open} == set(closed)
    assert all((day.open_hour, day.close_hour) == hours for day in store.open_days)
    assert validate(store) == [] and store == generate_store(template, currency=currency)


@pytest.mark.parametrize("template", FORMATS)
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("dimensions", [(8, 6), (8, 40), (40, 6), (40, 40)])
def test_extreme_sizes_keep_routes_and_allow_one_hour_sunday_opening(template, style, dimensions):
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
def test_mixed_seating_spaced_counters_and_clear_areas_can_be_combined(template, wall, rotation):
    store = generate_store(template, options=LayoutOptions(width=32, height=28,
        checkout_wall=wall, gate_wall=wall, checkout_clearance=2, checkouts=3,
        table_mix=DiningTableMix(two_seat=2, four_seat=1, six_seat=1), table_rotation=rotation, table_clearance=2,
        reserved_areas=[ReservedArea(label="Pickup", x=24, y=21, width=4, height=3)],
        design_theme="retro", open_hour=0, close_hour=24, closed_days=[]))
    assert validate(store) == []
    assert sorted(len(rack.occupied_positions) for rack in store.racks if rack.type == "table") == [2, 2, 4, 6]
    assert store.design_theme == "retro" and len(store.counters) == 3
    assert all(day.is_open and day.open_hour == 0 and day.close_hour == 24 for day in store.weekly_schedule)
