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
from typing import Literal

from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Face, Weekday, stable_seed

from .catalog import CATALOG, category_label, localized

type LayoutStyle = Literal["aisles", "loop"]


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
        near_counter=["coffee_station", "checkout_impulse"], open_hours=(7, 22),
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
]

_BY_ID = {t.id: t for t in TEMPLATES}


def get_template(template_id: str) -> StoreTemplate | None:
    return _BY_ID.get(template_id)


class _Builder:
    def __init__(self, t: StoreTemplate, currency: str, rng: random.Random):
        self.t, self.currency, self.rng = t, currency, rng
        self.w, self.h = t.grid
        self.racks: list[Rack] = []
        self.taken: set[tuple[int, int]] = set()
        self.sku_n = 0
        self.by_name: dict[str, SlotItem] = {}
        self.counts: dict[str, int] = {}

    def free(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and (x, y) not in self.taken

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
        self.taken.add((x, y))
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
    style: LayoutStyle | None = None,
) -> Store:
    t = _BY_ID.get(template_id)
    if t is None:
        raise ValueError(f"unknown store template: {template_id}")
    rng = random.Random(stable_seed("layout-template", template_id, seed))
    b = _Builder(t, currency, rng)
    w, h = b.w, b.h
    layout_style = style or t.style

    # Front (south wall, y = h-1): entrance + exit at the bottom-left, counter next to it.
    entrance_x = 0
    b.add(RackType.ENTRANCE, entrance_x, h - 1)
    b.taken.discard((entrance_x, h - 1))  # entrance/exit tiles stay walkable
    b.racks.append(Rack(id="r_exit", type=RackType.EXIT, shape=[[1]], position=(entrance_x, h - 1)))
    b.taken.add((entrance_x, h - 1))
    counter_x = 2
    b.add(RackType.COUNTER, counter_x, h - 1, name="Counter", variant="b")
    for i, cat in enumerate(t.near_counter[:2]):
        x = counter_x + 1 + i
        if b.free(x, h - 1):
            b.add(RackType.SHELF, x, h - 1, category=cat, faces=[Face.N], variant="c")

    # Back wall (y = 0): reach-in fridges facing south, freezers continuing the row.
    back = [(RackType.FRIDGE, c, "a") for c in t.fridges] + [(RackType.FRIDGE, c, "b") for c in t.freezers]
    xs = list(range(1, w - 1))
    for (kind, cat, variant), x in zip(back, xs, strict=False):
        b.add(kind, x, 0, category=cat, faces=[Face.S], variant=variant)

    # Side wall (x = w-1): wall shelves facing west.
    for cat, y in zip(t.wall_shelves, range(2, h - 2), strict=False):
        b.add(RackType.SHELF, w - 1, y, category=cat, faces=[Face.W], rotation=270)

    # Islands: two-sided gondolas in rows with walkable aisles around them, split into runs of
    # at most four racks by cross aisles; categories fill the island tiles in template order.
    row_ys = list(range(2, h - 2, 3)) if layout_style == "aisles" else ([2, h - 4] if h >= 8 else [2])
    island_xs = list(range(2, w - 3)) if layout_style == "aisles" else list(range(3, w - 4))
    tiles: list[tuple[int, int]] = []
    for y in row_ys:
        run = 0
        for x in island_xs:
            if run == 4:
                run = 0
                continue
            if b.free(x, y):
                tiles.append((x, y))
                run += 1
    if t.gondolas:
        for i, (x, y) in enumerate(tiles):
            cat = t.gondolas[min(len(t.gondolas) - 1, i * len(t.gondolas) // len(tiles))]
            b.add(RackType.SHELF, x, y, category=cat, faces=[Face.N, Face.S], variant="b" if (y // 3) % 2 else "a")

    days = [DaySchedule(day=Weekday(d), is_open=d not in t.closed_days,
                        open_hour=t.open_hours[0], close_hour=t.open_hours[1]) for d in range(1, 8)]
    return Store(
        id=store_id or f"store_{template_id}_{seed}", name=name or t.name, type=t.store_type,
        grid_size=(w, h), weekly_schedule=days, racks=b.racks,
    )
