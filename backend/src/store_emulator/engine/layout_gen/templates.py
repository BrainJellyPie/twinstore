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
from dataclasses import dataclass, field

from store_emulator.domain.layout_options import CheckoutPlacement, LayoutOptions, LayoutStyle, SeatingZone, StoreDesign
from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Face, Weekday, stable_seed

from .catalog import CATALOG, category_label, localized

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
        gondolas=["pantry", "pantry", "instant_food", "household", "chips", "sweets", "pet_care"], open_hours=(8, 23),
    ),
    StoreTemplate(
        id="warehouse_club", name="Warehouse club", description="Large 36×28 bulk-shopping floor with long sightlines and a central spine.",
        store_type="supermarket", grid=(36, 28), fridges=["dairy", "fresh_meals", "water_sports"] * 6,
        freezers=["ice_cream"] * 4, wall_shelves=["household", "car_care", "electronics"] * 4,
        gondolas=["pantry", "household", "pet_care", "water_sports", "chips"], style="spine", open_hours=(9, 21),
    ),
    StoreTemplate(
        id="organic_market", name="Organic neighborhood market", description="Produce, pantry essentials and chilled meals around a generous circulation loop.",
        store_type="supermarket", grid=(18, 16), fridges=["fresh_produce", "dairy", "fresh_meals"] * 3,
        wall_shelves=["pantry", "pantry", "household"], gondolas=["fresh_produce", "pantry", "bakery"], style="loop", open_hours=(8, 21),
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
        near_counter=["wellness"], style="spine", open_hours=(8, 22),
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
        near_counter=["cafe_menu", "desserts"], style="spine", open_hours=(10, 22), dining_tables=8,
    ),
    StoreTemplate(
        id="fashion_boutique", name="Fashion boutique", description="Curated apparel and accessories on free-flow display islands with perimeter collections.",
        store_type="fashion", grid=(16, 14), fridges=[], wall_shelves=["apparel"] * 5,
        gondolas=["apparel", "souvenirs"], near_counter=["apparel"], style="free_flow", open_hours=(10, 21),
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
]

_BY_ID = {t.id: t for t in TEMPLATES}


def get_template(template_id: str) -> StoreTemplate | None:
    return _BY_ID.get(template_id)


