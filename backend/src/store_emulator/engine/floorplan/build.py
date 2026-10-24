"""Floor plan reading → a stocked Parastore store on the grid.

The outline maps to an 8–16 tile grid at the realistic mode's 1.25 m per tile. Each fixture covers
the tiles whose centres fall inside it and becomes one 1×1 rack per tile (the grid editor's unit).
Shelves and fridges face the free floor next to them; free-standing gondolas are shopped from both
long sides. Products come from the built-in catalog: the category a fixture's label names, else a
rotation of typical categories for its kind. Short openings are cleared through fixtures until
the aisles are connected to the entrance.
"""

from collections import deque
from typing import Literal

from store_emulator.domain.floorplan import FloorPlanReading, PlanFixture
from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType, Slot, SlotItem
from store_emulator.domain.store import GRID_MAX_SIDE, GRID_MIN_SIDE, DaySchedule, Store
from store_emulator.domain.types import Face
from store_emulator.engine.capture.catalog_match import match_category
from store_emulator.engine.layout_gen.catalog import CATALOG, category_label, localized

TILE_M = 1.25
FRIDGE_CATEGORIES = ("soft_drinks", "water_sports", "dairy", "energy_coffee", "beer_alcohol")
FREEZER_CATEGORIES = ("ice_cream",)
SHELF_CATEGORIES = ("chips", "sweets", "instant_food", "household", "health_beauty", "bakery", "stationery")
_ROTATION: dict[Face, Literal[0, 90, 180, 270]] = {Face.S: 0, Face.E: 90, Face.N: 180, Face.W: 270}
_STEP = {Face.N: (0, -1), Face.S: (0, 1), Face.W: (-1, 0), Face.E: (1, 0)}


def grid_for(reading: FloorPlanReading) -> tuple[int, int]:
    def side(m: float) -> int:
        return max(GRID_MIN_SIDE, min(GRID_MAX_SIDE, round(m / TILE_M)))

    w, h = side(reading.width_m), side(reading.depth_m)
    # Keep the plan's proportions when one side hit a bound.
    ratio = reading.width_m / reading.depth_m
    if w == GRID_MAX_SIDE or h == GRID_MAX_SIDE:
        if ratio >= 1:
            h = max(GRID_MIN_SIDE, min(GRID_MAX_SIDE, round(w / ratio)))
        else:
            w = max(GRID_MIN_SIDE, min(GRID_MAX_SIDE, round(h * ratio)))
    return w, h


def fixture_tiles(f: PlanFixture, w: int, h: int) -> list[tuple[int, int]]:
    """Tiles whose centre lies inside the fixture (at least the tile under its centre)."""
    tiles = [(x, y) for y in range(h) for x in range(w)
             if f.x1 <= (x + 0.5) / w <= f.x2 and f.y1 <= (y + 0.5) / h <= f.y2]
    if not tiles:
        tiles = [(min(w - 1, int((f.x1 + f.x2) / 2 * w)), min(h - 1, int((f.y1 + f.y2) / 2 * h)))]
    return tiles


class _Stocker:
    def __init__(self, currency: str) -> None:
        self.currency = currency
        self.by_name: dict[str, SlotItem] = {}
        self.uses: dict[str, int] = {}

    def items(self, category: str) -> list[SlotItem]:
        pool = CATALOG[category]
        start = (self.uses.get(category, 0) * 5) % len(pool)
        self.uses[category] = self.uses.get(category, 0) + 1
        out: list[SlotItem] = []
        for item in pool[start:] + pool[:start]:
            name, price = localized(item, self.currency)
            if name not in self.by_name:
                self.by_name[name] = SlotItem(sku=f"fp{len(self.by_name) + 1:04d}", name=name, price=price)
            out.append(self.by_name[name])
        return out

    def slots(self, category: str, faces: list[Face]) -> list[Slot]:
        slots: list[Slot] = []
        for face in faces:
            items = self.items(category)
            per_level = 4 if len(items) >= 12 else 3
            for i, level in enumerate([3, 2, 4, 1][:RACK_LEVELS]):
                chunk = items[i * per_level:(i + 1) * per_level] or items[:per_level]
                slots.append(Slot(block=0, face=face, level=level, items=chunk))
        return slots


