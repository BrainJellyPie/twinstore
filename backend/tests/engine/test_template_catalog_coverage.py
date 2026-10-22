"""The ready-made maps expose the expanded catalog without a model call."""

import pytest

from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("seed", [0, 7, 42])
def test_default_maps_collectively_stock_every_catalog_product_and_photo(currency, seed):
    expected = {catalog_slot_item(product, currency).sku: catalog_slot_item(product, currency)
                for products in CATALOG.values() for product in products}
    stocked = {}
    categories = set()
    for template in TEMPLATES:
        store = generate_store(template.id, currency=currency, seed=seed)
        items = [item for rack in store.product_racks for slot in rack.slots for item in slot.items]
        assert any(item.image_url for item in items), template.id
        categories.update(rack.rack_desc for rack in store.product_racks)
        for item in items:
            assert item == expected[item.sku], (template.id, item.sku)
            stocked[item.sku] = item
    assert categories == set(CATALOG)
    assert stocked == expected


DEPARTMENTS = [
    ("toy_hobby_store", {"toy_vehicles", "plush_toys", "educational_toys", "puzzle_games",
                         "model_building_supplies", "miniature_painting"}),
    ("baby_family_store", {"baby_care", "baby_feeding", "baby_bath", "plush_toys"}),
    ("community_pharmacy", {"first_aid_tools", "oral_care", "nutrition_supplements"}),
    ("specialty_cafe", {"home_coffee_tea", "barista_tools"}),
    ("design_showroom", {"home_linen", "dinnerware", "home_lighting", "bathroom_accessories"}),
    ("electronics_shop", {"digital_accessories", "computer_peripherals", "photography_accessories"}),
    ("pet_superstore", {"aquarium_supplies", "aquarium_decor", "bird_supplies", "pet_grooming"}),
    ("art_supply_warehouse", {"fine_art_supplies", "sewing_textiles", "woodcraft_supplies",
                              "ceramic_craft_supplies", "miniature_painting"}),
]


@pytest.mark.parametrize("template_id,departments", DEPARTMENTS)
def test_new_departments_are_stocked_in_their_matching_format(template_id, departments):
    store = generate_store(template_id)
    assert departments <= {rack.rack_desc for rack in store.product_racks}
    for category in departments:
        items = [item for rack in store.product_racks if rack.rack_desc == category
                 for slot in rack.slots for item in slot.items]
        assert any(item.image_url for item in items)


@pytest.mark.parametrize("template_id,departments", DEPARTMENTS)
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_new_departments_respect_exclusions_limits_and_small_floor_space(template_id, departments, currency):
    before = generate_store(template_id, currency=currency)
    excluded = sorted(departments)[0]
    options = LayoutOptions(width=8, height=6, dining_tables=0, checkouts=1,
                            excluded_categories=[excluded], products_per_category=1,
                            category_product_limits={category: 2 for category in departments})
    store = generate_store(template_id, currency=currency, options=options)
    assert validate(store) == []
    assert store.product_racks
    assert excluded not in {rack.rack_desc for rack in store.product_racks}
    for rack in store.product_racks:
        skus = {item.sku for other in store.product_racks if other.rack_desc == rack.rack_desc
                for slot in other.slots for item in slot.items}
        assert len(skus) <= (2 if rack.rack_desc in departments else 1)
    assert generate_store(template_id, currency=currency, options=options) == store
    assert generate_store(template_id, currency=currency) == before


