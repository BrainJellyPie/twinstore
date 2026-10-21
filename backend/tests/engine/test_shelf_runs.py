"""Shelf run limits add cross aisles while keeping every product accessible."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "showroom"])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("limit", [1, 8])
@pytest.mark.parametrize("dimensions", [(8, 6), (40, 40)])
def test_runs_never_exceed_the_selected_limit(style, direction, limit, dimensions):
    store = generate_store("hypermarket", options=LayoutOptions(
        style=style, width=dimensions[0], height=dimensions[1], shelf_direction=direction,
        max_shelf_run=limit, aisle_width=3, density="dense",
    ))
    assert validate(store) == []
    w, h = dimensions
    rows = {}
    for rack in store.product_racks:
        x, y = rack.position
        if 0 < x < w - 1 and 0 < y < h - 1:
            along, across = (y, x) if direction == "vertical" else (x, y)
            rows.setdefault(across, []).append(along)
    longest = 0
    for positions in rows.values():
        previous, run = -2, 0
        for position in sorted(positions):
            run = run + 1 if position == previous + 1 else 1
            previous = position
            longest = max(longest, run)
    assert longest <= limit
    if style == "aisles" and dimensions == (40, 40):
        assert longest == limit


@pytest.mark.parametrize("template_id", [t.id for t in TEMPLATES])
@pytest.mark.parametrize("limit", [1, 8])
def test_each_format_supports_short_and_long_runs_with_valid_shopping_routes(template_id, limit):
    options = LayoutOptions(max_shelf_run=limit, aisle_width=2, shelf_direction="vertical")
    store = generate_store(template_id, seed=13, options=options)
    assert validate(store) == []
    assert store.product_racks
    assert store == generate_store(template_id, seed=13, options=options)


@pytest.mark.parametrize("density,limit", [("spacious", 3), ("balanced", 4), ("dense", 6)])
def test_omitted_run_limit_retains_the_density_default(density, limit):
    options = LayoutOptions(density=density, width=30, height=24)
    assert generate_store("hypermarket", options=options) == generate_store(
        "hypermarket", options=options.model_copy(update={"max_shelf_run": limit}))


def test_shorter_runs_add_gaps_without_moving_tables_gates_or_wall_fixtures():
    options = LayoutOptions(width=30, height=24, style="aisles", dining_tables=4, seating_zone="front",
                            aisle_width=2, max_shelf_run=8, entrance="center", exit_position="right")
    long = generate_store("book_cafe", options=options)
    short = generate_store("book_cafe", options=options.model_copy(update={"max_shelf_run": 1}))
    assert len(short.product_racks) < len(long.product_racks)
    assert [r for r in long.racks if not r.slots or r.position[0] in (0, 29) or r.position[1] in (0, 23)] == [
        r for r in short.racks if not r.slots or r.position[0] in (0, 29) or r.position[1] in (0, 23)]


def test_run_limit_does_not_change_perimeter_layouts():
    assert generate_store("family_restaurant") == generate_store("family_restaurant", options=LayoutOptions(max_shelf_run=1))
