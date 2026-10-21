"""Central plazas remain clear and reachable across retail and dining requirements."""

from collections import deque

import pytest

from store_emulator.domain.layout_options import DiningTableMix, LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


def reachable_cells(store):
    grid = store.walkable_grid()
    width, height = store.grid_size
    seen = {store.entrances[0].position}
    queue = deque(seen)
    while queue:
        x, y = queue.popleft()
        for cell in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            cx, cy = cell
            if 0 <= cx < width and 0 <= cy < height and grid[cy][cx] and cell not in seen:
                seen.add(cell)
                queue.append(cell)
    return seen


@pytest.mark.parametrize("template", [template.id for template in TEMPLATES])
@pytest.mark.parametrize("density", ["spacious", "balanced", "dense"])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
def test_every_format_keeps_the_center_reachable_with_default_seating(template, density, direction):
    store = generate_store(template, seed=9, options=LayoutOptions(style="plaza", density=density, shelf_direction=direction))
    assert validate(store) == [] and store.product_racks
    width, height = store.grid_size
    assert (width // 2, height // 2) in reachable_cells(store)


@pytest.mark.parametrize("width,height,xs,ys", [
    (8, 6, range(3, 5), range(2, 4)),
    (8, 40, range(3, 5), range(14, 26)),
    (40, 6, range(14, 26), range(2, 4)),
    (40, 40, range(14, 26), range(14, 26)),
    (17, 13, range(6, 11), range(5, 8)),
    (32, 28, range(11, 21), range(10, 18)),
])
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
def test_exact_plaza_bounds_at_extremes_odd_sizes_and_with_overlapping_reservations(width, height, xs, ys, wall, direction):
    store = generate_store("hypermarket", options=LayoutOptions(style="plaza", width=width, height=height,
        gate_wall=wall, entrance="center", exit_position="right", checkout_wall=wall, checkouts=1, checkout_clearance=3,
        dining_tables=0, aisle_width=4, max_shelf_run=8, shelf_direction=direction,
        reserved_areas=[ReservedArea(label="Gathering space", x=xs.start, y=ys.start, width=2, height=2)]))
    assert validate(store) == [] and store.product_racks
    plaza = {(x, y) for x in xs for y in ys}
    occupied = {cell for rack in store.racks for cell in rack.occupied_positions}
    assert not plaza & occupied
    assert plaza <= reachable_cells(store)


@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("clearance", [1, 2, 3])
@pytest.mark.parametrize("zone", ["auto", "front", "back", "left", "right", "center"])
def test_mixed_tables_keep_clearance_and_leave_the_plaza_open(wall, rotation, clearance, zone):
    store = generate_store("office_cafeteria", options=LayoutOptions(style="plaza", width=32, height=28,
        gate_wall=wall, checkout_wall=wall, checkouts=3, checkout_clearance=2,
        table_mix=DiningTableMix(two_seat=1, four_seat=1, six_seat=1), table_rotation=rotation,
        table_clearance=clearance, seating_zone=zone, shelf_direction="vertical",
        reserved_areas=[ReservedArea(label="Pickup", x=26, y=21, width=3, height=2)]))
    assert validate(store) == []
    tables = [rack for rack in store.racks if rack.type == "table"]
    assert sorted(len(table.occupied_positions) for table in tables) == [2, 4, 6]
    plaza = {(x, y) for x in range(11, 21) for y in range(10, 18)}
    assert not plaza & {cell for rack in store.racks for cell in rack.occupied_positions}
    assert plaza <= reachable_cells(store)
    grid = store.walkable_grid()
    for table in tables:
        cells = set(table.occupied_positions)
        ring = {(x + dx, y + dy) for x, y in cells for dx in range(-clearance, clearance + 1)
                for dy in range(-clearance, clearance + 1)} - cells
        assert all(grid[y][x] for x, y in ring)


def test_explicit_seating_overflow_is_rejected_and_zero_or_auto_can_recover():
    for seats in [2, 4, 6]:
        with pytest.raises(ValueError, match="fits at most"):
            generate_store("family_restaurant", options=LayoutOptions(style="plaza", width=8, height=6, dining_tables=48, dining_seats=seats))
    for count in [None, 0]:
        store = generate_store("family_restaurant", options=LayoutOptions(style="plaza", width=8, height=6, dining_tables=count))
        assert validate(store) == [] and not any(rack.type == "table" for rack in store.racks)


def test_plaza_keeps_surrounding_rows_and_changes_only_the_selected_pattern():
    options = LayoutOptions(width=32, height=28, dining_tables=0, density="dense")
    aisles = generate_store("hypermarket", seed=7, options=options)
    plaza = generate_store("hypermarket", seed=7, options=options.model_copy(update={"style": "plaza"}))
    perimeter = generate_store("hypermarket", seed=7, options=options.model_copy(update={"style": "perimeter"}))
    assert len(perimeter.product_racks) < len(plaza.product_racks) < len(aisles.product_racks)
    assert plaza == generate_store("hypermarket", seed=7, options=options.model_copy(update={"style": "plaza"}))
    assert plaza.weekly_schedule == aisles.weekly_schedule
