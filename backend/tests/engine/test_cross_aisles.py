"""Central cross paths remain walkable even when seating is requested."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions, ReservedArea
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("gap", [1, 2, 3, 4])
@pytest.mark.parametrize("dimensions", [(8, 6), (17, 13), (40, 40)])
def test_cross_paths_are_clear_through_the_interior_with_seating_and_reservations(direction, gap, dimensions):
    options = LayoutOptions(style="cross", width=dimensions[0], height=dimensions[1], aisle_width=gap,
                            shelf_direction=direction, seating_zone="center",
                            reserved_areas=[ReservedArea(label="Pickup", x=1, y=1, width=2, height=2)])
    store = generate_store("book_cafe", seed=8, options=options)
    assert validate(store) == []
    w, h = dimensions
    x_start, y_start = (w - gap) // 2, (h - gap) // 2
    grid = store.walkable_grid()
    assert all(grid[y][x] == 1 for x in range(1, w - 1) for y in range(1, h - 1)
               if x_start <= x < x_start + gap or y_start <= y < y_start + gap)
    occupied = {p for rack in store.racks for p in rack.occupied_positions}
    assert {(1, 1), (1, 2), (2, 1), (2, 2)}.isdisjoint(occupied)
    assert store == generate_store("book_cafe", seed=8, options=options)


def test_automatic_seating_adapts_but_explicit_counts_cannot_block_cross_paths():
    options = LayoutOptions(style="cross", width=8, height=6)
    automatic = generate_store("specialty_cafe", options=options)
    assert not any(r.type == "table" for r in automatic.racks)
    assert validate(automatic) == []
    with pytest.raises(ValueError, match="at most 0 dining tables"):
        generate_store("specialty_cafe", options=options.model_copy(update={"dining_tables": 1}))


def test_cross_pattern_keeps_gates_counters_and_wall_fixtures_in_place():
    options = LayoutOptions(style="aisles", width=24, height=18, aisle_width=3,
                            entrance="center", exit_position="right", checkouts=4)
    parallel = generate_store("garden_center", options=options)
    crossed = generate_store("garden_center", options=options.model_copy(update={"style": "cross"}))
    assert len(crossed.product_racks) < len(parallel.product_racks)
    assert [r for r in parallel.racks if r.position[0] in (0, 23) or r.position[1] in (0, 17)] == [
        r for r in crossed.racks if r.position[0] in (0, 23) or r.position[1] in (0, 17)]


@pytest.mark.parametrize("template_id,category,theme,counters", [
    ("garden_center", "garden_supplies", "botanical", 4),
    ("art_craft_store", "art_craft", "warm", 2),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_garden_and_craft_formats_have_complete_specialty_assortments(template_id, category, theme, counters, currency):
    store = generate_store(template_id, currency=currency)
    items = [item for rack in store.product_racks if rack.rack_desc == category
             for slot in rack.slots for item in slot.items]
    assert len({item.name for item in items}) == 12
    assert all(item.price > 0 for item in items)
    assert store.design_theme == theme and len(store.counters) == counters
    assert store.currency == currency and validate(store) == []
