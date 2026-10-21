"""Store-format templates and a procedural layout generator.

Each template describes a real-world retail format (urban convenience store, campus store,
station kiosk, gas-station shop, drugstore, mini-mart, café-bakery, office lobby, tourist shop)
by its grid size, which categories go into wall fridges / wall shelves / island gondolas, and an
assortment depth. The generator lays the store out the way such shops usually are:

- reach-in fridges along the back wall (cold drinks, dairy, beer), freezers near them;
- wall shelves on the side wall, two-sided gondolas in parallel island rows with aisles between;
- entrance and counter at the front, a checkout-treats rack by the counter, coffee station near it;
- eye level (level 3) holds the best-selling items of each category, bottom shelves the bulk packs.

The result always passes `engine.validation.validate` without errors (checked by tests).
"""

import random
from dataclasses import dataclass, field, replace
from typing import Literal

from store_emulator.domain.layout_options import CheckoutPlacement, LayoutOptions, LayoutStyle, SeatingZone, StoreDesign
from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Face, Weekday, stable_seed

from .catalog import CATALOG, CatalogItem, category_label, catalog_slot_item

@dataclass(frozen=True)
class StoreTemplate:
    id: str
    name: str
    description: str
    store_type: str
    grid: tuple[int, int]
    fridges: list[str]                 # back-wall reach-in fridges, in order
    freezers: list[str] = field(default_factory=list[str])
    wall_shelves: list[str] = field(default_factory=list[str])
    gondolas: list[str] = field(default_factory=list[str])
    near_counter: list[str] = field(default_factory=lambda: ["checkout_impulse"])
    open_hours: tuple[int, int] = (0, 24)
    closed_days: tuple[int, ...] = ()
    style: LayoutStyle = "aisles"
    dining_tables: int = 0
    checkouts: int = 1
    seating_zone: SeatingZone = "auto"
    checkout_placement: CheckoutPlacement = "auto"
    design_theme: StoreDesign | None = None


