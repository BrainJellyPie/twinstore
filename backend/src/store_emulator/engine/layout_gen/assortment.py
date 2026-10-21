"""A complete store built from a retailer's own assortment (categories with priced products).

Used to import a real product mix — e.g. the top categories and best sellers of a POS export or a
public transaction dataset — as a walkable store: refrigerated and frozen categories go to
reach-in fridges along the back and side walls, the rest to two-sided gondolas in aisles, the
entrance, exit and counter at the front. Best sellers sit at eye level (level 3), then waist (2),
top (4) and bottom (1), the usual retail convention.
"""

import hashlib
import math
from dataclasses import dataclass, field
from typing import Literal

from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Face, Weekday

type Storage = Literal["shelf", "fridge", "freezer"]

_LEVEL_ORDER = [3, 2, 4, 1][:RACK_LEVELS]


@dataclass(frozen=True)
class AssortmentCategory:
    key: str                                   # stable id, also written to rack_desc
    label: str                                 # the rack sign shoppers read
    items: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])  # (name, price), best sellers first
    storage: Storage = "shelf"


def _sku(category: str, name: str) -> str:
    return "a-" + hashlib.sha1(f"{category}|{name}".encode()).hexdigest()[:10]


def _slots(category: AssortmentCategory, faces: list[Face]) -> list[Slot]:
    items = [SlotItem(sku=_sku(category.key, n), name=n, price=p) for n, p in category.items]
    if not items:
        return []
    per_level = max(1, min(4, math.ceil(len(items) / len(_LEVEL_ORDER))))
    slots: list[Slot] = []
    for face in faces:
        for i, level in enumerate(_LEVEL_ORDER):
            chunk = items[i * per_level:(i + 1) * per_level]
            if chunk:
                slots.append(Slot(block=0, face=face, level=level, items=chunk))
    return slots


def _island_tiles(w: int, h: int) -> list[tuple[int, int]]:
    """Gondola tiles: rows every third line from y=2, columns 2..w-3, a cross aisle after every 4."""
    tiles: list[tuple[int, int]] = []
    for y in range(2, h - 2, 3):
        run = 0
        for x in range(2, w - 2):
            if run == 4:
                run = 0
                continue
            tiles.append((x, y))
            run += 1
    return tiles


def generate_assortment_store(
    categories: list[AssortmentCategory], *, store_id: str = "assortment_store", name: str = "Store",
    store_type: str = "supermarket", open_hours: tuple[int, int] = (6, 24), min_width: int = 12,
) -> Store:
    """One rack per category (two-sided gondola, or a wall fridge for chilled/frozen goods)."""
    cold = [c for c in categories if c.storage != "shelf" and c.items]
    dry = [c for c in categories if c.storage == "shelf" and c.items]

    # Width: the back wall holds the cold categories (corners excluded); height: enough island
    # rows for the dry categories plus the side-wall overflow of the cold ones.
    w = max(min_width, min(len(cold), 14) + 2)
    h = 8
    while True:
        side_slots = max(0, h - 4)
        overflow = max(0, len(cold) - (w - 2))
        if len(_island_tiles(w, h)) >= len(dry) and overflow <= side_slots:
            break
        h += 1

    racks: list[Rack] = []

    def add(kind: RackType, x: int, y: int, *, category: AssortmentCategory | None = None,
            faces: list[Face] | None = None, rotation: int = 0, rack_name: str = "", variant: str = "a") -> None:
        racks.append(Rack(
            id=f"r_{len(racks):03d}", type=kind, shape=[[1]], position=(x, y),
            rotation=rotation,  # type: ignore[arg-type]
            rack_name=rack_name or (category.label if category else ""),
            rack_desc=category.key if category else "", design_variant=variant,  # type: ignore[arg-type]
            slots=_slots(category, faces) if category and faces else [],
        ))

    add(RackType.ENTRANCE, 0, h - 1)
    racks.append(Rack(id="r_exit", type=RackType.EXIT, shape=[[1]], position=(0, h - 1)))
    add(RackType.COUNTER, 2, h - 1, rack_name="Counter", variant="b")

    back = list(range(1, w - 1))
    for cat, x in zip(cold, back, strict=False):
        add(RackType.FRIDGE, x, 0, category=cat, faces=[Face.S], variant="b" if cat.storage == "freezer" else "a")
    for cat, y in zip(cold[len(back):], range(2, h - 2), strict=False):
        add(RackType.FRIDGE, w - 1, y, category=cat, faces=[Face.W], rotation=270,
            variant="b" if cat.storage == "freezer" else "a")

    for cat, (x, y) in zip(dry, _island_tiles(w, h), strict=False):
        add(RackType.SHELF, x, y, category=cat, faces=[Face.N, Face.S], variant="b" if (y // 3) % 2 else "a")

    days = [DaySchedule(day=Weekday(d), is_open=True, open_hour=open_hours[0], close_hour=open_hours[1])
            for d in range(1, 8)]
    return Store(id=store_id, name=name, type=store_type, grid_size=(w, h), weekly_schedule=days, racks=racks)
