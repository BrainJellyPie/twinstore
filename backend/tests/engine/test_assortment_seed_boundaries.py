"""Safe browser seed boundaries reproduce products without moving the floor plan."""
import pytest
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.validation import validate

SEEDS = [-9007199254740991, -42, -1, 0, 1, 9007199254740990, 9007199254740991]
FORMATS = ["hypermarket", "community_pharmacy", "pet_superstore", "sports_outlet", "thai_kitchen", "turkish_cafe"]


def geometry(store):
    return [(r.type, r.position, r.shape, r.rotation) for r in store.racks]


def products(store):
    return {r.rack_desc: {item.sku for rack in store.product_racks if rack.rack_desc == r.rack_desc
                        for slot in rack.slots for item in slot.items} for r in store.product_racks}


@pytest.mark.parametrize("template", FORMATS)
@pytest.mark.parametrize("seed", SEEDS)
def test_exact_seed_repeats_across_currencies_without_moving_fixtures(template, seed):
    options = LayoutOptions(products_per_category=3, width=32, height=28,
        table_clearance_x=1, table_clearance_y=2, table_rotation=90)
    store = generate_store(template, seed=seed, options=options)
    assert validate(store) == []
    assert store == generate_store(template, seed=seed, options=options)
    assert geometry(store) == geometry(generate_store(template, seed=0, options=options))
    for currency in ["KRW", "JPY"]:
        converted = generate_store(template, seed=seed, currency=currency, options=options)
        assert geometry(converted) == geometry(store)
        assert products(converted) == products(store)


@pytest.mark.parametrize("template", FORMATS)
def test_selecting_a_new_seed_changes_limited_assortment_and_restoring_recreates_it(template):
    options = LayoutOptions(products_per_category=2)
    original = generate_store(template, seed=-42, options=options)
    other = generate_store(template, seed=-41, options=options)
    assert products(original) != products(other)
    assert original == generate_store(template, seed=-42, options=options)