TEMPLATES: list[StoreTemplate] = [
    StoreTemplate(
        id="urban_cvs", name="Urban convenience store", description="Typical 24h city convenience store: drinks wall, snacks and instant food islands, fresh lunch fridge.",
        store_type="convenience", grid=(12, 10),
        fridges=["soft_drinks", "soft_drinks", "water_sports", "energy_coffee", "dairy", "beer_alcohol", "fresh_meals"],
        freezers=["ice_cream"], wall_shelves=["household", "health_beauty", "bakery"],
        gondolas=["chips", "chips", "sweets", "instant_food", "instant_food", "sweets"],
        near_counter=["checkout_impulse", "coffee_station"],
    ),
    StoreTemplate(
        id="compact_cvs", name="Compact street-corner store", description="Small 8×8 shop: few fridges, one island, everything within a few steps.",
        store_type="convenience", grid=(8, 8),
        fridges=["soft_drinks", "water_sports", "dairy", "beer_alcohol"], freezers=["ice_cream"],
        wall_shelves=["household"], gondolas=["chips", "instant_food"], open_hours=(6, 24),
    ),
    StoreTemplate(
        id="campus_cvs", name="University campus store", description="Student traffic: energy drinks, instant noodles, rice balls, stationery and cheap snacks.",
        store_type="convenience", grid=(12, 12),
        fridges=["energy_coffee", "energy_coffee", "soft_drinks", "water_sports", "dairy", "fresh_meals", "fresh_meals"],
        freezers=["ice_cream"], wall_shelves=["stationery", "health_beauty", "bakery"],
        gondolas=["instant_food", "instant_food", "chips", "sweets", "chips", "instant_food"],
        near_counter=["checkout_impulse", "coffee_station"], open_hours=(7, 24),
    ),
    StoreTemplate(
        id="station_kiosk", name="Station kiosk", description="Grab-and-go in a transit station: drinks, sandwiches, gum — tiny footprint, peak hours.",
        store_type="convenience", grid=(8, 6),
        fridges=["soft_drinks", "water_sports", "energy_coffee", "fresh_meals"],
        wall_shelves=["sweets"], gondolas=["chips"], open_hours=(5, 24),
    ),
    StoreTemplate(
        id="gas_station", name="Gas-station shop", description="Drivers' stop: coffee, energy drinks, snacks, car care and household basics.",
        store_type="convenience", grid=(10, 8),
        fridges=["soft_drinks", "energy_coffee", "water_sports", "dairy", "beer_alcohol"], freezers=["ice_cream"],
        wall_shelves=["car_care", "household"], gondolas=["chips", "sweets", "instant_food"],
        near_counter=["checkout_impulse", "coffee_station"],
    ),
    StoreTemplate(
        id="drugstore", name="Health & beauty drugstore", description="Beauty and health aisles with a small drinks fridge.",
        store_type="pharmacy", grid=(12, 10),
        fridges=["water_sports", "energy_coffee", "dairy"],
        wall_shelves=["health_beauty", "health_beauty", "household"],
        gondolas=["health_beauty", "health_beauty", "health_beauty", "sweets", "household", "health_beauty"],
        open_hours=(9, 22),
    ),
    StoreTemplate(
        id="mini_mart", name="Neighborhood mini-mart", description="Groceries for nearby homes: produce, dairy, instant food, household goods, beer.",
        store_type="supermarket", grid=(14, 12),
        fridges=["dairy", "dairy", "soft_drinks", "water_sports", "beer_alcohol", "beer_alcohol", "fresh_meals", "fresh_produce"],
        freezers=["ice_cream", "ice_cream"], wall_shelves=["household", "household", "health_beauty", "bakery"],
        gondolas=["instant_food", "instant_food", "chips", "sweets", "instant_food", "chips", "fresh_produce", "sweets"],
        open_hours=(8, 23), style="loop",
    ),
    StoreTemplate(
        id="cafe_bakery", name="Café-bakery", description="Bakery displays and a coffee bar with a cold-drinks fridge.",
        store_type="bakery", grid=(10, 8),
        fridges=["dairy", "soft_drinks", "water_sports"], freezers=["ice_cream"],
        wall_shelves=["bakery", "bakery"], gondolas=["bakery", "bakery", "sweets"],
        near_counter=["coffee_station", "checkout_impulse"], open_hours=(7, 22), dining_tables=2,
    ),
    StoreTemplate(
        id="office_lobby", name="Office-tower lobby store", description="Weekday office crowd: coffee, salads, sandwiches, snacks; closed on weekends.",
        store_type="convenience", grid=(10, 8),
        fridges=["energy_coffee", "fresh_meals", "fresh_meals", "water_sports", "dairy"],
        wall_shelves=["health_beauty"], gondolas=["chips", "sweets", "instant_food"],
        near_counter=["coffee_station", "checkout_impulse"], open_hours=(7, 21), closed_days=(6, 7),
    ),
    StoreTemplate(
        id="tourist_shop", name="Tourist-area store", description="Visitors: water, sunscreen, souvenirs, local snacks, beer.",
        store_type="convenience", grid=(12, 10),
        fridges=["water_sports", "soft_drinks", "beer_alcohol", "beer_alcohol", "dairy"], freezers=["ice_cream"],
        wall_shelves=["souvenirs", "health_beauty"], gondolas=["souvenirs", "chips", "sweets", "instant_food"],
        open_hours=(7, 24),
    ),
    StoreTemplate(
        id="hypermarket", name="Large-format hypermarket", description="A 32×26 grocery anchor with pantry aisles, fresh food, household departments and a broad cold wall.",
        store_type="supermarket", grid=(32, 26), fridges=["dairy", "fresh_produce", "fresh_meals", "soft_drinks", "water_sports", "beer_alcohol"] * 3,
        freezers=["ice_cream"] * 4, wall_shelves=["household", "pet_care", "health_beauty"] * 4,
        gondolas=["pantry", "pantry", "instant_food", "household", "chips", "sweets", "pet_care"], open_hours=(8, 23), checkouts=6,
    ),
    StoreTemplate(
        id="warehouse_club", name="Warehouse club", description="Large 36×28 bulk-shopping floor with long sightlines and a central spine.",
        store_type="supermarket", grid=(36, 28), fridges=["dairy", "fresh_meals", "water_sports"] * 6,
        freezers=["ice_cream"] * 4, wall_shelves=["household", "car_care", "electronics"] * 4,
        gondolas=["pantry", "household", "pet_care", "water_sports", "chips"], style="spine", open_hours=(9, 21), checkouts=8,
    ),
    StoreTemplate(
        id="organic_market", name="Organic neighborhood market", description="Produce, pantry essentials and chilled meals around a generous circulation loop.",
        store_type="supermarket", grid=(18, 16), fridges=["fresh_produce", "dairy", "fresh_meals"] * 3,
        wall_shelves=["pantry", "pantry", "household"], gondolas=["fresh_produce", "pantry", "bakery"], style="loop", open_hours=(8, 21), checkouts=2,
    ),
    StoreTemplate(
        id="community_pharmacy", name="Community pharmacy", description="First aid, OTC care and wellness displays with a front service counter. No prescription dispensing is modeled.",
        store_type="pharmacy", grid=(14, 12), fridges=["water_sports"],
        wall_shelves=["pharmacy_care", "wellness", "health_beauty"], gondolas=["pharmacy_care", "wellness", "pharmacy_care", "health_beauty"],
        near_counter=["wellness"], open_hours=(9, 21),
    ),
    StoreTemplate(
        id="wellness_pharmacy", name="Wellness & care pharmacy", description="Spacious care departments connected by a clear central spine; first aid, personal care and wellness.",
        store_type="pharmacy", grid=(20, 16), fridges=["water_sports", "dairy"],
        wall_shelves=["pharmacy_care", "wellness", "health_beauty"] * 2, gondolas=["wellness", "pharmacy_care", "health_beauty"],
        near_counter=["wellness"], style="spine", open_hours=(8, 22), checkouts=2,
    ),
    StoreTemplate(
        id="specialty_cafe", name="Specialty coffee bar", description="Coffee menu and pastry displays with an open center. Models counter purchases; seating service is not simulated.",
        store_type="cafe", grid=(12, 10), fridges=["dairy", "soft_drinks"], wall_shelves=["cafe_menu", "bakery"],
        gondolas=["desserts", "cafe_menu"], near_counter=["cafe_menu", "desserts"], style="perimeter", open_hours=(7, 20), dining_tables=4,
    ),
    StoreTemplate(
        id="book_cafe", name="Bookshop café", description="Browsing islands for books and stationery plus a coffee and cake counter.",
        store_type="cafe", grid=(18, 14), fridges=["dairy", "soft_drinks"], wall_shelves=["books", "books", "stationery"],
        gondolas=["books", "books", "stationery"], near_counter=["cafe_menu", "desserts"], style="free_flow", open_hours=(9, 22), dining_tables=4,
    ),
    StoreTemplate(
        id="dessert_cafe", name="Dessert & tea café", description="Small dessert displays, tea and coffee with a spacious showroom arrangement.",
        store_type="cafe", grid=(14, 12), fridges=["dairy", "desserts"], wall_shelves=["bakery", "cafe_menu"],
        gondolas=["desserts", "bakery"], near_counter=["cafe_menu", "desserts"], style="showroom", open_hours=(10, 22), dining_tables=4,
    ),
    StoreTemplate(
        id="quick_service", name="Quick-service restaurant", description="Menu displays and pickup counter for lunch orders. Counter ordering is modeled, not kitchen preparation or table service.",
        store_type="restaurant", grid=(14, 10), fridges=["soft_drinks", "water_sports"], wall_shelves=["restaurant_menu"],
        gondolas=["restaurant_menu", "desserts"], near_counter=["restaurant_menu", "desserts"], style="perimeter", open_hours=(10, 23), dining_tables=4,
    ),
    StoreTemplate(
        id="food_hall", name="Food hall & deli", description="Several food and beverage displays around a central circulation spine; use multiple checkout counters for service points.",
        store_type="restaurant", grid=(26, 20), fridges=["fresh_meals", "soft_drinks", "dairy"] * 3,
        wall_shelves=["restaurant_menu", "bakery", "cafe_menu"] * 2, gondolas=["restaurant_menu", "fresh_meals", "desserts", "bakery"],
        near_counter=["cafe_menu", "desserts"], style="spine", open_hours=(10, 22), dining_tables=8, checkouts=4,
    ),
    StoreTemplate(
        id="fashion_boutique", name="Fashion boutique", description="Curated apparel and accessories on free-flow display islands with perimeter collections.",
        store_type="fashion", grid=(16, 14), fridges=[], wall_shelves=["apparel"] * 5,
        gondolas=["apparel", "souvenirs"], near_counter=["apparel"], style="free_flow", open_hours=(10, 21),
    ),
    StoreTemplate(
        id="campus_dining_hall", name="Campus dining hall", description="A large weekday dining floor with 24 four-seat tables, perimeter meal displays and four checkout counters. Models counter purchases; kitchen and table service are not simulated.",
        store_type="restaurant", grid=(32, 24), fridges=["water_sports", "soft_drinks", "dairy"] * 2,
        wall_shelves=["restaurant_menu", "bakery", "desserts"] * 3,
        gondolas=["restaurant_menu", "fresh_meals", "bakery"], near_counter=["cafe_menu", "desserts"],
        style="perimeter", open_hours=(7, 21), closed_days=(6, 7), dining_tables=24, checkouts=4,
        seating_zone="center", design_theme="minimal",
    ),
    StoreTemplate(
        id="design_showroom", name="Home & design showroom", description="Separated homeware display groups with wide sightlines and perimeter collections.",
        store_type="home", grid=(24, 20), fridges=[], wall_shelves=["home_design"] * 8,
        gondolas=["home_design", "home_design", "flowers"], near_counter=["home_design"], style="showroom", open_hours=(10, 20),
    ),
    StoreTemplate(
        id="beauty_flagship", name="Beauty flagship", description="Beauty collections and wellness stations along a spacious discovery loop.",
        store_type="beauty", grid=(22, 18), fridges=[], wall_shelves=["health_beauty", "wellness"] * 4,
        gondolas=["health_beauty", "wellness", "health_beauty"], near_counter=["health_beauty"], style="loop", open_hours=(10, 22),
    ),
    StoreTemplate(
        id="bookstore", name="Independent bookstore", description="Book departments, stationery and gifts with a central discovery aisle.",
        store_type="books", grid=(18, 16), fridges=[], wall_shelves=["books"] * 8,
        gondolas=["books", "books", "stationery", "souvenirs"], near_counter=["stationery"], style="spine", open_hours=(10, 21),
    ),
    StoreTemplate(
        id="electronics_shop", name="Electronics experience store", description="Device and accessory displays organized as separated showroom islands.",
        store_type="electronics", grid=(20, 16), fridges=[], wall_shelves=["electronics"] * 6,
        gondolas=["electronics"], near_counter=["electronics"], style="showroom", open_hours=(10, 21),
    ),
    StoreTemplate(
        id="pet_store", name="Pet supplies store", description="Pet food, treats and care products with clear parallel shopping aisles.",
        store_type="pets", grid=(16, 12), fridges=[], wall_shelves=["pet_care"] * 5,
        gondolas=["pet_care", "household"], near_counter=["pet_care"], open_hours=(9, 21),
    ),
    StoreTemplate(
        id="sports_store", name="Sports & outdoor store", description="Fitness accessories and apparel departments along a racetrack route.",
        store_type="sports", grid=(22, 18), fridges=["water_sports"], wall_shelves=["sports", "apparel"] * 4,
        gondolas=["sports", "apparel", "sports"], near_counter=["sports"], style="loop", open_hours=(10, 21),
    ),
    StoreTemplate(
        id="florist", name="Flower & gift studio", description="Compact seasonal flower and gift displays with an open browsing center.",
        store_type="flowers", grid=(12, 10), fridges=[], wall_shelves=["flowers", "home_design", "souvenirs"],
        gondolas=["flowers"], near_counter=["flowers"], style="perimeter", open_hours=(9, 20),
    ),
    StoreTemplate(
        id="family_restaurant", name="Family restaurant", description="A broad dining floor with eight central tables, perimeter menu displays and a checkout near the entrance. Counter purchases are modeled; table service is not.",
        store_type="restaurant", grid=(24, 20), fridges=["soft_drinks", "water_sports", "dairy", "desserts"],
        wall_shelves=["restaurant_menu", "desserts", "cafe_menu"] * 2, gondolas=["restaurant_menu"],
        near_counter=["restaurant_menu", "desserts"], style="perimeter", open_hours=(11, 22), dining_tables=8,
        seating_zone="center", checkout_placement="near_entrance", design_theme="warm",
    ),
    StoreTemplate(
        id="neighborhood_bistro", name="Neighborhood bistro", description="Six tables toward the back of a compact dining room, with charcoal-and-brass finishes and menu displays. No kitchen or table-service simulation.",
        store_type="restaurant", grid=(16, 14), fridges=["soft_drinks", "desserts"],
        wall_shelves=["restaurant_menu", "restaurant_menu", "cafe_menu"], gondolas=["restaurant_menu"],
        near_counter=["restaurant_menu", "desserts"], style="perimeter", open_hours=(11, 23), closed_days=(1,),
        dining_tables=6, seating_zone="back", design_theme="luxury",
    ),
    StoreTemplate(
        id="takeaway_coffee", name="Takeaway coffee kiosk", description="A compact coffee stop with no seating, an entrance-side checkout, industrial finishes and pastry displays.",
        store_type="cafe", grid=(10, 8), fridges=["dairy", "soft_drinks"],
        wall_shelves=["cafe_menu", "bakery", "desserts"], gondolas=["cafe_menu", "bakery"],
        near_counter=["cafe_menu", "desserts"], style="perimeter", open_hours=(6, 19),
        checkout_placement="near_entrance", design_theme="industrial",
    ),
    StoreTemplate(
        id="tea_lounge", name="Tea lounge & gift shop", description="Six tables along the right side, botanical finishes, tea menus and small tea gifts on browsing islands.",
        store_type="cafe", grid=(18, 16), fridges=["soft_drinks", "desserts"],
        wall_shelves=["tea_menu", "tea_menu", "home_design", "desserts"], gondolas=["tea_menu", "home_design"],
        near_counter=["tea_menu", "desserts"], style="free_flow", open_hours=(10, 22), dining_tables=6,
        seating_zone="right", design_theme="botanical",
    ),
    StoreTemplate(
        id="artisan_bakery", name="Artisan bakery", description="Warm bread and pastry displays on a browsing loop, with two small dining groups near the front.",
        store_type="bakery", grid=(16, 12), fridges=["dairy", "soft_drinks", "desserts"],
        wall_shelves=["bakery", "bakery", "desserts"], gondolas=["bakery", "desserts"],
        near_counter=["cafe_menu", "bakery"], style="loop", open_hours=(6, 20), dining_tables=2,
        seating_zone="front", design_theme="warm",
    ),
    StoreTemplate(
        id="vintage_boutique", name="Vintage-inspired boutique", description="Warm wood, apparel, accessories and gift displays on a free-flow floor, with checkout away from the entrance.",
        store_type="fashion", grid=(16, 14), fridges=[], wall_shelves=["apparel", "souvenirs", "apparel", "apparel"],
        gondolas=["apparel", "souvenirs"], near_counter=["apparel"], style="free_flow", open_hours=(11, 20),
        checkout_placement="away_from_entrance", design_theme="warm",
    ),
    StoreTemplate(
        id="hardware_store", name="Hardware & home repair store", description="Tool and home-repair aisles with industrial finishes, household essentials and an accessory wall.",
        store_type="hardware", grid=(24, 18), fridges=[], wall_shelves=["hardware", "household", "electronics"] * 3,
        gondolas=["hardware", "hardware", "household"], near_counter=["hardware"], open_hours=(7, 21), design_theme="industrial",
    ),
    StoreTemplate(
        id="toy_hobby_store", name="Toy & hobby store", description="Games, puzzles, craft supplies and books on a free-flow discovery floor with bright minimal finishes.",
        store_type="toys", grid=(20, 16), fridges=[], wall_shelves=["toys_hobbies", "books", "stationery"] * 2,
        gondolas=["toys_hobbies", "toys_hobbies", "stationery"], near_counter=["toys_hobbies"],
        style="free_flow", open_hours=(10, 21), design_theme="minimal",
    ),
    StoreTemplate(
        id="shoe_boutique", name="Footwear boutique", description="Footwear collections, shoe-care accessories and apparel arranged in showroom groups with charcoal and brass finishes.",
        store_type="fashion", grid=(22, 16), fridges=[], wall_shelves=["footwear", "footwear", "apparel"] * 2,
        gondolas=["footwear", "footwear", "sports"], near_counter=["footwear"], style="showroom",
        open_hours=(10, 21), checkouts=2, checkout_placement="away_from_entrance", design_theme="luxury",
    ),
    StoreTemplate(
        id="baby_family_store", name="Baby & family store", description="Baby essentials, clothing, books and family gifts along a central spine with warm wood finishes and two checkout counters.",
        store_type="baby", grid=(24, 18), fridges=[], wall_shelves=["baby_supplies", "apparel", "books"] * 3,
        gondolas=["baby_supplies", "baby_supplies", "toys_hobbies"], near_counter=["baby_supplies", "toys_hobbies"],
        style="spine", open_hours=(9, 21), checkouts=2, design_theme="warm",
    ),
    StoreTemplate(
        id="travel_essentials", name="Travel essentials shop", description="Travel bags, packing accessories, chargers and personal-care supplies in compact aisles with checkout near the entrance.",
        store_type="travel", grid=(18, 12), fridges=["water_sports", "soft_drinks"],
        wall_shelves=["travel_gear", "electronics", "health_beauty"] * 2,
        gondolas=["travel_gear", "travel_gear", "electronics"], near_counter=["travel_gear", "health_beauty"],
        open_hours=(6, 23), checkouts=2, checkout_placement="near_entrance", design_theme="industrial",
    ),
    StoreTemplate(
        id="garden_center", name="Garden & outdoor center", description="Plants, growing supplies and garden tools on a large botanical floor with clear central cross aisles and four checkout counters.",
        store_type="garden", grid=(32, 26), fridges=[], wall_shelves=["garden_supplies", "flowers", "home_design"] * 4,
        gondolas=["garden_supplies", "garden_supplies", "flowers", "home_design"], near_counter=["garden_supplies", "flowers"],
        style="cross", open_hours=(8, 20), checkouts=4, design_theme="botanical",
    ),
    StoreTemplate(
        id="art_craft_store", name="Art & craft supply store", description="Painting, drawing and craft materials around intersecting central aisles, with stationery and books along warm wood walls.",
        store_type="crafts", grid=(22, 18), fridges=[], wall_shelves=["art_craft", "stationery", "books"] * 3,
        gondolas=["art_craft", "art_craft", "stationery"], near_counter=["art_craft"],
        style="cross", open_hours=(10, 21), checkouts=2, design_theme="warm",
    ),
    StoreTemplate(
        id="optical_shop", name="Optical & eyewear shop", description="Frames, sunglasses and eyewear accessories in minimal showroom groups with two service counters. Models retail purchases; eye exams and lens fitting are not simulated.",
        store_type="eyewear", grid=(20, 16), fridges=[], wall_shelves=["eyewear"] * 6,
        gondolas=["eyewear", "eyewear", "travel_gear"], near_counter=["eyewear"],
        style="showroom", open_hours=(10, 21), checkouts=2, checkout_placement="away_from_entrance", design_theme="minimal",
    ),
    StoreTemplate(
        id="jewelry_boutique", name="Jewelry & accessories boutique", description="A compact luxury showroom for jewelry, watches and gift accessories, with two checkout counters away from the entrance.",
        store_type="jewelry", grid=(16, 12), fridges=[], wall_shelves=["jewelry"] * 5,
        gondolas=["jewelry", "jewelry", "souvenirs"], near_counter=["jewelry"],
        style="showroom", open_hours=(10, 20), checkouts=2, checkout_placement="away_from_entrance", design_theme="luxury",
    ),
    StoreTemplate(
        id="music_store", name="Music & instrument store", description="Instruments, practice gear and audio accessories on free-flow display islands with industrial finishes and two checkout counters.",
        store_type="music", grid=(24, 18), fridges=[], wall_shelves=["music_gear", "electronics", "music_gear"] * 3,
        gondolas=["music_gear", "music_gear", "electronics"], near_counter=["music_gear"],
        style="free_flow", open_hours=(10, 21), checkouts=2, design_theme="industrial",
    ),
    StoreTemplate(
        id="fashion_outlet", name="Large fashion outlet", description="A 32×24 apparel, footwear and bag store with a racetrack layout, coastal finishes and four checkout counters.",
        store_type="fashion", grid=(32, 24), fridges=[], wall_shelves=["apparel", "footwear", "travel_gear"] * 4,
        gondolas=["apparel", "apparel", "footwear", "travel_gear"], near_counter=["apparel", "footwear"],
        style="loop", open_hours=(10, 22), checkouts=4, design_theme="coastal",
    ),
    StoreTemplate(
        id="pizzeria", name="Neighborhood pizzeria", description="Pizza, slices and sides around a terracotta dining floor with eight four-seat tables and two ordering counters. Models counter purchases.",
        store_type="restaurant", grid=(22, 18), fridges=["soft_drinks", "water_sports", "dairy"],
        wall_shelves=["pizza_menu"] * 5, gondolas=["pizza_menu", "desserts"], near_counter=["pizza_menu", "desserts"],
        style="perimeter", open_hours=(11, 23), dining_tables=8, checkouts=2, seating_zone="center", design_theme="terracotta",
    ),
    StoreTemplate(
        id="sushi_shop", name="Sushi & roll shop", description="Sushi sets, rolls and sides in a minimal showroom layout with four four-seat tables and two counters. Models counter purchases.",
        store_type="restaurant", grid=(18, 14), fridges=["sushi_menu", "sushi_menu", "water_sports", "soft_drinks"],
        wall_shelves=["sushi_menu", "tea_menu", "sushi_menu"], gondolas=["sushi_menu"], near_counter=["sushi_menu", "tea_menu"],
        style="showroom", open_hours=(11, 22), dining_tables=4, checkouts=2, seating_zone="back", design_theme="minimal",
    ),
    StoreTemplate(
        id="noodle_bar", name="Noodle & ramen bar", description="Noodle bowls and side dishes along a warm perimeter with six four-seat tables and two ordering counters. Models counter purchases.",
        store_type="restaurant", grid=(20, 16), fridges=["soft_drinks", "water_sports", "dairy"],
        wall_shelves=["noodle_menu"] * 4, gondolas=["noodle_menu"], near_counter=["noodle_menu", "tea_menu"],
        style="perimeter", open_hours=(11, 23), dining_tables=6, checkouts=2, seating_zone="left", design_theme="warm",
    ),
    StoreTemplate(
        id="juice_bar", name="Juice & smoothie bar", description="Fruit juices, smoothies and fruit bowls in a compact botanical café with two four-seat tables. Models counter purchases.",
        store_type="cafe", grid=(12, 10), fridges=["juice_menu", "juice_menu", "water_sports"],
        wall_shelves=["juice_menu", "fresh_produce"], gondolas=["juice_menu"], near_counter=["juice_menu"],
        style="perimeter", open_hours=(7, 20), dining_tables=2, seating_zone="right", checkout_placement="near_entrance", design_theme="botanical",
    ),
    StoreTemplate(
        id="korean_restaurant", name="Korean casual restaurant", description="Rice bowls, stews and Korean sides around a warm dining floor with twelve four-seat tables and two ordering counters. Models counter purchases.",
        store_type="restaurant", grid=(26, 22), fridges=["soft_drinks", "water_sports", "dairy"],
        wall_shelves=["korean_menu"] * 6, gondolas=["korean_menu"], near_counter=["korean_menu", "tea_menu"],
        style="perimeter", open_hours=(11, 22), dining_tables=12, checkouts=2, seating_zone="center", design_theme="warm",
    ),
    StoreTemplate(
        id="burger_shop", name="Burger & fries shop", description="Burgers, fries and sides on an industrial dining floor with ten four-seat tables and three ordering counters near the entrance. Models counter purchases.",
        store_type="restaurant", grid=(24, 20), fridges=["soft_drinks", "water_sports", "dairy"],
        wall_shelves=["burger_menu"] * 5, gondolas=["burger_menu"], near_counter=["burger_menu", "desserts"],
        style="perimeter", open_hours=(10, 23), dining_tables=10, checkouts=3, seating_zone="back", checkout_placement="near_entrance", design_theme="industrial",
    ),
    StoreTemplate(
        id="salad_cafe", name="Salad & grain-bowl café", description="Salads, grain bowls and soup with botanical finishes, six four-seat tables and two ordering counters. Models counter purchases.",
        store_type="cafe", grid=(22, 18), fridges=["salad_menu", "salad_menu", "juice_menu", "water_sports"],
        wall_shelves=["salad_menu", "salad_menu", "cafe_menu"], gondolas=["salad_menu"], near_counter=["salad_menu", "cafe_menu"],
        style="free_flow", open_hours=(8, 21), dining_tables=6, checkouts=2, seating_zone="left", design_theme="botanical",
    ),
    StoreTemplate(
        id="ice_cream_parlor", name="Ice cream & gelato parlor", description="Scoops, cones, sundaes and milkshakes with coastal finishes and three four-seat tables near the front. Models counter purchases.",
        store_type="cafe", grid=(14, 12), fridges=["scoop_menu", "dairy", "water_sports"], freezers=["scoop_menu", "scoop_menu"],
        wall_shelves=["scoop_menu", "desserts"], gondolas=["scoop_menu"], near_counter=["scoop_menu"],
        style="perimeter", open_hours=(11, 22), dining_tables=3, seating_zone="front", checkout_placement="near_entrance", design_theme="coastal",
    ),
    StoreTemplate(
        id="refill_market", name="Refill & bulk grocery", description="A large 28×22 market for refill packs, pantry staples and reusable containers with broad cross aisles. Products use fixed pack prices; bulk weighing is not simulated.",
        store_type="supermarket", grid=(28, 22), fridges=["dairy", "fresh_produce", "water_sports"] * 3,
        wall_shelves=["refill_goods", "pantry", "household"] * 3, gondolas=["refill_goods", "refill_goods", "pantry"],
        near_counter=["refill_goods"], style="cross", open_hours=(8, 21), checkouts=4, design_theme="botanical",
    ),
    StoreTemplate(
        id="care_supply_store", name="Care & mobility supply store", description="Everyday care aids, mobility accessories and first-aid goods with a clear central spine and three service counters. Models retail purchases, not clinical consultations or prescription dispensing.",
        store_type="pharmacy", grid=(24, 18), fridges=["water_sports"],
        wall_shelves=["care_supplies", "pharmacy_care", "wellness"] * 2, gondolas=["care_supplies", "care_supplies", "pharmacy_care", "wellness"],
        near_counter=["care_supplies"], style="spine", open_hours=(9, 19), checkouts=3, design_theme="minimal",
    ),
    StoreTemplate(
        id="fragrance_boutique", name="Fragrance concept boutique", description="Perfumes, discovery sets and home scents in a luxury showroom with two checkout counters and open display groups.",
        store_type="beauty", grid=(16, 14), fridges=[],
        wall_shelves=["fragrances", "fragrances", "health_beauty"], gondolas=["fragrances", "fragrances", "health_beauty"],
        near_counter=["fragrances"], style="showroom", open_hours=(10, 21), checkouts=2, design_theme="luxury",
    ),
    StoreTemplate(
        id="bubble_tea_cafe", name="Bubble tea café", description="Pearl milk teas, fruit teas and desserts around a coastal café with four four-seat tables and two ordering counters. Models fixed menu purchases.",
        store_type="cafe", grid=(16, 14), fridges=["bubble_tea_menu", "dairy", "water_sports"],
        wall_shelves=["bubble_tea_menu", "bubble_tea_menu", "desserts"], gondolas=["bubble_tea_menu"], near_counter=["bubble_tea_menu", "desserts"],
        style="perimeter", open_hours=(10, 22), dining_tables=4, checkouts=2, seating_zone="back", checkout_placement="near_entrance", design_theme="coastal",
    ),
    StoreTemplate(
        id="nordic_lifestyle", name="Nordic lifestyle showroom", description="Homeware, books and plant gifts on open browsing islands with pale ash finishes, slate accents and two checkout counters.",
        store_type="home", grid=(22, 18), fridges=[],
        wall_shelves=["home_design", "books", "flowers"] * 2,
        gondolas=["home_design", "home_design", "books", "flowers"], near_counter=["souvenirs", "home_design"],
        style="free_flow", open_hours=(10, 20), checkouts=2, design_theme="nordic",
    ),
    StoreTemplate(
        id="retro_diner", name="Retro diner & shake bar", description="Burgers, hot meals, coffee and frozen desserts around six tables, cherry-red counters and mint accents. Models counter purchases; kitchen and table service are not simulated.",
        store_type="restaurant", grid=(20, 16), fridges=["soft_drinks", "dairy", "water_sports"], freezers=["scoop_menu"],
        wall_shelves=["burger_menu", "restaurant_menu"] * 2, gondolas=["burger_menu", "restaurant_menu"],
        near_counter=["cafe_menu", "scoop_menu"], style="perimeter", open_hours=(7, 23), dining_tables=6,
        checkouts=2, seating_zone="center", checkout_placement="near_entrance", design_theme="retro",
    ),
    StoreTemplate(
        id="airport_shopping_gallery", name="Airport shopping gallery", description="Travel gifts, fragrance, jewelry and electronics around a large luxury shopping loop with four checkout counters.",
        store_type="travel", grid=(30, 24), fridges=["water_sports", "soft_drinks"],
        wall_shelves=["fragrances", "jewelry", "electronics", "travel_gear", "apparel"] * 3,
        gondolas=["travel_gear", "fragrances", "jewelry", "electronics", "souvenirs"],
        near_counter=["souvenirs", "checkout_impulse"], style="loop", checkouts=4,
        checkout_placement="away_from_entrance", design_theme="luxury",
    ),
    StoreTemplate(
        id="hospital_convenience", name="Hospital convenience & gift shop", description="A 24-hour shop for visitors and staff with meals, everyday care supplies, baby essentials and flowers around clear cross aisles.",
        store_type="convenience", grid=(18, 16), fridges=["fresh_meals", "dairy", "water_sports", "soft_drinks", "fresh_meals"],
        wall_shelves=["care_supplies", "baby_supplies", "pharmacy_care", "flowers"] * 2,
        gondolas=["care_supplies", "baby_supplies", "health_beauty", "bakery", "pantry"],
        near_counter=["flowers", "coffee_station"], style="cross", checkouts=2,
        checkout_placement="near_entrance", design_theme="minimal",
    ),
    StoreTemplate(
        id="museum_gift_shop", name="Museum book & gift shop", description="Books, art supplies, keepsakes and small home gifts on Nordic display islands. Open 10–18, with Mondays closed.",
        store_type="gift", grid=(16, 14), fridges=["water_sports"],
        wall_shelves=["books", "art_craft", "souvenirs", "stationery", "home_design"],
        gondolas=["books", "souvenirs", "art_craft", "home_design"], near_counter=["souvenirs", "stationery"],
        style="free_flow", open_hours=(10, 18), closed_days=(1,), checkouts=2,
        checkout_placement="away_from_entrance", design_theme="nordic",
    ),
    StoreTemplate(
        id="evening_food_court", name="Evening food court", description="A large 16–24 dining hall with twelve four-seat tables, six ordering counters and hot-meal, burger, salad and juice displays. Models counter purchases.",
        store_type="restaurant", grid=(32, 26), fridges=["soft_drinks", "water_sports", "dairy"] * 2, freezers=["scoop_menu"],
        wall_shelves=["restaurant_menu", "korean_menu", "burger_menu", "salad_menu", "juice_menu"] * 2,
        gondolas=["restaurant_menu", "korean_menu", "salad_menu"], near_counter=["juice_menu", "scoop_menu"],
        style="perimeter", open_hours=(16, 24), dining_tables=12, checkouts=6, seating_zone="center",
        checkout_placement="near_entrance", design_theme="terracotta",
    ),
    StoreTemplate(
        id="weekend_farmers_market", name="Weekend farmers' market", description="A large botanical market for produce, bread, pantry goods and flowers, with cross aisles and four checkout counters. Open Saturday and Sunday, 8–16; products use fixed pack prices.",
        store_type="supermarket", grid=(28, 22), fridges=["fresh_produce", "fresh_produce", "dairy", "water_sports"],
        wall_shelves=["bakery", "pantry", "flowers", "refill_goods"] * 3,
        gondolas=["fresh_produce", "pantry", "bakery", "flowers", "refill_goods"], near_counter=["bakery", "flowers"],
        style="cross", open_hours=(8, 16), closed_days=(1, 2, 3, 4, 5), checkouts=4,
        checkout_placement="near_entrance", design_theme="botanical",
    ),
    StoreTemplate(
        id="station_food_market", name="Station fresh-food market", description="Fresh meals, sandwiches, salads and coffee along a central spine, with two tables at the back and three checkout counters. Open 5–24 for commuter shopping.",
        store_type="convenience", grid=(20, 14), fridges=["fresh_meals", "fresh_meals", "salad_menu", "energy_coffee", "water_sports", "dairy"],
        wall_shelves=["bakery", "travel_gear", "pantry", "bakery"],
        gondolas=["fresh_meals", "bakery", "salad_menu", "travel_gear"], near_counter=["coffee_station", "bakery"],
        style="spine", open_hours=(5, 24), dining_tables=2, seating_zone="back", checkouts=3,
        checkout_placement="near_entrance", design_theme="coastal",
    ),
    StoreTemplate(
        id="cinema_snack_shop", name="Cinema snack shop", description="Popcorn, chips, sweets, drinks and ice cream in an open-center snack shop with three ordering counters and no dining tables. Open 10–24; tickets and screenings are outside the retail model.",
        store_type="convenience", grid=(18, 12), fridges=["soft_drinks", "soft_drinks", "water_sports"], freezers=["ice_cream", "scoop_menu"],
        wall_shelves=["chips", "sweets", "chips", "sweets", "bakery"],
        gondolas=["chips", "sweets"], near_counter=["chips", "checkout_impulse"],
        style="perimeter", open_hours=(10, 24), checkouts=3,
        checkout_placement="near_entrance", design_theme="industrial",
    ),
    StoreTemplate(
        id="office_cafeteria", name="Weekday office cafeteria", description="A 28×24 lunch floor with sixteen four-seat tables, four ordering counters and hot meals, salads and coffee. Open Monday–Friday, 7–19. Models counter purchases.",
        store_type="restaurant", grid=(28, 24), fridges=["salad_menu", "fresh_meals", "water_sports", "dairy", "soft_drinks"],
        wall_shelves=["restaurant_menu", "korean_menu", "bakery", "cafe_menu"] * 2,
        gondolas=["restaurant_menu", "salad_menu", "korean_menu"], near_counter=["coffee_station", "juice_menu"],
        style="perimeter", open_hours=(7, 19), closed_days=(6, 7), dining_tables=16, seating_zone="center", checkouts=4,
        checkout_placement="near_entrance", design_theme="minimal",
    ),
    StoreTemplate(
        id="community_market_hall", name="Community market hall", description="A 32×28 botanical market with a clear central plaza, four tables toward the back and four checkout counters. Produce, bread, meals, pantry goods and flowers are available daily, 8–20, at fixed pack prices.",
        store_type="supermarket", grid=(32, 28), fridges=["fresh_produce", "fresh_produce", "dairy", "fresh_meals", "water_sports"],
        wall_shelves=["bakery", "pantry", "flowers", "refill_goods"] * 3,
        gondolas=["fresh_produce", "pantry", "bakery", "flowers", "refill_goods", "fresh_meals"],
        near_counter=["coffee_station", "bakery"], style="plaza", open_hours=(8, 20), dining_tables=4,
        seating_zone="back", checkouts=4, checkout_placement="near_entrance", design_theme="botanical",
    ),
    StoreTemplate(
        id="creative_design_hall", name="Creative design hall", description="A 30×24 Nordic concept store with homeware, art materials, books, jewelry and plant gifts around an open central plaza. Three checkout counters; open 10–20 with Tuesdays closed.",
        store_type="home", grid=(30, 24), fridges=[],
        wall_shelves=["home_design", "art_craft", "books", "jewelry", "flowers"] * 3,
        gondolas=["home_design", "art_craft", "books", "jewelry", "flowers", "stationery"],
        near_counter=["souvenirs", "stationery"], style="plaza", open_hours=(10, 20), closed_days=(2,),
        checkouts=3, checkout_placement="away_from_entrance", design_theme="nordic",
    ),
    StoreTemplate(
        id="compact_pharmacy", name="Compact neighborhood pharmacy", description="An 8×8 care shop with a central spine, one service counter and first-aid, wellness and personal-care displays. Open 9–19, with Sundays closed. No prescription dispensing is modeled.",
        store_type="pharmacy", grid=(8, 8), fridges=["water_sports"],
        wall_shelves=["pharmacy_care", "wellness", "health_beauty"],
        gondolas=["pharmacy_care", "wellness"], near_counter=["pharmacy_care"],
        style="spine", open_hours=(9, 19), closed_days=(7,), checkouts=1, design_theme="minimal",
        checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="round_the_clock_pharmacy", name="24-hour care pharmacy", description="A 24×18 pharmacy with cross aisles, four service counters and first-aid, wellness, personal-care and mobility supplies. Open 0–24 every day. Models retail purchases without prescription dispensing.",
        store_type="pharmacy", grid=(24, 18), fridges=["water_sports", "water_sports"],
        wall_shelves=["pharmacy_care", "wellness", "health_beauty", "care_supplies"] * 2,
        gondolas=["pharmacy_care", "care_supplies", "wellness", "health_beauty"], near_counter=["pharmacy_care", "wellness"],
        style="cross", open_hours=(0, 24), checkouts=4, design_theme="coastal", checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="mediterranean_deli", name="Mediterranean deli", description="A 20×18 coastal deli with twelve pita, mezze, salad and rice dishes, six four-seat tables and two ordering counters. Perimeter displays leave the dining area open. Open 10–22, closed Mondays; purchases are made at counters.",
        store_type="restaurant", grid=(20, 18), fridges=["mediterranean_menu", "water_sports"],
        wall_shelves=["mediterranean_menu", "mediterranean_menu", "desserts", "soft_drinks"],
        gondolas=["mediterranean_menu"], near_counter=["mediterranean_menu", "coffee_station"],
        style="perimeter", open_hours=(10, 22), closed_days=(1,), dining_tables=6, seating_zone="center",
        checkouts=2, design_theme="coastal", checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="mexican_cantina", name="Mexican cantina", description="A 24×20 terracotta restaurant with twelve burrito, taco, quesadilla and side dishes, eight four-seat tables and three counters around a clear central plaza. Open 11–24 daily; models counter purchases, not kitchen or table service.",
        store_type="restaurant", grid=(24, 20), fridges=["soft_drinks", "water_sports"],
        wall_shelves=["mexican_menu", "mexican_menu", "desserts", "mexican_menu"],
        gondolas=["mexican_menu", "desserts"], near_counter=["mexican_menu"],
        style="plaza", open_hours=(11, 24), dining_tables=8, seating_zone="back", checkouts=3,
        design_theme="terracotta", checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="art_supply_warehouse", name="Art supply warehouse", description="A 36×28 industrial store with long art-material and stationery aisles, books, hobby kits and basic tools. Five checkout counters; open 9–20 daily.",
        store_type="crafts", grid=(36, 28), fridges=[],
        wall_shelves=["art_craft", "stationery", "books", "hardware", "toys_hobbies"] * 4,
        gondolas=["art_craft", "art_craft", "stationery", "toys_hobbies", "hardware"],
        near_counter=["stationery", "art_craft"], style="aisles", open_hours=(9, 20),
        checkouts=5, design_theme="industrial",
    ),
    StoreTemplate(
        id="beauty_outlet", name="Beauty & fragrance outlet", description="A 32×24 minimal shop for personal care, fragrance and wellness products, with cross aisles and four checkout counters. Open 10–22 daily; services and treatments are not modeled.",
        store_type="beauty", grid=(32, 24), fridges=[],
        wall_shelves=["health_beauty", "fragrances", "wellness"] * 5,
        gondolas=["health_beauty", "fragrances", "health_beauty", "wellness"],
        near_counter=["fragrances", "wellness"], style="cross", open_hours=(10, 22),
        checkouts=4, design_theme="minimal", checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="indian_curry_house", name="Indian curry house", description="Twelve curry, biryani, bread, side and drink choices around a 24×20 warm dining floor with eight four-seat tables and three ordering counters. Open 11–22, closed Tuesdays. Models counter purchases.",
        store_type="restaurant", grid=(24, 20), fridges=["water_sports", "soft_drinks"],
        wall_shelves=["indian_menu"] * 5, gondolas=["indian_menu", "desserts"],
        near_counter=["indian_menu"], style="perimeter", open_hours=(11, 22), closed_days=(2,),
        dining_tables=8, seating_zone="center", checkouts=3, design_theme="warm",
        checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="vietnamese_cafe", name="Vietnamese café & pho", description="Pho bowls, banh mi, rolls, coffee and tea on a 22×18 botanical floor with a browsing loop, six four-seat tables and two ordering counters. Open 9–21, closed Mondays. Models counter purchases without kitchen or table service.",
        store_type="cafe", grid=(22, 18), fridges=["water_sports", "soft_drinks"],
        wall_shelves=["vietnamese_menu", "vietnamese_menu", "soft_drinks", "desserts"],
        gondolas=["vietnamese_menu", "desserts"], near_counter=["vietnamese_menu"],
        style="loop", open_hours=(9, 21), closed_days=(1,), dining_tables=6,
        seating_zone="back", checkouts=2, design_theme="botanical", checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="pet_superstore", name="Pet supplies superstore", description="A 36×28 industrial store with pet-food and care aisles, carriers, beds, walking and grooming accessories, and five checkout counters. Open 9–21 daily; animal care services are not simulated.",
        store_type="pets", grid=(36, 28), fridges=[],
        wall_shelves=["pet_care", "pet_accessories"] * 7,
        gondolas=["pet_care", "pet_accessories", "pet_care", "pet_accessories"],
        near_counter=["pet_care", "pet_accessories"], style="aisles", open_hours=(9, 21),
        checkouts=5, design_theme="industrial",
    ),
    StoreTemplate(
        id="sports_outlet", name="Sports & camping outlet", description="A 34×26 Nordic store with a browsing loop for sports, camping equipment, outdoor accessories, apparel and footwear. Four checkouts; open 10–21 daily.",
        store_type="sports", grid=(34, 26), fridges=["water_sports"],
        wall_shelves=["sports", "outdoor_gear", "apparel", "footwear"] * 3,
        gondolas=["outdoor_gear", "sports", "footwear", "apparel"],
        near_counter=["sports", "outdoor_gear"], style="loop", open_hours=(10, 21),
        checkouts=4, design_theme="nordic",
    ),
    StoreTemplate(
        id="thai_kitchen", name="Thai kitchen & tea", description="Twelve noodle, curry, rice, side and drink choices on a 24×20 botanical floor with perimeter displays, eight four-seat tables and three ordering counters. Open 11–22, closed Wednesdays; models counter purchases.",
        store_type="restaurant", grid=(24, 20), fridges=["water_sports", "soft_drinks"],
        wall_shelves=["thai_menu"] * 5, gondolas=["thai_menu", "desserts"], near_counter=["thai_menu"],
        style="perimeter", open_hours=(11, 22), closed_days=(3,), dining_tables=8,
        seating_zone="center", checkouts=3, design_theme="botanical", checkout_placement="near_entrance",
    ),
    StoreTemplate(
        id="turkish_cafe", name="Turkish café & bakery", description="Twelve doner, flatbread, soup, sweet and drink choices on a 22×20 terracotta showroom floor with six four-seat tables and two counters. Open 8–22 daily; kitchen preparation and table service are not simulated.",
        store_type="cafe", grid=(22, 20), fridges=["water_sports", "soft_drinks"],
        wall_shelves=["turkish_menu"] * 4, gondolas=["turkish_menu", "desserts"], near_counter=["turkish_menu"],
        style="showroom", open_hours=(8, 22), dining_tables=6, seating_zone="back",
        checkouts=2, design_theme="terracotta", checkout_placement="near_entrance",
    ),
]