@pytest.mark.parametrize("template_id,category", [
    ("tea_lounge", "tea_menu"), ("burger_shop", "burger_menu"),
    ("noodle_bar", "noodle_menu"), ("quick_service", "restaurant_menu"),
    ("sushi_shop", "sushi_menu"), ("bubble_tea_cafe", "bubble_tea_menu"),
    ("ice_cream_parlor", "scoop_menu"), ("turkish_cafe", "turkish_menu"),
    ("pizzeria", "pizza_menu"), ("salad_cafe", "salad_menu"), ("juice_bar", "juice_menu"),
    ("indian_curry_house", "indian_menu"), ("thai_kitchen", "thai_menu"),
    ("korean_restaurant", "korean_menu"), ("mediterranean_deli", "mediterranean_menu"),
    ("mexican_cantina", "mexican_menu"), ("vietnamese_cafe", "vietnamese_menu"),
    ("specialty_cafe", "cafe_menu"),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_default_menu_maps_stock_their_complete_photographed_menu(template_id, category, currency):
    expected = {catalog_slot_item(product, currency).sku: catalog_slot_item(product, currency)
                for product in CATALOG[category]}
    store = generate_store(template_id, currency=currency)
    stocked = {item.sku: item for rack in store.product_racks if rack.rack_desc == category
               for slot in rack.slots for item in slot.items}
    assert stocked == expected
    assert all(item.image_url for item in stocked.values())


@pytest.mark.parametrize("template_id", ["wellness_pharmacy", "care_supply_store", "round_the_clock_pharmacy"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_default_care_maps_stock_complete_photographed_care_departments(template_id, currency):
    store = generate_store(template_id, currency=currency)
    for category in ["first_aid_tools", "nutrition_supplements", "oral_care", "care_supplies", "bath_body", "pharmacy_care"]:
        expected = {catalog_slot_item(product, currency).sku: catalog_slot_item(product, currency)
                    for product in CATALOG[category]}
        stocked = {item.sku: item for rack in store.product_racks if rack.rack_desc == category
                   for slot in rack.slots for item in slot.items}
        assert stocked == expected, (template_id, category)
        assert all(item.image_url for item in stocked.values()), (template_id, category)


@pytest.mark.parametrize("template_id,category", [
    ("wellness_pharmacy", "health_beauty"), ("wellness_pharmacy", "wellness"),
    ("wellness_pharmacy", "baby_care"), ("wellness_pharmacy", "hair_care"),
    ("pet_superstore", "pet_care"), ("pet_superstore", "pet_enrichment"),
    ("organic_market", "plant_based"), ("urban_cvs", "artisan_snacks"),
    ("urban_cvs", "craft_refreshments"), ("gas_station", "car_care"),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_default_everyday_maps_stock_complete_photographed_departments(template_id, category, currency):
    store = generate_store(template_id, currency=currency)
    expected = {catalog_slot_item(product, currency).sku: catalog_slot_item(product, currency)
                for product in CATALOG[category]}
    stocked = {item.sku: item for rack in store.product_racks if rack.rack_desc == category
               for slot in rack.slots for item in slot.items}
    assert stocked == expected
    assert all(item.image_url for item in stocked.values())


@pytest.mark.parametrize("template_id,category", [
    ("urban_cvs", "dairy"), ("campus_cvs", "fresh_meals"), ("specialty_cafe", "desserts"),
    ("organic_market", "breakfast_spreads"), ("specialty_cafe", "home_coffee_tea"),
    ("artisan_bakery", "baking_ingredients"), ("hypermarket", "frozen_meals"),
    ("hypermarket", "fresh_seafood"), ("specialty_cafe", "barista_tools"),
])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_default_food_maps_stock_complete_photographed_departments(template_id, category, currency):
    store = generate_store(template_id, currency=currency)
    expected = {catalog_slot_item(product, currency).sku: catalog_slot_item(product, currency)
                for product in CATALOG[category]}
    stocked = {item.sku: item for rack in store.product_racks if rack.rack_desc == category
               for slot in rack.slots for item in slot.items}
    assert stocked == expected
    assert all(item.image_url for item in stocked.values())


@pytest.mark.parametrize("template_id,category", [('urban_cvs', 'household'), ('bookstore', 'stationery'), ('tourist_shop', 'souvenirs'), ('urban_cvs', 'checkout_impulse'), ('cafe_bakery', 'coffee_station'), ('organic_market', 'pantry'), ('bookstore', 'books'), ('electronics_shop', 'electronics'), ('design_showroom', 'home_design'), ('sports_store', 'sports'), ('hardware_store', 'hardware'), ('music_store', 'music_gear'), ('garden_center', 'garden_supplies'), ('design_showroom', 'kitchen_tools'), ('refill_market', 'laundry_care'), ('florist', 'flowers')])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_default_essentials_maps_stock_complete_photographed_departments(template_id, category, currency):
    store = generate_store(template_id, currency=currency)
    expected = {catalog_slot_item(product, currency).sku: catalog_slot_item(product, currency)
                for product in CATALOG[category]}
    stocked = {item.sku: item for rack in store.product_racks if rack.rack_desc == category
               for slot in rack.slots for item in slot.items}
    assert stocked == expected
    assert all(item.image_url for item in stocked.values())
