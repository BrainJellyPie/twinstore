"""Per-category assortment limits preserve geometry and seeded product identity."""
import pytest
from pydantic import ValidationError
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG
from store_emulator.engine.validation import validate


def products(store, category):
    return {item.sku: (item.name, item.price) for rack in store.product_racks if rack.rack_desc == category
            for slot in rack.slots for item in slot.items}


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.id)
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_category_limits_override_shared_depth_without_changing_geometry_or_product_identity(template, currency):
    categories = sorted(set(template.fridges + template.freezers + template.wall_shelves + template.gondolas + template.near_counter))
    limits = {category: [1, 4, 16][index % 3] for index, category in enumerate(categories) if index % 4 != 3}
    full = generate_store(template.id, seed=24, currency=currency)
    options = LayoutOptions(products_per_category=3, category_product_limits=limits)
    focused = generate_store(template.id, seed=24, currency=currency, options=options)
    assert validate(focused) == []
    assert [rack.model_dump(exclude={"slots"}) for rack in focused.racks] == [rack.model_dump(exclude={"slots"}) for rack in full.racks]
    for category in {rack.rack_desc for rack in focused.product_racks}:
        selected, original = products(focused, category), products(full, category)
        assert len(selected) == min(limits.get(category, 3), len(CATALOG[category]))
        assert all(original[sku] == item for sku, item in selected.items())
    assert focused == generate_store(template.id, seed=24, currency=currency, options=options)
    assert options.category_product_limits == limits


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.id)
@pytest.mark.parametrize("limit", [1, 4, 16])
def test_identical_category_limits_match_the_existing_shared_limit_exactly(template, limit):
    categories = set(template.fridges + template.freezers + template.wall_shelves + template.gondolas + template.near_counter)
    assert generate_store(template.id, seed=7, options=LayoutOptions(products_per_category=limit)) == generate_store(
        template.id, seed=7, options=LayoutOptions(category_product_limits={category: limit for category in categories}))


@pytest.mark.parametrize("value", [0, -1, 17, 1.5, True, False, "3", None, float("nan"), float("inf"), [], {}])
def test_limits_require_strict_bounded_integers(value):
    with pytest.raises(ValidationError):
        LayoutOptions(category_product_limits={"soft_drinks": value})


@pytest.mark.parametrize("limits", [{"": 1}, {"x" * 81: 1}, {f"c{i}": 1 for i in range(65)}, None, []])
def test_limits_require_a_bounded_map_of_category_identifiers(limits):
    with pytest.raises(ValidationError):
        LayoutOptions(category_product_limits=limits)


def test_unknown_limits_are_rejected_even_when_excluded_and_known_unused_limits_are_harmless():
    with pytest.raises(ValueError, match="Unknown product categories in assortment limits: imaginary"):
        generate_store("community_pharmacy", options=LayoutOptions(category_product_limits={"imaginary": 2}, excluded_categories=["imaginary"]))
    assert generate_store("community_pharmacy") == generate_store(
        "community_pharmacy", options=LayoutOptions(category_product_limits={"mexican_menu": 12}))


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_excluded_limits_are_retained_and_seeded_subsets_survive_size_direction_and_currency(currency):
    limits = {"mexican_menu": 3, "desserts": 1}
    baseline = generate_store("mexican_cantina", seed=13, options=LayoutOptions(category_product_limits=limits))
    options = LayoutOptions(width=32, height=24, shelf_direction="vertical", excluded_categories=["desserts"],
                            products_per_category=1, category_product_limits=limits)
    changed = generate_store("mexican_cantina", seed=13, currency=currency, options=options)
    assert set(products(baseline, "mexican_menu")) == set(products(changed, "mexican_menu"))
    assert not products(changed, "desserts") and options.category_product_limits == limits
    assert validate(changed) == []
    shuffled = generate_store("mexican_cantina", seed=14, options=LayoutOptions(category_product_limits=limits))
    assert set(products(baseline, "mexican_menu")) != set(products(shuffled, "mexican_menu"))


def test_empty_overrides_and_separate_default_maps_preserve_legacy_behavior():
    first, second = LayoutOptions(), LayoutOptions()
    first.category_product_limits["soft_drinks"] = 1
    assert second.category_product_limits == {}
    assert generate_store("urban_cvs") == generate_store("urban_cvs", options=second)
