"""Dining circulation is real empty floor space, including around the entire table group."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("clearance", [1, 2, 3])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
def test_every_side_of_each_dining_group_has_the_requested_clear_space(clearance, style, direction):
    area = ReservedArea(label="Pickup", x=15, y=5, width=3, height=3)
    store = generate_store("book_cafe", options=LayoutOptions(width=24, height=20, dining_tables=4,
                           table_clearance=clearance, style=style, shelf_direction=direction,
                           density="dense", seating_zone="center", reserved_areas=[area]))
    tables = [r for r in store.racks if r.type == "table"]
    assert len(tables) == 4
    assert validate(store) == []
    grid = store.walkable_grid()
    for table in tables:
        px, py = table.position
        own = set(table.occupied_positions)
        ring = {(x, y) for x in range(px - clearance, px + 2 + clearance)
                for y in range(py - clearance, py + 2 + clearance)} - own
        assert all(0 <= x < 24 and 0 <= y < 20 and grid[y][x] == 1 for x, y in ring)


@pytest.mark.parametrize("template_id", [t.id for t in TEMPLATES])
@pytest.mark.parametrize("clearance", [2, 3])
def test_all_formats_adapt_default_seating_to_the_requested_circulation(template_id, clearance):
    store = generate_store(template_id, options=LayoutOptions(table_clearance=clearance))
    assert validate(store) == []
    assert store.product_racks


def test_increasing_clearance_reduces_capacity_and_explicit_counts_report_the_limit():
    standard = generate_store("food_hall", options=LayoutOptions(width=16, height=14))
    spacious = generate_store("food_hall", options=LayoutOptions(width=16, height=14, table_clearance=3))
    assert sum(r.type == "table" for r in standard.racks) == 8
    assert sum(r.type == "table" for r in spacious.racks) == 2
    with pytest.raises(ValueError, match="at most 2 dining tables with 3-cell"):
        generate_store("food_hall", options=LayoutOptions(width=16, height=14, table_clearance=3, dining_tables=3))
    tiny = generate_store("specialty_cafe", options=LayoutOptions(width=8, height=6, table_clearance=2))
    assert not any(r.type == "table" for r in tiny.racks)
    assert validate(tiny) == []
