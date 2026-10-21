"""Table sizes agree with occupied floor cells and preserve circulation."""

import pytest
from pydantic import ValidationError

from store_emulator.domain.layout_options import LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("seats", [2, 4, 6])
@pytest.mark.parametrize("clearance", [1, 2, 3])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
def test_table_sizes_keep_every_side_clear(seats, clearance, style, direction):
    store = generate_store("book_cafe", options=LayoutOptions(
        width=32, height=28, dining_tables=4, dining_seats=seats, table_clearance=clearance,
        style=style, shelf_direction=direction, seating_zone="center", density="dense",
        reserved_areas=[ReservedArea(label="Kitchen", x=25, y=20, width=4, height=3)],
    ))
    assert validate(store) == []
    tables = [rack for rack in store.racks if rack.type == "table"]
    assert len(tables) == 4
    grid = store.walkable_grid()
    for table in tables:
        assert table.shape == [[1] * (seats // 2)] * 2
        assert len(table.occupied_positions) == seats
        assert table.slots == []
        x, y = table.position
        ring = {(cx, cy) for cx in range(x - clearance, x + seats // 2 + clearance)
                for cy in range(y - clearance, y + 2 + clearance)} - set(table.occupied_positions)
        assert all(grid[cy][cx] == 1 for cx, cy in ring)


@pytest.mark.parametrize("template_id", [template.id for template in TEMPLATES])
@pytest.mark.parametrize("seats", [2, 4, 6])
def test_all_formats_adapt_default_seating_without_losing_stock(template_id, seats):
    store = generate_store(template_id, options=LayoutOptions(dining_seats=seats))
    assert validate(store) == []
    assert store.product_racks
    assert all(len(rack.occupied_positions) == seats for rack in store.racks if rack.type == "table")


@pytest.mark.parametrize("seats", [2, 4, 6])
def test_tiny_floor_explicit_overflow_zero_tables_and_legacy_default(seats):
    store = generate_store("specialty_cafe", options=LayoutOptions(width=8, height=6, dining_seats=seats))
    tables = [rack for rack in store.racks if rack.type == "table"]
    with pytest.raises(ValueError, match=f"at most {len(tables)} dining tables"):
        generate_store("specialty_cafe", options=LayoutOptions(width=8, height=6, dining_seats=seats, dining_tables=len(tables) + 1))
    empty = generate_store("specialty_cafe", options=LayoutOptions(dining_seats=seats, dining_tables=0))
    assert not any(rack.type == "table" for rack in empty.racks)
    assert generate_store("specialty_cafe") == generate_store("specialty_cafe", options=LayoutOptions(dining_seats=4))


@pytest.mark.parametrize("seats", [0, 1, 3, 5, 7, 48, -2, 2.0, 2.5, True, False, "2", None])
def test_table_sizes_are_strict_even_integer_choices(seats):
    with pytest.raises(ValidationError):
        LayoutOptions(dining_seats=seats)