_BY_ID = {t.id: t for t in TEMPLATES}


def get_template(template_id: str) -> StoreTemplate | None:
    return _BY_ID.get(template_id)


class _Builder:
    def __init__(self, t: StoreTemplate, currency: str, rng: random.Random, options: LayoutOptions, seed: int):
        self.t, self.currency, self.rng = t, currency, rng
        self.options = options
        self.assortments: dict[str, list[CatalogItem]] = {}
        for category in set(t.fridges + t.freezers + t.wall_shelves + t.gondolas + t.near_counter):
            pool = CATALOG[category]
            limit = options.category_product_limits.get(category, options.products_per_category)
            self.assortments[category] = (
                random.Random(stable_seed("layout-assortment", seed, category)).sample(pool, limit)
                if limit is not None and limit < len(pool) else pool
            )
        self.w, self.h = options.width or t.grid[0], options.height or t.grid[1]
        self.racks: list[Rack] = []
        self.taken: set[tuple[int, int]] = set()
        self.reserved: set[tuple[int, int]] = set()
        for area in options.reserved_areas:
            if area.x + area.width > self.w - 1 or area.y + area.height > self.h - 1:
                raise ValueError(f"Reserved area '{area.label}' must fit inside the {self.w}×{self.h} floor, leaving the outer wall cells clear.")
            self.reserved.update((x, y) for x in range(area.x, area.x + area.width)
                                 for y in range(area.y, area.y + area.height))
        self.by_product: dict[CatalogItem, SlotItem] = {}
        self.counts: dict[str, int] = {}

    def free(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and (x, y) not in self.taken and (x, y) not in self.reserved

    def _items_for(self, category: str) -> list[SlotItem]:
        pool = self.assortments[category]
        start = self.counts.get(category, 0)
        self.counts[category] = start + 1
        # Rotate through the assortment so two racks of one category carry different products.
        order = pool[(start * 5) % len(pool):] + pool[: (start * 5) % len(pool)]
        items: list[SlotItem] = []
        for item in order:
            if item not in self.by_product:
                self.by_product[item] = catalog_slot_item(item, self.currency)
            items.append(self.by_product[item])
        return items

    def _slots(self, category: str, faces: list[Face]) -> list[Slot]:
        """4 levels × up to 4 items per face; eye level (3) first, then waist (2), top (4), bottom (1)."""
        slots: list[Slot] = []
        for face in faces:
            items = self._items_for(category)
            per_level = 4 if len(items) >= 12 else 3
            levels = [3, 2, 4, 1][:RACK_LEVELS]
            for i, level in enumerate(levels):
                chunk = items[i * per_level:(i + 1) * per_level] or items[:per_level]
                slots.append(Slot(block=0, face=face, level=level, items=[item.model_copy() for item in chunk]))
        return slots

    def add(self, kind: RackType, x: int, y: int, *, category: str | None = None, faces: list[Face] | None = None,
            rotation: int = 0, name: str = "", variant: str = "a") -> None:
        if not self.free(x, y):
            raise ValueError(f"fixture position is unavailable: {(x, y)}")
        self.taken.add((x, y))
        if kind == RackType.SHELF and self.options.fixture_design != "mixed":
            variant = self.options.fixture_design
        label = name or (category_label(category, self.currency) if category else "")
        n = sum(1 for r in self.racks if r.rack_name.startswith(label)) if label else 0
        rack_name = f"{label} {n + 1}" if label and kind not in (RackType.COUNTER,) else label
        self.racks.append(Rack(
            id=f"r_{len(self.racks):03d}", type=kind, shape=[[1]], position=(x, y),
            rotation=rotation,  # type: ignore[arg-type]
            rack_name=rack_name, rack_desc=category or "", design_variant=variant,  # type: ignore[arg-type]
            slots=self._slots(category, faces) if category and faces else [],
        ))


def generate_store(
    template_id: str, *, seed: int = 0, currency: str = "USD", store_id: str = "", name: str = "",
    style: LayoutStyle | None = None, options: LayoutOptions | None = None,
) -> Store:
    t = _BY_ID.get(template_id)
    if t is None:
        raise ValueError(f"unknown store template: {template_id}")
    rng = random.Random(stable_seed("layout-template", template_id, seed))
    options = options or LayoutOptions()
    open_hour = t.open_hours[0] if options.open_hour is None else options.open_hour
    close_hour = t.open_hours[1] if options.close_hour is None else options.close_hour
    closed_days = list(t.closed_days) if options.closed_days is None else options.closed_days
    if options.weekly_hours is None:
        if open_hour >= close_hour:
            raise ValueError("Opening hour must be earlier than closing hour. Overnight hours are not supported; use 0–24 for all-day opening.")
        if len(closed_days) != len(set(closed_days)):
            raise ValueError("Closed weekdays must not contain duplicates.")
        if len(closed_days) == 7:
            raise ValueError("Keep at least one open weekday for this store.")
    unknown_limits = options.category_product_limits.keys() - CATALOG.keys()
    if unknown_limits:
        raise ValueError(f"Unknown product categories in assortment limits: {', '.join(sorted(unknown_limits))}")
    if options.excluded_categories:
        excluded = set(options.excluded_categories)
        unknown = excluded - CATALOG.keys()
        if unknown:
            raise ValueError(f"Unknown product categories: {', '.join(sorted(unknown))}")
        t = replace(t, fridges=[c for c in t.fridges if c not in excluded],
                    freezers=[c for c in t.freezers if c not in excluded],
                    wall_shelves=[c for c in t.wall_shelves if c not in excluded],
                    gondolas=[c for c in t.gondolas if c not in excluded],
                    near_counter=[c for c in t.near_counter if c not in excluded])
        if not (t.fridges or t.freezers or t.wall_shelves or t.gondolas or t.near_counter):
            raise ValueError("Keep at least one product category for this store format.")
    b = _Builder(t, currency, rng, options, seed)
    w, h = b.w, b.h
    layout_style = style or options.style or t.style
    aisle, run_length = {"spacious": (3, 3), "balanced": (2, 4), "dense": (1, 6)}[options.density]
    aisle = options.aisle_width or aisle
    run_length = options.max_shelf_run or run_length
    clear_center: set[tuple[int, int]] = set()
    if layout_style == "cross":
        cross_x, cross_y = (w - aisle) // 2, (h - aisle) // 2
        clear_center = {(x, y) for x in range(1, w - 1) for y in range(1, h - 1)
                        if cross_x <= x < cross_x + aisle or cross_y <= y < cross_y + aisle}
    elif layout_style == "plaza":
        plaza_width, plaza_depth = max(2, (w - 2) // 3), max(2, (h - 2) // 3)
        plaza_x, plaza_y = (w - plaza_width) // 2, (h - plaza_depth) // 2
        clear_center = {(x, y) for x in range(plaza_x, plaza_x + plaza_width)
                        for y in range(plaza_y, plaza_y + plaza_depth)}
    checkout_placement = t.checkout_placement if options.checkout_placement == "auto" else options.checkout_placement
    seating_zone = t.seating_zone if options.seating_zone == "auto" else options.seating_zone

    # Reserve both gates before allocating checkout counters on the chosen wall.
    gate_positions = {
        "front": {"left": (0, h - 1), "center": (w // 2, h - 1), "right": (w - 1, h - 1)},
        "back": {"left": (1, 0), "center": (w // 2, 0), "right": (w - 2, 0)},
        "left": {"left": (0, 1), "center": (0, h // 2), "right": (0, h - 2)},
        "right": {"left": (w - 1, 1), "center": (w - 1, h // 2), "right": (w - 1, h - 2)},
    }
    entrance_position = gate_positions[options.gate_wall][options.entrance]
    exit_wall = options.gate_wall if options.exit_position == "shared" else options.exit_wall or options.gate_wall
    exit_position = entrance_position if options.exit_position == "shared" else gate_positions[exit_wall][options.exit_position]
    entrance_x, entrance_y = entrance_position
    gate_rotations: dict[str, Literal[0, 90, 180, 270]] = {"front": 0, "back": 180, "left": 90, "right": 270}
    gate_rotation = gate_rotations[options.gate_wall]
    b.add(RackType.ENTRANCE, *entrance_position, rotation=gate_rotation)
    b.racks.append(Rack(id="r_exit", type=RackType.EXIT, shape=[[1]], position=exit_position,
                       rotation=gate_rotations[exit_wall]))
    b.taken.add(exit_position)
    wall = options.checkout_wall
    if wall in ("front", "back"):
        wall_positions = [(x, h - 1 if wall == "front" else 0) for x in range(1, w - 1)]
    else:
        wall_positions = [(0 if wall == "left" else w - 1, y) for y in range(1, h - 1)]
    counter_positions = [p for p in wall_positions if b.free(*p)
                         and not (wall == "front" and checkout_placement == "auto" and p[0] == 1)]
    if checkout_placement == "near_entrance":
        counter_positions.sort(key=lambda p: abs(p[0] - entrance_x) + abs(p[1] - entrance_y))
    elif checkout_placement == "away_from_entrance":
        counter_positions.sort(key=lambda p: -(abs(p[0] - entrance_x) + abs(p[1] - entrance_y)))
    if options.checkout_clearance:
        spaced_positions: list[tuple[int, int]] = []
        for x, y in counter_positions:
            if all(abs(x - cx) + abs(y - cy) > options.checkout_clearance for cx, cy in spaced_positions):
                spaced_positions.append((x, y))
        counter_positions = spaced_positions
    checkout_count = min(t.checkouts, len(counter_positions)) if options.checkouts is None else options.checkouts
    if checkout_count > len(counter_positions):
        if options.checkout_clearance:
            raise ValueError(f"This checkout arrangement can place {len(counter_positions)} counters on the {wall} wall with {options.checkout_clearance}-cell spacing. Reduce the counter count or spacing, change placement or wall, or enlarge the floor.")
        raise ValueError(f"This {w}×{h} grid fits at most {len(counter_positions)} checkout counters on the {wall} wall with the selected gates and placement. Reduce the counter count, choose another wall or enlarge the floor.")
    counter_positions = counter_positions[:checkout_count]
    rotation = {"front": 0, "back": 180, "left": 90, "right": 270}[wall]
    face = {"front": Face.N, "back": Face.S, "left": Face.E, "right": Face.W}[wall]
    for i, (x, y) in enumerate(counter_positions):
        b.add(RackType.COUNTER, x, y, name=f"Counter {i + 1}", variant="b", rotation=rotation)
    if options.checkout_clearance:
        # Keep spacing open when the remaining wall displays are populated.
        b.taken.update((x, y) for x, y in wall_positions
                       if any(abs(x - cx) + abs(y - cy) <= options.checkout_clearance for cx, cy in counter_positions))
    stock_positions = [p for p in wall_positions if b.free(*p)]
    if wall != "front":
        stock_positions.sort(key=lambda p: min(abs(p[0] - cx) + abs(p[1] - cy) for cx, cy in counter_positions))
    for cat, (x, y) in zip(t.near_counter, stock_positions, strict=False):
        b.add(RackType.SHELF, x, y, category=cat, faces=[face], variant="c", rotation=rotation)

    # Back wall (y = 0): reach-in fridges facing south, freezers continuing the row.
    back = [(RackType.FRIDGE, c, "a") for c in t.fridges] + [(RackType.FRIDGE, c, "b") for c in t.freezers]
    xs = [x for x in range(1, w - 1) if b.free(x, 0)]
    for (kind, cat, variant), x in zip(back, xs, strict=False):
        b.add(kind, x, 0, category=cat, faces=[Face.S], variant=variant)

    # Side wall (x = w-1): wall shelves facing west.
    side_ys = [y for y in range(2, h - 2) if b.free(w - 1, y)]
    for cat, y in zip(t.wall_shelves, side_ys, strict=False):
        b.add(RackType.SHELF, w - 1, y, category=cat, faces=[Face.W], rotation=270)

    # Place larger mixed groups first; every footprint includes its chairs.
    clearance_x = options.table_clearance if options.table_clearance_x is None else options.table_clearance_x
    clearance_y = options.table_clearance if options.table_clearance_y is None else options.table_clearance_y
    clearance_label = f"{clearance_x}-cell" if clearance_x == clearance_y else f"{clearance_x}-cell left-right and {clearance_y}-cell back-front"
    mix = options.table_mix
    groups: list[tuple[int, int | None]] = [(options.dining_seats, options.dining_tables)] if mix is None else [
        (6, mix.six_seat), (4, mix.four_seat), (2, mix.two_seat),
    ]
    dining_clearance: set[tuple[int, int]] = set()
    table_index = 0
    for seats, requested in groups:
        target = t.dining_tables if requested is None else requested
        if target == 0:
            continue
        table_width, table_depth = (2, seats // 2) if options.table_rotation == 90 else (seats // 2, 2)
        step_x, step_y = (clearance_x + table_width, clearance_y + table_depth) if mix is None else (1, 1)
        table_positions = [(x, y) for y in range(clearance_y + 1, h - clearance_y - table_depth, step_y)
                           for x in range(clearance_x + 1, w - clearance_x - table_width, step_x)]
        table_positions = [(x, y) for x, y in table_positions
                           if all(b.free(cx, cy) and (cx, cy) not in clear_center
                                  for cx in range(x, x + table_width) for cy in range(y, y + table_depth))]
        # Seating extends into neighboring parts of the floor as its count grows.
        if seating_zone == "front":
            table_positions.sort(key=lambda p: (-p[1], abs(p[0] + (table_width - 1) / 2 - entrance_x)))
        elif seating_zone == "back":
            table_positions.sort(key=lambda p: (p[1], abs(p[0] + (table_width - 1) / 2 - (w - 1) / 2)))
        elif seating_zone == "left":
            table_positions.sort(key=lambda p: (p[0], p[1]))
        elif seating_zone == "right":
            table_positions.sort(key=lambda p: (-p[0], p[1]))
        elif seating_zone == "center":
            table_positions.sort(key=lambda p: (p[0] + (table_width - 1) / 2 - (w - 1) / 2) ** 2 + (p[1] + (table_depth - 1) / 2 - (h - 1) / 2) ** 2)
        elif seating_zone in ("near_entrance", "away_from_entrance"):
            distance_direction = 1 if seating_zone == "near_entrance" else -1
            table_positions.sort(key=lambda p: distance_direction * (
                abs(p[0] + (table_width - 1) / 2 - entrance_x) + abs(p[1] + (table_depth - 1) / 2 - entrance_y)))
        placed = 0
        for x, y in table_positions:
            if placed == target:
                break
            if any((cx, cy) in dining_clearance for cx in range(x, x + table_width) for cy in range(y, y + table_depth)):
                continue
            table_index += 1
            seat_label = {2: "Two", 4: "Four", 6: "Six"}[seats]
            table = Rack(id=f"r_table_{table_index}", type=RackType.TABLE, shape=[[1] * (seats // 2) for _ in range(2)],
                         position=(x, y), rotation=90 if options.table_rotation == 90 else 0,
                         rack_name=f"Dining table {table_index}", rack_desc=f"{seat_label} seats; furniture only")
            b.racks.append(table)
            b.taken.update(table.occupied_positions)
            dining_clearance.update((cx, cy) for cx in range(x - clearance_x, x + table_width + clearance_x)
                                    for cy in range(y - clearance_y, y + table_depth + clearance_y))
            placed += 1
        if requested is not None and placed < requested:
            if mix is not None:
                raise ValueError(f"This mixed dining arrangement can place {placed} of the requested {requested} {seats}-seat tables after larger tables, with {clearance_label} circulation space. Reduce the mix or clearance, change the seating zone or rotation, or enlarge the floor.")
            raise ValueError(f"This {w}×{h} grid fits at most {placed} dining tables with {clearance_label} circulation space, the selected aisle pattern and requested reserved areas. Reduce the table count or clearance, adjust the layout or increase the grid size.")

    # Every populated face opens onto a continuous aisle. Cross-aisles split
    # long shelf runs, and the front two rows stay clear for checkout circulation.
    vertical = options.shelf_direction == "vertical" and layout_style != "perimeter"
    pattern_width, pattern_height = (h, w) if vertical else (w, h)
    row_ys = list(range(2, pattern_height - 2, aisle + 1))
    island_xs = [x for x in range(2, pattern_width - 2) if (x - 2) % (run_length + aisle) < run_length]
    tiles: list[tuple[int, int, list[Face]]] = []
    if layout_style == "perimeter":
        tiles = [(0, y, [Face.E]) for y in range(2, h - 2)]
    else:
        if layout_style == "loop":
            row_ys = [2, pattern_height - 4] if pattern_height >= 8 else [2]
            if options.aisle_width is not None and row_ys[-1] - row_ys[0] <= aisle:
                row_ys = row_ys[:1]
            island_xs = [x for x in island_xs if 3 <= x < pattern_width - 3]
        for row, y in enumerate(row_ys):
            for x in island_xs:
                if layout_style == "spine" and abs(x - pattern_width // 2) < aisle:
                    continue
                if layout_style == "free_flow" and (x - 2 - row % 2) % (aisle + 1) != 0:
                    continue
                if layout_style == "showroom" and (x - 2) % (aisle + 3) >= 2:
                    continue
                tiles.append((x, y, [Face.N, Face.S]))
    if vertical:
        tiles = [(y, x, [Face.W, Face.E]) for x, y, _ in tiles]
    if t.gondolas:
        categories = list(t.gondolas)
        rng.shuffle(categories)
        for category in sorted(set(categories)):
            b.counts[category] = rng.randrange(len(CATALOG[category]))
        for i, (x, y, faces) in enumerate(tiles):
            cat = categories[min(len(categories) - 1, i * len(categories) // len(tiles))]
            if b.free(x, y) and (x, y) not in dining_clearance and (x, y) not in clear_center:
                b.add(RackType.SHELF, x, y, category=cat, faces=faces,
                      rotation=90 if layout_style == "perimeter" or vertical else 0,
                      variant="b" if (y // 3) % 2 else "a")

    if not any(slot.items for rack in b.racks for slot in rack.slots):
        raise ValueError(
            "No products from the included categories fit this layout: the selected product categories have "
            "no display space. Increase the grid size, reduce aisle width, checkout count or counter spacing, "
            "change the checkout wall or layout pattern, or include more categories."
        )

    format_design: dict[str, StoreDesign] = {
        "pharmacy": "minimal", "cafe": "warm", "bakery": "warm", "restaurant": "warm",
        "fashion": "luxury", "home": "minimal", "beauty": "luxury", "books": "warm",
        "electronics": "industrial", "sports": "industrial", "flowers": "botanical",
    }
    if options.weekly_hours is not None:
        days = [DaySchedule(day=Weekday(entry.day), is_open=entry.is_open,
                            open_hour=entry.open_hour, close_hour=entry.close_hour) for entry in options.weekly_hours]
    else:
        days = [DaySchedule(day=Weekday(d), is_open=d not in closed_days,
                            open_hour=open_hour, close_hour=close_hour) for d in range(1, 8)]
    return Store(
        id=store_id or f"store_{template_id}_{seed}", name=name or t.name, type=t.store_type,
        grid_size=(w, h), weekly_schedule=days, racks=b.racks,
        design_theme=options.design_theme or t.design_theme or format_design.get(t.store_type, "classic"),
        design_colors=options.design_colors,
        currency=currency.upper(),
    )