def plan_to_store(
    reading: FloorPlanReading, *, currency: str = "USD", name: str = "Floor plan", store_type: str = "convenience",
    schedule: list[DaySchedule] | None = None, store_id: str = "store_floorplan",
) -> tuple[Store, list[str]]:
    w, h = grid_for(reading)
    notes: list[str] = [f"{reading.width_m:g} × {reading.depth_m:g} m → {w} × {h} tiles of {TILE_M:g} m"]
    taken: dict[tuple[int, int], int] = {}
    fixtures = [f for f in reading.fixtures if f.kind not in ("entrance", "counter")]
    for k, f in enumerate(fixtures):
        for t in fixture_tiles(f, w, h):
            taken.setdefault(t, k)

    entrance = next((f for f in reading.fixtures if f.kind == "entrance"), None)
    if entrance is not None:
        ex, ey = fixture_tiles(entrance, w, h)[0]
        # Snap to the nearest border tile.
        dists = {(ex, 0): ey, (ex, h - 1): h - 1 - ey, (0, ey): ex, (w - 1, ey): w - 1 - ex}
        door = min(dists, key=lambda t: dists[t])
    else:
        door = (0, h - 1)
    taken.pop(door, None)
    racks: list[Rack] = [
        Rack(id="r_entrance", type=RackType.ENTRANCE, shape=[[1]], position=door),
        Rack(id="r_exit", type=RackType.EXIT, shape=[[1]], position=door),
    ]
    counter = next((f for f in reading.fixtures if f.kind == "counter"), None)
    if counter is not None:
        cx, cy = fixture_tiles(counter, w, h)[0]
    else:
        cx, cy = min(w - 1, door[0] + 2), door[1]
    if (cx, cy) != door:
        taken.pop((cx, cy), None)
        racks.append(Rack(id="r_counter", type=RackType.COUNTER, shape=[[1]], position=(cx, cy), rack_name="Counter", design_variant="b"))
    occupied = set(taken) | {(cx, cy)}

    stocker = _Stocker(currency)
    rotation_by_kind: dict[str, int] = {}
    for k, f in enumerate(fixtures):
        tiles = [t for t, owner in taken.items() if owner == k]
        if not tiles:
            continue
        rack_type = RackType.FRIDGE if f.kind in ("fridge", "freezer") else RackType.SHELF
        if f.label.strip():
            category = match_category(f.label, rack_type="fridge" if rack_type == RackType.FRIDGE else "shelf")
        else:
            pool = FREEZER_CATEGORIES if f.kind == "freezer" else FRIDGE_CATEGORIES if f.kind == "fridge" else SHELF_CATEGORIES
            n = rotation_by_kind.get(f.kind, 0)
            rotation_by_kind[f.kind] = n + 1
            category = pool[n % len(pool)]
        if category not in CATALOG:
            category = SHELF_CATEGORIES[0] if rack_type == RackType.SHELF else FRIDGE_CATEGORIES[0]
        horizontal = (f.x2 - f.x1) * w >= (f.y2 - f.y1) * h
        label = category_label(category, currency)
        for i, (x, y) in enumerate(sorted(tiles)):
            free = [face for face, (dx, dy) in _STEP.items()
                    if 0 <= x + dx < w and 0 <= y + dy < h and (x + dx, y + dy) not in occupied]
            if f.kind == "gondola":
                free = [face for face in free if (face in (Face.N, Face.S)) == horizontal] or free
            else:
                free = free[:1]
            if not free:
                continue  # an inner tile of a deep block: left as floor
            racks.append(Rack(
                id=f"r_fp{k:02d}_{i:02d}", type=rack_type, shape=[[1]], position=(x, y),
                rotation=_ROTATION[free[0]] if len(free) == 1 else _ROTATION[Face.S if horizontal else Face.E],
                rack_name=f"{label} {k + 1}", rack_desc=category,
                design_variant="b" if f.kind in ("gondola", "freezer") else "a",
                slots=stocker.slots(category, free),
            ))

    store = Store(id=store_id, name=name, type=store_type, grid_size=(w, h), weekly_schedule=schedule or [], racks=racks,
                  currency=currency.upper())
    dropped = 0
    fixed = {rack.position for rack in store.counters}
    # A repair removes at least one product tile, bounded by the generated grid.
    # Connect floor regions through the cheapest opening instead of deleting
    # unreachable shelves behind a barrier while leaving that barrier intact.
    for _ in range(len(store.product_racks) + 1):
        products = {rack.position: rack.id for rack in store.product_racks}
        cost = {door: 0}
        previous: dict[tuple[int, int], tuple[int, int]] = {}
        pending = deque([door])
        target: tuple[int, int] | None = None
        # 0–1 BFS: walking on floor costs zero; opening a product tile costs one.
        while pending:
            cell = pending.popleft()
            if cost[cell] > 0 and cell not in products:
                target = cell
                break
            for dx, dy in _STEP.values():
                neighbor = cell[0] + dx, cell[1] + dy
                if not (0 <= neighbor[0] < w and 0 <= neighbor[1] < h) or neighbor in fixed:
                    continue
                step = int(neighbor in products)
                distance = cost[cell] + step
                if distance >= cost.get(neighbor, w * h + 1):
                    continue
                cost[neighbor], previous[neighbor] = distance, cell
                if step:
                    pending.append(neighbor)
                else:
                    pending.appendleft(neighbor)
        if target is None:
            break
        cleared: set[str] = set()
        while target != door:
            if target in products:
                cleared.add(products[target])
            target = previous[target]
        store = store.model_copy(update={"racks": [rack for rack in store.racks if rack.id not in cleared]})
        dropped += len(cleared)
    if dropped:
        notes.append(f"{dropped} tile(s) cleared so every rack can be reached from the entrance")
    return store, notes