class _Builder:
    def __init__(self, t: StoreTemplate, currency: str, rng: random.Random, options: LayoutOptions):
        self.t, self.currency, self.rng = t, currency, rng
        self.options = options
        self.w, self.h = options.width or t.grid[0], options.height or t.grid[1]
        self.racks: list[Rack] = []
        self.taken: set[tuple[int, int]] = set()
        self.reserved: set[tuple[int, int]] = set()
        for area in options.reserved_areas:
            if area.x + area.width > self.w - 1 or area.y + area.height > self.h - 1:
                raise ValueError(f"Reserved area '{area.label}' must fit inside the {self.w}×{self.h} floor, leaving the outer wall cells clear.")
            self.reserved.update((x, y) for x in range(area.x, area.x + area.width)
                                 for y in range(area.y, area.y + area.height))
        self.sku_n = 0
        self.by_name: dict[str, SlotItem] = {}
        self.counts: dict[str, int] = {}

    def free(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and (x, y) not in self.taken and (x, y) not in self.reserved

    def _items_for(self, category: str) -> list[SlotItem]:
        pool = CATALOG[category]
        start = self.counts.get(category, 0)
        self.counts[category] = start + 1
        # Rotate through the assortment so two racks of one category carry different products.
        order = pool[(start * 5) % len(pool):] + pool[: (start * 5) % len(pool)]
        items: list[SlotItem] = []
        for item in order:
            name, price = localized(item, self.currency)
            if name not in self.by_name:  # a product shown on several faces is one SKU with more facings
                self.sku_n += 1
                self.by_name[name] = SlotItem(sku=f"g{self.sku_n:04d}", name=name, price=price)
            items.append(self.by_name[name])
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
                slots.append(Slot(block=0, face=face, level=level, items=chunk))
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
    b = _Builder(t, currency, rng, options)
    w, h = b.w, b.h
    layout_style = style or options.style or t.style
    checkout_placement = t.checkout_placement if options.checkout_placement == "auto" else options.checkout_placement
    seating_zone = t.seating_zone if options.seating_zone == "auto" else options.seating_zone

    # Reserve both gates before allocating checkout counters along the front wall.
    entrance_x = {"left": 0, "center": w // 2, "right": w - 1}[options.entrance]
    exit_x = entrance_x if options.exit_position == "shared" else {"left": 0, "center": w // 2, "right": w - 1}[options.exit_position]
    b.add(RackType.ENTRANCE, entrance_x, h - 1)
    b.racks.append(Rack(id="r_exit", type=RackType.EXIT, shape=[[1]], position=(exit_x, h - 1)))
    b.taken.add((exit_x, h - 1))
    counter_xs = [x for x in range(2 if checkout_placement == "auto" else 1, w - 1) if b.free(x, h - 1)]
    if checkout_placement == "near_entrance":
        counter_xs.sort(key=lambda x: abs(x - entrance_x))
    elif checkout_placement == "away_from_entrance":
        counter_xs.sort(key=lambda x: -abs(x - entrance_x))
    counter_xs = counter_xs[:options.checkouts]
    for i, x in enumerate(counter_xs):
        b.add(RackType.COUNTER, x, h - 1, name=f"Counter {i + 1}", variant="b")
    front_xs = [x for x in range(1, w - 1) if b.free(x, h - 1)]
    for cat, x in zip(t.near_counter, front_xs, strict=False):
        b.add(RackType.SHELF, x, h - 1, category=cat, faces=[Face.N], variant="c")

    # Back wall (y = 0): reach-in fridges facing south, freezers continuing the row.
    back = [(RackType.FRIDGE, c, "a") for c in t.fridges] + [(RackType.FRIDGE, c, "b") for c in t.freezers]
    xs = list(range(1, w - 1))
    for (kind, cat, variant), x in zip(back, xs, strict=False):
        b.add(kind, x, 0, category=cat, faces=[Face.S], variant=variant)

    # Side wall (x = w-1): wall shelves facing west.
    for cat, y in zip(t.wall_shelves, range(2, h - 2), strict=False):
        b.add(RackType.SHELF, w - 1, y, category=cat, faces=[Face.W], rotation=270)

    # A dining group occupies 2×2 cells, including its four chairs. Keep the
    # selected circulation ring clear of other tables, walls and retail displays.
    clearance = options.table_clearance
    table_positions = [(x, y) for y in range(clearance + 1, h - clearance - 2, clearance + 2)
                       for x in range(clearance + 1, w - clearance - 2, clearance + 2)]
    table_positions = [(x, y) for x, y in table_positions
                       if all(b.free(cx, cy) for cx in (x, x + 1) for cy in (y, y + 1))]
    # Rank safe seating positions without changing the table footprint or clearance.
    # As the count grows, seating extends into neighboring parts of the floor.
    if seating_zone == "front":
        table_positions.sort(key=lambda p: (-p[1], abs(p[0] + 0.5 - entrance_x)))
    elif seating_zone == "back":
        table_positions.sort(key=lambda p: (p[1], abs(p[0] + 0.5 - (w - 1) / 2)))
    elif seating_zone == "left":
        table_positions.sort(key=lambda p: (p[0], p[1]))
    elif seating_zone == "right":
        table_positions.sort(key=lambda p: (-p[0], p[1]))
    elif seating_zone == "center":
        table_positions.sort(key=lambda p: (p[0] + 0.5 - (w - 1) / 2) ** 2 + (p[1] + 0.5 - (h - 1) / 2) ** 2)
    table_count = min(t.dining_tables, len(table_positions)) if options.dining_tables is None else options.dining_tables
    if table_count > len(table_positions):
        raise ValueError(f"This {w}×{h} grid fits at most {len(table_positions)} dining tables with {clearance}-cell circulation space and the requested reserved areas. Reduce the table count or clearance, adjust reserved areas or increase the grid size.")
    dining_clearance: set[tuple[int, int]] = set()
    for i, (x, y) in enumerate(table_positions[:table_count]):
        table = Rack(id=f"r_table_{i + 1}", type=RackType.TABLE, shape=[[1, 1], [1, 1]],
                     position=(x, y), rack_name=f"Dining table {i + 1}", rack_desc="Four seats; furniture only")
        b.racks.append(table)
        b.taken.update(table.occupied_positions)
        dining_clearance.update((cx, cy) for cx in range(x - clearance, x + 2 + clearance)
                                for cy in range(y - clearance, y + 2 + clearance))

    # Every populated face opens onto a continuous aisle. Cross-aisles split
    # long shelf runs, and the front two rows stay clear for checkout circulation.
    aisle, run_length = {"spacious": (3, 3), "balanced": (2, 4), "dense": (1, 6)}[options.density]
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
            if b.free(x, y) and (x, y) not in dining_clearance:
                b.add(RackType.SHELF, x, y, category=cat, faces=faces,
                      rotation=90 if layout_style == "perimeter" or vertical else 0,
                      variant="b" if (y // 3) % 2 else "a")

    format_design: dict[str, StoreDesign] = {
        "pharmacy": "minimal", "cafe": "warm", "bakery": "warm", "restaurant": "warm",
        "fashion": "luxury", "home": "minimal", "beauty": "luxury", "books": "warm",
        "electronics": "industrial", "sports": "industrial", "flowers": "botanical",
    }
    days = [DaySchedule(day=Weekday(d), is_open=d not in t.closed_days,
                        open_hour=t.open_hours[0], close_hour=t.open_hours[1]) for d in range(1, 8)]
    return Store(
        id=store_id or f"store_{template_id}_{seed}", name=name or t.name, type=t.store_type,
        grid_size=(w, h), weekly_schedule=days, racks=b.racks,
        design_theme=options.design_theme or t.design_theme or format_design.get(t.store_type, "classic"),
        currency=currency.upper(),
    )
