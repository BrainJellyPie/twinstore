"""Small and all-day pharmacies and distinct dining menus retain bounded layouts."""
import pytest
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import generate_store, get_template
from store_emulator.engine.validation import validate

FORMATS = [
    ("compact_pharmacy", (8, 8), "spine", "minimal", 1, 0, (9, 19), [7], "pharmacy_care", 8),
    ("round_the_clock_pharmacy", (24, 18), "cross", "coastal", 4, 0, (0, 24), [], "care_supplies", 12),
    ("mediterranean_deli", (20, 18), "perimeter", "coastal", 2, 6, (10, 22), [1], "mediterranean_menu", 12),
    ("mexican_cantina", (24, 20), "plaza", "terracotta", 3, 8, (11, 24), [], "mexican_menu", 12),
]

@pytest.mark.parametrize("template,grid,style,theme,counters,tables,hours,closed,category,count", FORMATS)
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_defaults_preserve_menu_stock_schedules_and_repeatability(template, grid, style, theme, counters, tables, hours, closed, category, count, currency):
    store = generate_store(template, currency=currency)
    assert validate(store) == [] and store == generate_store(template, currency=currency)
    assert store.grid_size == grid and store.design_theme == theme and store.currency == currency
    assert get_template(template).style == style
    assert len(store.counters) == counters and sum(r.type == "table" for r in store.racks) == tables
    assert [d.day for d in store.weekly_schedule if not d.is_open] == closed
    assert {(d.open_hour, d.close_hour) for d in store.open_days} == {hours}
    items = [item for rack in store.product_racks if rack.rack_desc == category for slot in rack.slots for item in slot.items]
    assert len({item.sku for item in items}) == len({item.name for item in items}) == count
    assert all(item.price > 0 for item in items)
    if currency == "KRW": assert all(item.price % 100 == 0 for item in items)
    if currency == "JPY": assert all(item.price % 10 == 0 for item in items)

@pytest.mark.parametrize("template", [row[0] for row in FORMATS])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "plaza", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("grid", [(8, 6), (8, 40), (40, 6), (40, 40)])
def test_all_patterns_at_extreme_dimensions(template, style, grid):
    store = generate_store(template, options=LayoutOptions(width=grid[0], height=grid[1], style=style, checkouts=1, dining_tables=0,
        gate_wall="back", entrance="center", exit_wall="right", exit_position="center", shelf_direction="vertical", products_per_category=1))
    assert validate(store) == [] and store.grid_size == grid and store.product_racks

@pytest.mark.parametrize("template,category,count", [(row[0], row[8], row[9]) for row in FORMATS])
@pytest.mark.parametrize("grid", [(8, 6), (9, 7), (40, 40)])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("limit", [1, 16])
def test_isolated_specialty_category_and_assortment_limits(template, category, count, grid, direction, limit):
    definition = get_template(template)
    categories = set(definition.fridges + definition.freezers + definition.wall_shelves + definition.gondolas + definition.near_counter)
    options = LayoutOptions(width=grid[0], height=grid[1], checkouts=1, dining_tables=0, shelf_direction=direction,
        excluded_categories=sorted(categories - {category}), products_per_category=limit,
        gate_wall="left", exit_wall="right", entrance="center", exit_position="center")
    store = generate_store(template, seed=45, options=options)
    assert validate(store) == []
    assert {rack.rack_desc for rack in store.product_racks} == {category}
    assert len({item.sku for rack in store.product_racks for slot in rack.slots for item in slot.items}) == min(limit, count)
    assert store == generate_store(template, seed=45, options=options)

@pytest.mark.parametrize("template", [row[0] for row in FORMATS])
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("rotation", [0, 90])
def test_mixed_dining_and_clearance_with_individual_hours_and_colors(template, wall, rotation):
    options = LayoutOptions.model_validate({"width": 32, "height": 28, "checkouts": 3, "checkout_clearance": 2,
        "gate_wall": wall, "checkout_wall": wall, "table_mix": {"two_seat": 2, "four_seat": 2, "six_seat": 2},
        "table_rotation": rotation, "table_clearance": 2, "design_colors": {"floor": "#000000", "accent": "#abcdef"},
        "reserved_areas": [{"label": "Service corner", "x": 24, "y": 18, "width": 2, "height": 2}],
        "weekly_hours": [{"day": d, "is_open": d == 7, "open_hour": 23, "close_hour": 24} for d in range(1, 8)]})
    store = generate_store(template, options=options)
    assert validate(store) == []
    assert sorted(len(r.occupied_positions) for r in store.racks if r.type == "table") == [2, 2, 4, 4, 6, 6]
    assert [entry.day for entry in store.open_days] == [7]
    assert store.design_colors.floor == "#000000"

@pytest.mark.parametrize("template", [row[0] for row in FORMATS])
def test_excluding_every_category_returns_an_explicit_recovery_error(template):
    t = get_template(template)
    with pytest.raises(ValueError, match="at least one product category"):
        generate_store(template, options=LayoutOptions(excluded_categories=sorted(set(t.fridges + t.freezers + t.wall_shelves + t.gondolas + t.near_counter))))
