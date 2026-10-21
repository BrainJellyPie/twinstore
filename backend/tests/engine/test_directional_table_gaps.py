"""Directional circulation stays clear across table footprints, orientations and floor patterns."""
import re
import pytest
from pydantic import ValidationError
from store_emulator.domain.layout_options import LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate

GAPS = [(1, 4), (4, 1), (2, 3), (3, 2), (4, 4), (None, 4)]
STYLES = ["aisles", "loop", "spine", "cross", "plaza", "free_flow", "perimeter", "showroom"]


def assert_clear_ring(store, gap_x, gap_y):
    grid = store.walkable_grid()
    for table in [rack for rack in store.racks if rack.type == "table"]:
        own = set(table.occupied_positions)
        min_x, max_x = min(x for x, _ in own), max(x for x, _ in own)
        min_y, max_y = min(y for _, y in own), max(y for _, y in own)
        ring = {(x, y) for x in range(min_x - gap_x, max_x + gap_x + 1)
                for y in range(min_y - gap_y, max_y + gap_y + 1)} - own
        assert all(0 <= x < store.grid_size[0] and 0 <= y < store.grid_size[1] and grid[y][x] == 1 for x, y in ring)


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("gap_x,gap_y", GAPS)
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("seats", [2, 4, 6, "mixed"])
def test_every_ring_stays_walkable_with_mixed_sizes_rotations_and_reserved_space(style, gap_x, gap_y, rotation, seats):
    options = LayoutOptions(width=40, height=36, style=style, density="dense", shelf_direction="vertical",
        table_clearance=2, table_clearance_x=gap_x, table_clearance_y=gap_y, table_rotation=rotation,
        reserved_areas=[ReservedArea(label="Pickup", x=30, y=26, width=4, height=3)], seating_zone="center",
        dining_tables=4 if seats == "mixed" else 3, dining_seats=4 if seats == "mixed" else seats,
        table_mix={"two_seat": 2, "four_seat": 1, "six_seat": 1} if seats == "mixed" else None)
    store = generate_store("book_cafe", options=options)
    assert validate(store) == []
    tables = [rack for rack in store.racks if rack.type == "table"]
    assert len(tables) == (4 if seats == "mixed" else 3)
    assert sorted(len(rack.occupied_positions) for rack in tables) == ([2, 2, 4, 6] if seats == "mixed" else [seats] * 3)
    assert_clear_ring(store, gap_x or 2, gap_y)
    assert store == generate_store("book_cafe", options=options)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
@pytest.mark.parametrize("gap_x,gap_y", [(1, 4), (4, 1), (4, 4)])
def test_formats_adapt_default_seating_and_keep_stock(template, gap_x, gap_y):
    store = generate_store(template.id, options=LayoutOptions(table_clearance_x=gap_x, table_clearance_y=gap_y))
    assert validate(store) == [] and store.product_racks
    assert_clear_ring(store, gap_x, gap_y)


@pytest.mark.parametrize("grid", [(8, 6), (8, 40), (40, 6), (40, 40)])
@pytest.mark.parametrize("gap_x,gap_y", [(1, 4), (4, 1), (4, 4)])
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("seats", [2, 4, 6])
def test_capacity_boundary_is_reported_and_recovers_without_shrinking_tables(grid, gap_x, gap_y, rotation, seats):
    base = dict(width=grid[0], height=grid[1], table_clearance_x=gap_x, table_clearance_y=gap_y,
                table_rotation=rotation, dining_seats=seats, style="perimeter", checkouts=1)
    try:
        store = generate_store("specialty_cafe", options=LayoutOptions(**base, dining_tables=48))
        assert len([rack for rack in store.racks if rack.type == "table"]) == 48
    except ValueError as error:
        match = re.search(r"at most (\d+) dining tables", str(error))
        assert match, str(error)
        capacity = int(match[1])
        assert capacity < 48
        with pytest.raises(ValueError, match=f"at most {capacity} dining tables"):
            generate_store("specialty_cafe", options=LayoutOptions(**base, dining_tables=capacity + 1))
        store = generate_store("specialty_cafe", options=LayoutOptions(**base, dining_tables=capacity))
    assert validate(store) == []
    assert_clear_ring(store, gap_x, gap_y)
    assert all(len(rack.occupied_positions) == seats for rack in store.racks if rack.type == "table")


@pytest.mark.parametrize("axis", ["table_clearance_x", "table_clearance_y"])
@pytest.mark.parametrize("value", [0, -1, 5, 1.0, 1.5, True, False, "2", float("nan"), float("inf")])
def test_overrides_are_strict_whole_cell_counts(axis, value):
    with pytest.raises(ValidationError):
        LayoutOptions.model_validate({axis: value})


@pytest.mark.parametrize("clearance", [1, 2, 3])
@pytest.mark.parametrize("rotation", [0, 90])
def test_explicit_equal_gaps_and_partial_inheritance_match_shared_spacing(clearance, rotation):
    common = dict(width=28, height=24, table_rotation=rotation, table_clearance=clearance, dining_tables=4)
    original = generate_store("family_restaurant", options=LayoutOptions(**common))
    for x, y in [(None, None), (clearance, None), (None, clearance), (clearance, clearance)]:
        assert original == generate_store("family_restaurant", options=LayoutOptions(**common, table_clearance_x=x, table_clearance_y=y))


def test_mixed_capacity_error_names_both_directions_and_zero_tables_retains_oversized_gaps():
    options = dict(width=8, height=6, table_clearance_x=4, table_clearance_y=1, table_rotation=90)
    with pytest.raises(ValueError, match="4-cell left-right and 1-cell back-front"):
        generate_store("specialty_cafe", options=LayoutOptions(**options, table_mix={"six_seat": 1}))
    store = generate_store("specialty_cafe", options=LayoutOptions(**options, dining_tables=0))
    assert validate(store) == [] and not any(rack.type == "table" for rack in store.racks)
