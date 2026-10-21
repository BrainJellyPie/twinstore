"""Store-format templates: every layout is valid, localized, and shoppable."""

import asyncio

import pytest

from store_emulator.application.config import local_config
from store_emulator.application.simulation import (
    RunOptions,
    apply_options,
    run_simulation,
    subsample_personas,
)
from store_emulator.domain.config import EngineType
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen.catalog import category_label
from store_emulator.domain.persona import Persona
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("template_id", [t.id for t in TEMPLATES])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_every_template_is_valid(template_id, currency):
    store = generate_store(template_id, seed=3, currency=currency)
    assert not [i for i in validate(store) if i.severity == "error"]
    assert store.entrances and store.exits and store.counters
    items = [i for r in store.racks for s in r.slots for i in s.items]
    assert len(items) >= 100 and all(i.price > 0 for i in items)
    if currency == "KRW":
        assert all(i.price % 100 == 0 for i in items)
        assert all(r.rack_name.startswith(category_label(r.rack_desc, currency))
                   for r in store.product_racks)
    elif currency == "JPY":
        assert all(item.price % 10 == 0 for item in items)
    # Same product on several faces is one SKU (extra facings), never a renamed duplicate.
    names = {}
    for i in items:
        assert names.setdefault(i.name, i.sku) == i.sku


def test_generation_is_deterministic_and_styles_differ():
    a = generate_store("mini_mart", seed=1)
    assert a == generate_store("mini_mart", seed=1)
    loop = generate_store("urban_cvs", seed=1, style="loop")
    aisles = generate_store("urban_cvs", seed=1, style="aisles")
    assert {r.position for r in loop.racks} != {r.position for r in aisles.racks}


@pytest.mark.parametrize("template_id", ["campus_cvs", "specialty_cafe"])
def test_rule_based_shoppers_buy_in_a_generated_store(template_id):
    import json
    from pathlib import Path
    sample = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"
    personas = [Persona.model_validate(p) for p in json.loads((sample / "personas.json").read_text())]
    cfg = apply_options(local_config(), RunOptions(engine_type=EngineType.RULE_BASED, seed=1))
    store = generate_store(template_id, seed=1, options=LayoutOptions(entrance="left", exit_position="right"))
    agg, customers, _ = asyncio.run(run_simulation(cfg, store, subsample_personas(personas, 200, 1)))
    assert agg.summary.conversion_rate > 0.5 and agg.summary.units_sold > 100
    assert customers and all(customer.timeline for customer in customers)
    assert all((c.timeline[0].x, c.timeline[0].y) == store.entrances[0].position for c in customers)
    assert all(c.timeline[-1].action == "exit" and (c.timeline[-1].x, c.timeline[-1].y) == store.exits[0].position
               for c in customers)


@pytest.mark.parametrize("template_id", [t.id for t in TEMPLATES])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("density", ["spacious", "balanced", "dense"])
def test_all_format_pattern_density_combinations_are_accessible(template_id, style, density):
    store = generate_store(template_id, seed=17, options=LayoutOptions(
        style=style, density=density, entrance="center", checkouts=4))
    assert validate(store) == []
    assert len(store.counters) == 4
    assert store.product_racks


@pytest.mark.parametrize("dimensions", [(8, 6), (8, 7), (9, 8), (13, 11), (40, 40)])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("entrance", ["left", "center", "right"])
def test_custom_sizes_keep_routes_and_stock_accessible(dimensions, style, entrance):
    store = generate_store("hypermarket", seed=8, options=LayoutOptions(
        width=dimensions[0], height=dimensions[1], style=style, entrance=entrance, checkouts=4))
    assert store.grid_size == dimensions
    assert validate(store) == []
    assert len(store.counters) == 4


def test_shuffle_changes_assortment_but_keeps_reproducible_routes():
    original = generate_store("urban_cvs", seed=1)
    shuffled = generate_store("urban_cvs", seed=2)
    assert original.racks != shuffled.racks
    assert [r.position for r in original.racks] == [r.position for r in shuffled.racks]
    assert shuffled == generate_store("urban_cvs", seed=2)


def test_density_design_and_format_assortments_are_applied():
    spacious = generate_store("hypermarket", options=LayoutOptions(density="spacious"))
    dense = generate_store("hypermarket", options=LayoutOptions(density="dense", fixture_design="c"))
    assert len(dense.racks) > len(spacious.racks)
    assert all(r.design_variant == "c" for r in dense.racks if r.type == "shelf")
    pharmacy = generate_store("community_pharmacy")
    assert any(r.rack_desc == "pharmacy_care" for r in pharmacy.product_racks)
    restaurant = generate_store("quick_service")
    assert any(r.rack_desc == "restaurant_menu" for r in restaurant.product_racks)


@pytest.mark.parametrize("theme", ["classic", "warm", "minimal", "industrial", "botanical", "luxury"])
def test_interior_design_survives_store_round_trip(theme):
    from store_emulator.domain.store import Store
    store = generate_store("specialty_cafe", options=LayoutOptions(design_theme=theme))
    assert Store.model_validate(store.model_dump()).design_theme == theme
    assert validate(store) == []


def test_old_stores_keep_classic_design_and_formats_supply_defaults():
    from store_emulator.domain.store import Store
    store = generate_store("community_pharmacy")
    assert store.design_theme == "minimal"
    assert generate_store("specialty_cafe").design_theme == "warm"
    assert Store.model_validate(store.model_dump(exclude={"design_theme"})).design_theme == "classic"


