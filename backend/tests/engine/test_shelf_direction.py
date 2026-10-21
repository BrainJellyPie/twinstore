"""Interior patterns can turn without rotating the store's service and seating areas."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions, ReservedArea
from store_emulator.domain.types import Face
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("template_id", [t.id for t in TEMPLATES])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "showroom"])
def test_every_format_supports_vertical_shelves_with_accessible_products(template_id, style):
    store = generate_store(template_id, options=LayoutOptions(shelf_direction="vertical", style=style,
                           entrance="right", checkouts=4, density="dense"))
    assert validate(store) == []
    assert store.product_racks and len(store.counters) == 4
    w, h = store.grid_size
    interior = [r for r in store.product_racks if 0 < r.position[0] < w - 1 and 0 < r.position[1] < h - 1]
    assert all(r.rotation == 90 and {s.face for s in r.slots} == {Face.W, Face.E} for r in interior)


@pytest.mark.parametrize("dimensions", [(8, 6), (8, 7), (9, 8), (13, 11), (40, 40)])
@pytest.mark.parametrize("density", ["spacious", "balanced", "dense"])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "cross", "free_flow", "showroom"])
def test_rotated_patterns_fit_custom_dimensions_and_reserved_areas(dimensions, density, style):
    area = ReservedArea(label="Pickup", x=2, y=2, width=2, height=2)
    options = LayoutOptions(width=dimensions[0], height=dimensions[1], shelf_direction="vertical", style=style,
                            density=density, entrance="center", reserved_areas=[area])
    store = generate_store("book_cafe", seed=2, options=options)
    assert validate(store) == []
    assert store.grid_size == dimensions
    occupied = {pos for rack in store.racks for pos in rack.occupied_positions}
    assert {(2, 2), (3, 2), (2, 3), (3, 3)}.isdisjoint(occupied)
    assert store == generate_store("book_cafe", seed=2, options=options)


def test_shelf_direction_changes_interior_geometry_but_preserves_fixed_areas_and_legacy_defaults():
    options = LayoutOptions(width=24, height=16, style="aisles", dining_tables=2, seating_zone="front",
                            entrance="right", checkouts=3, checkout_placement="near_entrance")
    horizontal = generate_store("book_cafe", options=options)
    vertical = generate_store("book_cafe", options=options.model_copy(update={"shelf_direction": "vertical"}))
    assert horizontal == generate_store("book_cafe", options=options.model_copy(update={"shelf_direction": "horizontal"}))
    assert {r.position for r in horizontal.racks} != {r.position for r in vertical.racks}
    assert [r for r in horizontal.racks if r.type in ("entrance", "exit", "counter", "table")
            or r.position[0] in (0, 23) or r.position[1] in (0, 15)] == [
        r for r in vertical.racks if r.type in ("entrance", "exit", "counter", "table")
        or r.position[0] in (0, 23) or r.position[1] in (0, 15)]


def test_perimeter_pattern_keeps_wall_fixtures_in_place():
    assert generate_store("family_restaurant", options=LayoutOptions(style="perimeter")) == generate_store(
        "family_restaurant", options=LayoutOptions(style="perimeter", shelf_direction="vertical"))
