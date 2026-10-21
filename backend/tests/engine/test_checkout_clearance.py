"""Separated service points retain empty wall space and reachable merchandise."""

from itertools import combinations

import pytest
from pydantic import ValidationError

from store_emulator.domain.layout_options import DiningTableMix, LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


def assert_spacing(store, clearance):
    grid = store.walkable_grid()
    counters = [counter.position for counter in store.counters]
    for a, b in combinations(counters, 2):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) > clearance
    for counter in store.counters:
        x, y = counter.position
        horizontal = counter.rotation in (0, 180)
        for offset in range(-clearance, clearance + 1):
            cx, cy = (x + offset, y) if horizontal else (x, y + offset)
            if 0 <= cx < store.grid_size[0] and 0 <= cy < store.grid_size[1] and (cx, cy) != (x, y):
                assert grid[cy][cx], (counter.position, (cx, cy))
    assert validate(store) == []


@pytest.mark.parametrize("clearance", [0, 1, 2, 3])
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("placement", ["auto", "near_entrance", "away_from_entrance"])
@pytest.mark.parametrize("gate", ["front", "back", "left", "right"])
def test_spacing_leaves_gates_stock_and_mixed_dining_accessible(clearance, wall, placement, gate):
    options = LayoutOptions(width=32, height=28, checkout_clearance=clearance, checkouts=3,
                            checkout_wall=wall, checkout_placement=placement, gate_wall=gate,
                            entrance="center", exit_position="right", exit_wall=wall,
                            table_mix=DiningTableMix(two_seat=1, four_seat=1, six_seat=1),
                            table_rotation=90, table_clearance=2,
                            reserved_areas=[ReservedArea(label="Pickup", x=22, y=20, width=3, height=3)])
    store = generate_store("food_hall", options=options)
    assert len(store.counters) == 3
    assert_spacing(store, clearance)
    assert store == generate_store("food_hall", options=options)


@pytest.mark.parametrize("template", [template.id for template in TEMPLATES])
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
def test_all_formats_adapt_defaults_to_three_cell_spacing(template, wall):
    store = generate_store(template, options=LayoutOptions(checkout_clearance=3, checkout_wall=wall))
    assert 1 <= len(store.counters) <= next(t.checkouts for t in TEMPLATES if t.id == template)
    assert_spacing(store, 3)


@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("dimensions", [(8, 6), (8, 40), (40, 6), (40, 40)])
@pytest.mark.parametrize("clearance", [1, 2, 3])
def test_extreme_aspect_ratios_adapt_defaults_and_reject_excess_explicit_counts(wall, dimensions, clearance):
    options = LayoutOptions(width=dimensions[0], height=dimensions[1], checkout_wall=wall,
                            checkout_clearance=clearance, checkouts=None, dining_tables=0)
    store = generate_store("warehouse_club", options=options)
    assert_spacing(store, clearance)
    if len(store.counters) < 8:
        with pytest.raises(ValueError, match="checkout arrangement can place"):
            generate_store("warehouse_club", options=options.model_copy(update={"checkouts": 8}))


@pytest.mark.parametrize("bad", [-1, 4, 1.5, 2.0, True, False, "2", None])
def test_spacing_is_a_bounded_strict_integer(bad):
    with pytest.raises(ValidationError):
        LayoutOptions.model_validate({"checkout_clearance": bad})


def test_zero_spacing_preserves_existing_geometry_and_stock():
    for template in TEMPLATES:
        assert generate_store(template.id) == generate_store(template.id, options=LayoutOptions(checkout_clearance=0))