@pytest.mark.parametrize("dimensions,tables", [((8, 6), 1), ((14, 12), 6), ((40, 40), 12)])
@pytest.mark.parametrize("style", ["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"])
@pytest.mark.parametrize("entrance", ["left", "center", "right"])
def test_dining_furniture_reserves_space_without_blocking_shopping(dimensions, tables, style, entrance):
    store = generate_store("book_cafe", options=LayoutOptions(width=dimensions[0], height=dimensions[1],
                           dining_tables=tables, style=style, entrance=entrance, checkouts=4, density="dense"))
    dining = [r for r in store.racks if r.type == "table"]
    assert len(dining) == tables
    assert validate(store) == []
    grid = store.walkable_grid()
    for table in dining:
        assert len(table.occupied_positions) == 4
        assert table.slots == [] and table.valid_faces(0) == []
        assert table.access_tiles(store.grid_size)
        assert all(grid[y][x] == 0 for x, y in table.occupied_positions)


def test_dining_defaults_fit_small_grids_but_explicit_capacity_is_enforced():
    small = generate_store("food_hall", options=LayoutOptions(width=8, height=6))
    assert len([r for r in small.racks if r.type == "table"]) == 1
    assert validate(small) == []
    assert not any(r.type == "table" for r in generate_store("food_hall", options=LayoutOptions(dining_tables=0)).racks)
    with pytest.raises(ValueError, match="at most 1 dining tables"):
        generate_store("specialty_cafe", options=LayoutOptions(width=8, height=6, dining_tables=2))


@pytest.mark.parametrize("zone", ["auto", "front", "back", "left", "right", "center"])
@pytest.mark.parametrize("placement", ["auto", "near_entrance", "away_from_entrance"])
@pytest.mark.parametrize("entrance", ["left", "center", "right"])
@pytest.mark.parametrize("dimensions,tables", [((8, 6), 1), ((18, 14), 8)])
def test_seating_and_checkout_placement_keep_routes_clear(zone, placement, entrance, dimensions, tables):
    options = LayoutOptions(width=dimensions[0], height=dimensions[1], dining_tables=tables,
                            seating_zone=zone, checkout_placement=placement, entrance=entrance,
                            checkouts=4, density="dense", style="showroom")
    store = generate_store("book_cafe", seed=5, options=options)
    assert validate(store) == []
    assert len(store.counters) == 4
    assert sum(r.type == "table" for r in store.racks) == tables
    assert store == generate_store("book_cafe", seed=5, options=options)


def test_seating_starts_in_the_requested_part_of_the_floor():
    positions = {}
    for zone in ("auto", "front", "back", "left", "right", "center"):
        store = generate_store("specialty_cafe", options=LayoutOptions(width=20, height=16,
                               dining_tables=1, seating_zone=zone))
        positions[zone] = next(r.position for r in store.racks if r.type == "table")
    assert positions["auto"] == (2, 2)  # Existing saved defaults keep their layout.
    assert positions["front"][1] > 16 * 2 / 3
    assert positions["back"][1] < 16 / 3
    assert positions["left"][0] < 20 / 3
    assert positions["right"][0] > 20 * 2 / 3
    assert abs(positions["center"][0] + 1 - 10) <= 2
    assert abs(positions["center"][1] + 1 - 8) <= 2


@pytest.mark.parametrize("entrance", ["left", "center", "right"])
def test_checkout_placement_uses_distance_from_the_actual_entrance(entrance):
    near = generate_store("hypermarket", options=LayoutOptions(entrance=entrance, checkout_placement="near_entrance"))
    far = generate_store("hypermarket", options=LayoutOptions(entrance=entrance, checkout_placement="away_from_entrance"))
    door_x = near.entrances[0].position[0]
    assert abs(near.counters[0].position[0] - door_x) < abs(far.counters[0].position[0] - door_x)
    assert validate(near) == validate(far) == []


@pytest.mark.parametrize("template_id,tables,design", [
    ("family_restaurant", 8, "warm"), ("neighborhood_bistro", 6, "luxury"),
    ("takeaway_coffee", 0, "industrial"), ("tea_lounge", 6, "botanical"),
    ("artisan_bakery", 2, "warm"), ("vintage_boutique", 0, "warm"),
    ("hardware_store", 0, "industrial"), ("toy_hobby_store", 0, "minimal"),
])
def test_specialty_formats_have_distinct_defaults_that_users_can_override(template_id, tables, design):
    store = generate_store(template_id)
    assert store.design_theme == design
    assert sum(r.type == "table" for r in store.racks) == tables
    assert validate(store) == []
    custom = generate_store(template_id, options=LayoutOptions(design_theme="classic", dining_tables=1,
                            seating_zone="front", checkout_placement="away_from_entrance"))
    assert custom.design_theme == "classic"
    assert sum(r.type == "table" for r in custom.racks) == 1
    assert validate(custom) == []


def test_new_format_defaults_apply_actual_positions_and_specialty_products():
    cafe = generate_store("tea_lounge")
    tables = [rack for rack in cafe.racks if rack.type == "table"]
    assert tables[0].position[0] > cafe.grid_size[0] / 2
    assert any(rack.rack_desc == "tea_menu" for rack in cafe.product_racks)
    assert any(rack.rack_desc == "hardware" for rack in generate_store("hardware_store").product_racks)
    assert any(rack.rack_desc == "toys_hobbies" for rack in generate_store("toy_hobby_store").product_racks)
    assert generate_store("vintage_boutique").design_theme != generate_store("fashion_boutique").design_theme
    assert generate_store("takeaway_coffee").counters[0].position[0] == 1
