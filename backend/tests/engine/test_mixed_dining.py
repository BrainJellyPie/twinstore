"""Mixed seating places exact counts and leaves walkable circulation between sizes."""

from collections import Counter

import pytest
from pydantic import ValidationError

from store_emulator.domain.layout_options import DiningTableMix, LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("mix", [DiningTableMix(two_seat=3, four_seat=2, six_seat=1), DiningTableMix(two_seat=2, six_seat=2), DiningTableMix(four_seat=2, six_seat=2)])
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("clearance", [1, 2, 3])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "perimeter", "showroom"])
def test_mixed_groups_have_exact_counts_and_clear_circulation(mix, rotation, clearance, style):
    options = LayoutOptions(width=32, height=28, table_mix=mix, table_rotation=rotation, table_clearance=clearance,
                            style=style, seating_zone="center", reserved_areas=[ReservedArea(label="Kitchen", x=25, y=20, width=4, height=3)])
    store = generate_store("retro_diner", options=options)
    assert validate(store) == []
    assert store == generate_store("retro_diner", options=options)
    tables = [rack for rack in store.racks if rack.type == "table"]
    expected = Counter({size: count for size, count in [(2, mix.two_seat), (4, mix.four_seat), (6, mix.six_seat)] if count})
    assert Counter(len(rack.occupied_positions) for rack in tables) == expected
    assert len({rack.id for rack in tables}) == mix.total
    grid = store.walkable_grid()
    occupied = [cell for table in tables for cell in table.occupied_positions]
    assert len(set(occupied)) == len(occupied)
    for table in tables:
        assert table.rotation == rotation
        assert not table.slots
        x, y = table.position
        width, depth = len(table.rotated_shape[0]), len(table.rotated_shape)
        ring = {(cx, cy) for cx in range(x - clearance, x + width + clearance)
                for cy in range(y - clearance, y + depth + clearance)} - set(table.occupied_positions)
        assert all(grid[cy][cx] == 1 for cx, cy in ring)


@pytest.mark.parametrize("template", [t.id for t in TEMPLATES])
def test_every_format_can_mix_tables_on_a_large_floor(template):
    mix = DiningTableMix(two_seat=1, four_seat=1, six_seat=1)
    store = generate_store(template, options=LayoutOptions(width=32, height=28, table_mix=mix))
    assert validate(store) == []
    assert sorted(len(r.occupied_positions) for r in store.racks if r.type == "table") == [2, 4, 6]


@pytest.mark.parametrize("zone", ["auto", "front", "back", "left", "right", "center"])
@pytest.mark.parametrize("rotation", [0, 90])
def test_seating_zones_and_rotation_keep_every_requested_size(zone, rotation):
    store = generate_store("retro_diner", options=LayoutOptions(table_mix=DiningTableMix(two_seat=2, four_seat=1, six_seat=1), seating_zone=zone, table_rotation=rotation))
    assert validate(store) == []
    assert sorted(len(r.occupied_positions) for r in store.racks if r.type == "table") == [2, 2, 4, 6]


@pytest.mark.parametrize("field", ["two_seat", "four_seat", "six_seat"])
@pytest.mark.parametrize("value", [-1, 49, 1.5, 2.0, True, False, "2", None])
def test_mixed_counts_are_bounded_strict_integers(field, value):
    with pytest.raises(ValidationError):
        DiningTableMix.model_validate({field: value})


def test_total_limit_inconsistent_counts_empty_mix_and_missing_fields():
    with pytest.raises(ValidationError, match="at most 48"):
        DiningTableMix(two_seat=24, four_seat=24, six_seat=1)
    with pytest.raises(ValidationError, match="must match"):
        LayoutOptions(table_mix=DiningTableMix(two_seat=2), dining_tables=3)
    with pytest.raises(ValidationError):
        DiningTableMix.model_validate({"eight_seat": 1})
    assert DiningTableMix.model_validate({"two_seat": 2}).total == 2
    assert not any(r.type == "table" for r in generate_store("retro_diner", options=LayoutOptions(table_mix=DiningTableMix())).racks)


def test_mixed_capacity_failure_identifies_the_size_instead_of_dropping_it():
    with pytest.raises(ValueError, match="requested 1 6-seat tables"):
        generate_store("retro_diner", options=LayoutOptions(width=8, height=6, table_rotation=90,
                       table_mix=DiningTableMix(two_seat=1, six_seat=1)))
