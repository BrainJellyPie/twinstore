"""Custom shelf spacing keeps circulation open without moving service fixtures."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "free_flow", "showroom"])
@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("gap", [1, 4])
@pytest.mark.parametrize("dimensions", [(8, 6), (18, 14), (40, 40)])
def test_custom_gaps_separate_rows_and_shelf_runs_with_accessible_products(style, direction, gap, dimensions):
    store = generate_store("community_pharmacy", options=LayoutOptions(
        width=dimensions[0], height=dimensions[1], style=style, density="dense",
        shelf_direction=direction, aisle_width=gap,
    ))
    assert validate(store) == []
    w, h = store.grid_size
    interior = [r.position for r in store.product_racks if 0 < r.position[0] < w - 1 and 0 < r.position[1] < h - 1]
    rows = {}
    for x, y in interior:
        along, across = (y, x) if direction == "vertical" else (x, y)
        rows.setdefault(across, []).append(along)
    row_positions = sorted(rows)
    assert all(b - a - 1 >= gap for a, b in zip(row_positions, row_positions[1:]))
    for positions in rows.values():
        ordered = sorted(positions)
        assert all(b == a + 1 or b - a - 1 >= gap for a, b in zip(ordered, ordered[1:]))


@pytest.mark.parametrize("template_id", [t.id for t in TEMPLATES])
def test_all_formats_keep_accessible_products_with_wide_aisles_and_reserved_space(template_id):
    options = LayoutOptions(aisle_width=4, density="dense", shelf_direction="vertical",
                            reserved_areas=[ReservedArea(label="Consultation", x=2, y=2, width=3, height=2)])
    store = generate_store(template_id, seed=7, options=options)
    assert validate(store) == []
    assert store.product_racks
    assert {(2, 2), (3, 2), (4, 2), (2, 3), (3, 3), (4, 3)}.isdisjoint(
        pos for rack in store.racks for pos in rack.occupied_positions)
    assert store == generate_store(template_id, seed=7, options=options)


def test_wider_aisles_reduce_displays_without_moving_seating_or_service_areas():
    options = LayoutOptions(width=28, height=24, style="aisles", density="dense", dining_tables=2,
                            seating_zone="front", entrance="right", exit_position="center", checkouts=3)
    narrow = generate_store("book_cafe", options=options)
    wide = generate_store("book_cafe", options=options.model_copy(update={"aisle_width": 4}))
    assert len(wide.product_racks) < len(narrow.product_racks)
    assert [r for r in narrow.racks if not r.slots or r.position[0] in (0, 27) or r.position[1] in (0, 23)] == [
        r for r in wide.racks if not r.slots or r.position[0] in (0, 27) or r.position[1] in (0, 23)]


@pytest.mark.parametrize("density,gap", [("dense", 1), ("balanced", 2), ("spacious", 3)])
def test_omitted_spacing_retains_density_defaults(density, gap):
    options = LayoutOptions(width=24, height=18, style="aisles", density=density)
    assert generate_store("community_pharmacy", options=options) == generate_store(
        "community_pharmacy", options=options.model_copy(update={"aisle_width": gap}))


def test_perimeter_layout_does_not_change_with_aisle_gap():
    assert generate_store("family_restaurant") == generate_store("family_restaurant", options=LayoutOptions(aisle_width=4))
