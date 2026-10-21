"""Market and design halls start with plazas and accept independent overrides."""

import pytest

from store_emulator.domain.layout_options import DiningTableMix, LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate

FORMATS = ["community_market_hall", "creative_design_hall"]


@pytest.mark.parametrize("template,grid,theme,counters,tables,hours,closed,categories", [
    ("community_market_hall", (32, 28), "botanical", 4, 4, (8, 20), [], {"fresh_produce", "fresh_meals", "bakery", "pantry", "flowers", "refill_goods"}),
    ("creative_design_hall", (30, 24), "nordic", 3, 0, (10, 20), [2], {"home_design", "art_craft", "books", "jewelry", "flowers", "stationery"}),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_default_plazas_stock_schedule_and_repeatability(template, grid, theme, counters, tables, hours, closed, categories, currency):
    store = generate_store(template, currency=currency)
    assert validate(store) == [] and store == generate_store(template, currency=currency)
    assert store.grid_size == grid and store.design_theme == theme and store.currency == currency
    assert len(store.counters) == counters and sum(rack.type == "table" for rack in store.racks) == tables
    assert categories <= {rack.rack_desc for rack in store.product_racks}
    assert {day.day for day in store.weekly_schedule if not day.is_open} == set(closed)
    assert all((day.open_hour, day.close_hour) == hours for day in store.open_days)
    assert store.walkable_grid()[grid[1] // 2][grid[0] // 2]
    assert store == generate_store(template, currency=currency, options=LayoutOptions(style="plaza"))


@pytest.mark.parametrize("template", FORMATS)
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "plaza", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("dimensions", [(8, 6), (8, 40), (40, 6), (40, 40)])
def test_extreme_pattern_overrides_are_valid_or_recover_by_reducing_counter_spacing(template, style, dimensions):
    options = LayoutOptions(style=style, width=dimensions[0], height=dimensions[1],
        dining_tables=0, checkouts=1, checkout_wall="right", checkout_clearance=3,
        gate_wall="back", entrance="center", exit_wall="left", exit_position="center", products_per_category=1,
        open_hour=23, close_hour=24, closed_days=[1, 2, 3, 4, 5, 6])
    if template == "creative_design_hall" and style == "cross" and dimensions[1] == 6:
        with pytest.raises(ValueError, match="no display space.*counter spacing.*checkout wall"):
            generate_store(template, options=options)
        options = options.model_copy(update={"checkout_clearance": 0})
    store = generate_store(template, options=options)
    assert validate(store) == [] and store.product_racks
    assert len(store.open_days) == 1 and store.open_days[0].day == 7
    assert store.grid_size == dimensions


@pytest.mark.parametrize("template", FORMATS)
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("rotation", [0, 90])
def test_mixed_dining_reservations_and_all_entrance_walls(template, wall, rotation):
    store = generate_store(template, options=LayoutOptions(width=32, height=28, gate_wall=wall, checkout_wall=wall,
        table_mix=DiningTableMix(two_seat=2, four_seat=2, six_seat=2), table_rotation=rotation, table_clearance=2,
        checkouts=3, checkout_clearance=2, shelf_direction="vertical", excluded_categories=["flowers"],
        reserved_areas=[ReservedArea(label="Event space", x=12, y=11, width=3, height=3)]))
    assert validate(store) == []
    assert sorted(len(rack.occupied_positions) for rack in store.racks if rack.type == "table") == [2, 2, 4, 4, 6, 6]
    assert "flowers" not in {rack.rack_desc for rack in store.product_racks}
    center = {(x, y) for x in range(11, 21) for y in range(10, 18)}
    assert not center & {cell for rack in store.racks for cell in rack.occupied_positions}
