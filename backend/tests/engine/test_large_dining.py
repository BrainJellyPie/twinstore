"""Large dining floors retain full circulation and usable retail fixtures."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("clearance", [1, 2, 3])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"])
def test_maximum_48_table_floor_keeps_all_circulation_clear(clearance, style):
    store = generate_store("campus_dining_hall", options=LayoutOptions(width=40, height=40,
                           dining_tables=48, table_clearance=clearance, style=style, shelf_direction="vertical",
                           exit_position="right", checkouts=12))
    tables = [r for r in store.racks if r.type == "table"]
    assert len(tables) == 48 and len(store.counters) == 12
    assert validate(store) == []
    grid = store.walkable_grid()
    for table in tables:
        px, py = table.position
        own = set(table.occupied_positions)
        ring = {(x, y) for x in range(px - clearance, px + 2 + clearance)
                for y in range(py - clearance, py + 2 + clearance)} - own
        assert all(0 <= x < 40 and 0 <= y < 40 and grid[y][x] == 1 for x, y in ring)


def test_campus_dining_defaults_and_custom_capacity():
    store = generate_store("campus_dining_hall")
    assert store.grid_size == (32, 24)
    assert store.design_theme == "minimal"
    assert sum(r.type == "table" for r in store.racks) == 24
    assert len(store.counters) == 4
    assert [day.is_open for day in store.weekly_schedule] == [True] * 5 + [False] * 2
    assert validate(store) == []
    custom = generate_store("campus_dining_hall", options=LayoutOptions(dining_tables=13))
    assert sum(r.type == "table" for r in custom.racks) == 13
    assert validate(custom) == []
