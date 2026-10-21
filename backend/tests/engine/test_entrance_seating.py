"""Seating follows the entrance while preserving room, circulation and furniture sizes."""
import re
import pytest
from pydantic import ValidationError
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate

ZONES = ["near_entrance", "away_from_entrance"]
WALLS = ["front", "back", "left", "right"]
STYLES = ["aisles", "loop", "spine", "cross", "plaza", "free_flow", "perimeter", "showroom"]


def tables(store):
    return [r for r in store.racks if r.type == "table"]


def center(table):
    positions = table.occupied_positions
    return (sum(x for x, _ in positions) / len(positions), sum(y for _, y in positions) / len(positions))


def check_ring(store, gap_x, gap_y):
    grid = store.walkable_grid()
    for table in tables(store):
        own = set(table.occupied_positions)
        for x in range(min(x for x, _ in own) - gap_x, max(x for x, _ in own) + gap_x + 1):
            for y in range(min(y for _, y in own) - gap_y, max(y for _, y in own) + gap_y + 1):
                if (x, y) not in own:
                    assert 0 <= x < store.grid_size[0] and 0 <= y < store.grid_size[1] and grid[y][x] == 1


@pytest.mark.parametrize("wall", WALLS)
@pytest.mark.parametrize("position", ["left", "center", "right"])
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("seats", [2, 4, 6])
@pytest.mark.parametrize("gaps", [(1, 1), (4, 1), (1, 4)])
def test_first_table_tracks_actual_entrance_on_both_axes_and_ignores_the_exit(wall, position, rotation, seats, gaps):
    options = dict(width=28, height=24, style="perimeter", checkouts=1, gate_wall=wall, entrance=position,
        dining_tables=1, dining_seats=seats, table_rotation=rotation, table_clearance_x=gaps[0], table_clearance_y=gaps[1])
    near = generate_store("specialty_cafe", options=LayoutOptions(**options, seating_zone="near_entrance"))
    far = generate_store("specialty_cafe", options=LayoutOptions(**options, seating_zone="away_from_entrance"))
    assert validate(near) == validate(far) == []
    entrance = next(r.position for r in near.racks if r.type == "entrance")
    close, distant = center(tables(near)[0]), center(tables(far)[0])
    near_axes = [abs(close[i] - entrance[i]) for i in range(2)]
    far_axes = [abs(distant[i] - entrance[i]) for i in range(2)]
    assert all(a <= b for a, b in zip(near_axes, far_axes, strict=True)) and sum(near_axes) < sum(far_axes)
    assert len(tables(near)[0].occupied_positions) == len(tables(far)[0].occupied_positions) == seats
    independent_exit = generate_store("specialty_cafe", options=LayoutOptions(**options, seating_zone="near_entrance",
        exit_wall=WALLS[(WALLS.index(wall) + 1) % 4], exit_position="right"))
    assert tables(independent_exit)[0].position == tables(near)[0].position
    check_ring(near, *gaps); check_ring(far, *gaps)


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("wall", WALLS)
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("zone", ZONES)
def test_mixed_groups_keep_clear_gaps_and_reserved_space_in_every_pattern(style, wall, rotation, zone):
    gaps = (4, 1) if zone == "near_entrance" else (1, 4)
    options = LayoutOptions.model_validate({"width": 40, "height": 36, "style": style, "gate_wall": wall, "entrance": "right",
        "checkouts": 3, "checkout_wall": wall, "checkout_clearance": 2, "seating_zone": zone,
        "table_mix": {"two_seat": 2, "four_seat": 2, "six_seat": 2}, "table_rotation": rotation,
        "table_clearance_x": gaps[0], "table_clearance_y": gaps[1], "density": "dense",
        "shelf_direction": "vertical" if rotation else "horizontal",
        "reserved_areas": [{"label": "Pickup", "x": 30, "y": 26, "width": 4, "height": 3}]})
    store = generate_store("thai_kitchen", options=options)
    assert validate(store) == []
    assert sorted(len(r.occupied_positions) for r in tables(store)) == [2, 2, 4, 4, 6, 6]
    assert all(not (30 <= x < 34 and 26 <= y < 29) for table in tables(store) for x, y in table.occupied_positions)
    check_ring(store, *gaps)
    assert store == generate_store("thai_kitchen", options=options)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
@pytest.mark.parametrize("zone", ZONES)
def test_every_format_adapts_default_seating_without_losing_stock(template, zone):
    store = generate_store(template.id, options=LayoutOptions(seating_zone=zone))
    assert validate(store) == [] and store.product_racks
    check_ring(store, 1, 1)


@pytest.mark.parametrize("grid", [(8, 6), (8, 40), (40, 6), (40, 40)])
@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("seats", [2, 4, 6])
def test_capacity_boundary_recovers_without_reducing_table_size(grid, zone, rotation, seats):
    options = dict(width=grid[0], height=grid[1], seating_zone=zone, gate_wall="right", entrance="center",
        table_rotation=rotation, dining_seats=seats, table_clearance_x=4, table_clearance_y=1, checkouts=1)
    try:
        store = generate_store("specialty_cafe", options=LayoutOptions(**options, dining_tables=48))
        assert len(tables(store)) == 48
    except ValueError as error:
        match = re.search(r"at most (\d+) dining tables", str(error)); assert match, str(error)
        capacity = int(match[1]); assert capacity < 48
        with pytest.raises(ValueError, match=f"at most {capacity} dining tables"):
            generate_store("specialty_cafe", options=LayoutOptions(**options, dining_tables=capacity + 1))
        store = generate_store("specialty_cafe", options=LayoutOptions(**options, dining_tables=capacity))
    assert validate(store) == [] and all(len(r.occupied_positions) == seats for r in tables(store))
    check_ring(store, 4, 1)


@pytest.mark.parametrize("zone", ["near", "far", "entrance", "outside", "NEAR_ENTRANCE", ""])
def test_unknown_zone_does_not_silently_choose_a_default(zone):
    with pytest.raises(ValidationError): LayoutOptions(seating_zone=zone)
