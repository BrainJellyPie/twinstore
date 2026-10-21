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
@pytest.mark.parametrize("currency", ["USD", "KRW"])
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


def test_rule_based_shoppers_buy_in_a_generated_store():
    import json
    from pathlib import Path
    sample = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"
    personas = [Persona.model_validate(p) for p in json.loads((sample / "personas.json").read_text())]
    cfg = apply_options(local_config(), RunOptions(engine_type=EngineType.RULE_BASED, seed=1))
    store = generate_store("campus_cvs", seed=1)
    agg, _, _ = asyncio.run(run_simulation(cfg, store, subsample_personas(personas, 200, 1)))
    assert agg.summary.conversion_rate > 0.5 and agg.summary.units_sold > 100


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
