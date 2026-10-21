"""Checkout banks can use any wall without blocking gates, stock or dining routes."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("wall,rotation", [("back", 180), ("left", 90), ("right", 270)])
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.id)
def test_each_format_keeps_valid_checkout_and_shopping_access_on_other_walls(template, wall, rotation):
    store = generate_store(template.id, options=LayoutOptions(checkout_wall=wall))
    assert validate(store) == []
    width, height = store.grid_size
    assert len(store.counters) == template.checkouts
    for counter in store.counters:
        assert counter.rotation == rotation
        if wall == "back":
            assert counter.position[1] == 0
        else:
            assert counter.position[0] == (0 if wall == "left" else width - 1)
    assert all(gate.position[1] == height - 1 for gate in store.entrances + store.exits)
    assert store.product_racks


@pytest.mark.parametrize("wall", ["back", "left", "right"])
@pytest.mark.parametrize("entrance", ["left", "center", "right"])
def test_near_and_far_placement_uses_distance_from_actual_entrance_on_each_wall(wall, entrance):
    options = LayoutOptions(checkout_wall=wall, entrance=entrance, checkouts=3)
    near = generate_store("hypermarket", options=options.model_copy(update={"checkout_placement": "near_entrance"}))
    far = generate_store("hypermarket", options=options.model_copy(update={"checkout_placement": "away_from_entrance"}))
    ex, ey = near.entrances[0].position
    near_distance = sum(abs(c.position[0] - ex) + abs(c.position[1] - ey) for c in near.counters)
    far_distance = sum(abs(c.position[0] - ex) + abs(c.position[1] - ey) for c in far.counters)
    assert near_distance < far_distance


@pytest.mark.parametrize("wall", ["back", "left", "right"])
@pytest.mark.parametrize("style", ["perimeter", "cross"])
@pytest.mark.parametrize("dimensions", [(8, 6), (40, 40)])
def test_wall_stock_seating_and_separate_gates_coexist_on_small_and_large_floors(wall, style, dimensions):
    store = generate_store("food_hall", options=LayoutOptions(
        width=dimensions[0], height=dimensions[1], checkout_wall=wall, style=style,
        entrance="center", exit_position="right", shelf_direction="vertical",
    ))
    assert validate(store) == []


def test_side_wall_capacity_uses_depth_and_default_front_placement_is_unchanged():
    default = generate_store("hypermarket", seed=8)
    assert generate_store("hypermarket", seed=8, options=LayoutOptions(checkout_wall="front")) == default
    small = generate_store("warehouse_club", options=LayoutOptions(width=32, height=6, checkout_wall="right"))
    assert len(small.counters) == 4
    assert validate(small) == []
    with pytest.raises(ValueError, match="at most 4 checkout counters on the right wall"):
        generate_store("warehouse_club", options=LayoutOptions(width=32, height=6, checkout_wall="right", checkouts=5))


@pytest.mark.parametrize("wall,category,counters", [("front", "checkout_impulse", 6), ("back", "beer_alcohol", 6), ("right", "household", 4)])
def test_a_full_bank_cannot_silently_remove_the_only_requested_product_category(wall, category, counters):
    options = LayoutOptions(width=8, height=6, checkout_wall=wall, checkouts=counters,
                            checkout_placement="near_entrance", excluded_categories=[key for key in CATALOG if key != category])
    with pytest.raises(ValueError, match="No products from the included categories fit"):
        generate_store("urban_cvs", options=options)
