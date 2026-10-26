"""Layout edits ("moves") explored by the optimizer.

A move is a small frozen record that names what it touches by rack id, face, level and SKU, so
it can be re-applied to any store: the genetic search replays its parents' moves on the
baseline. `apply_move` never mutates its input. It returns a deep-copied store plus a
human-readable description, or None when the move does not apply to that store or would make
the layout infeasible (validation errors, newly unreachable product faces, broken constraints).

Planogram moves keep racks in place. Items only move between racks of the same type and the
same category label ("Drink 1" ~ "Drink 2"): the shopper engines match categories against rack
labels, so dropping snacks into a rack labeled "Drink" would score purchases the store could
never make. Whole categories move with `SwapContents`, which carries the labels along.

Placement moves relocate 1×1 shelves and fridges; contents and locked faces travel with the
rack. A moved rack is turned in quarter steps so that its stocked faces open onto free floor,
preferring to keep its back against a wall when it had one. ENTRANCE, EXIT and COUNTER racks
never move.
"""

import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Final, Literal

from store_emulator.domain.optimize import OptimizeConstraints, OptimizeScope
from store_emulator.domain.rack import (
    PASSTHROUGH_TYPES,
    RACK_LEVELS,
    SLOT_CAPABLE_TYPES,
    BlockFace,
    Rack,
    RackType,
    Slot,
    SlotItem,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import FACE_OFFSETS, Face, Position
from store_emulator.engine.validation import list_blocked_faces, validate

LEVEL_NAMES: Final[dict[int, str]] = {1: "bottom", 2: "waist", 3: "eye", 4: "top"}
MOVABLE_TYPES: Final[frozenset[RackType]] = frozenset({RackType.SHELF, RackType.FRIDGE})

_CLOCKWISE: Final[dict[Face, Face]] = {Face.N: Face.E, Face.E: Face.S, Face.S: Face.W, Face.W: Face.N}
_ROTATIONS: Final[tuple[Literal[0, 90, 180, 270], ...]] = (0, 90, 180, 270)
_TURN_ORDER: Final[tuple[int, ...]] = (0, 2, 1, 3)  # preferred quarter turns: none, reverse, sideways
_DRAW_ATTEMPTS = 40


@dataclass(frozen=True)
class SlotRef:
    rack_id: str
    block: int
    face: Face
    level: int


@dataclass(frozen=True)
class SwapSlots:
    """Exchange the item lists of two slots."""
    a: SlotRef
    b: SlotRef


@dataclass(frozen=True)
class SwapItems:
    """Exchange one item of slot `a` with one item of slot `b`."""
    a: SlotRef
    sku_a: str
    b: SlotRef
    sku_b: str


@dataclass(frozen=True)
class SwapLevels:
    """Exchange two levels of one rack face (moves the slot when the other level is empty)."""
    rack_id: str
    block: int
    face: Face
    level_a: int
    level_b: int


@dataclass(frozen=True)
class SwapFaces:
    """Exchange every level of two rack faces (a category block keeps its vertical order)."""
    rack_a: str
    block_a: int
    face_a: Face
    rack_b: str
    block_b: int
    face_b: Face


@dataclass(frozen=True)
class SwapContents:
    """Exchange everything two racks of the same type hold, labels included; racks stay put."""
    rack_a: str
    rack_b: str


@dataclass(frozen=True)
class SwapRacks:
    """Exchange the positions of two racks of the same type."""
    rack_a: str
    rack_b: str


@dataclass(frozen=True)
class RelocateRack:
    """Move a rack to a free tile."""
    rack_id: str
    target: Position


type Move = SwapSlots | SwapItems | SwapLevels | SwapFaces | SwapContents | SwapRacks | RelocateRack
type MoveKind = Literal[
    "swap_slots", "swap_items", "swap_levels", "swap_faces", "swap_contents", "swap_racks", "relocate_rack",
]

_PLANOGRAM_WEIGHTS: Final[dict[MoveKind, float]] = {
    "swap_levels": 0.3, "swap_items": 0.25, "swap_slots": 0.2, "swap_contents": 0.15, "swap_faces": 0.1,
}
_PLACEMENT_WEIGHTS: Final[dict[MoveKind, float]] = {"swap_racks": 0.5, "relocate_rack": 0.5}


def move_kind(move: Move) -> MoveKind:
    match move:
        case SwapSlots():
            return "swap_slots"
        case SwapItems():
            return "swap_items"
        case SwapLevels():
            return "swap_levels"
        case SwapFaces():
            return "swap_faces"
        case SwapContents():
            return "swap_contents"
        case SwapRacks():
            return "swap_racks"
        case RelocateRack():
            return "relocate_rack"


def kind_weights(scope: OptimizeScope) -> dict[MoveKind, float]:
    if scope == OptimizeScope.PLANOGRAM:
        return dict(_PLANOGRAM_WEIGHTS)
    if scope == OptimizeScope.PLACEMENT:
        return dict(_PLACEMENT_WEIGHTS)
    weights: dict[MoveKind, float] = {k: 0.6 * w for k, w in _PLANOGRAM_WEIGHTS.items()}
    weights.update({k: 0.4 * w for k, w in _PLACEMENT_WEIGHTS.items()})
    return weights


@dataclass(frozen=True)
class MoveRules:
    scope: OptimizeScope
    locked: frozenset[str] = frozenset()
    fridges_on_walls: bool = True
    # Counts of exact offers already unreachable in the baseline. A blocked copy
    # does not permit hiding additional facings or another price/photo of its SKU.
    allowed_blocked: Counter[str] = field(default_factory=Counter[str])

    @classmethod
    def for_baseline(cls, baseline: Store, scope: OptimizeScope, constraints: OptimizeConstraints) -> "MoveRules":
        return cls(
            scope=scope,
            locked=frozenset(constraints.lock_rack_ids),
            fridges_on_walls=constraints.keep_fridges_on_walls,
            allowed_blocked=Counter(item.model_dump_json() for item in _blocked_items(baseline)),
        )


def _blocked_items(store: Store) -> list[SlotItem]:
    faces = {(d.rack_id, d.block, d.face) for d in list_blocked_faces(store)}
    return [
        item for rack in store.racks for slot in rack.slots
        if (rack.id, slot.block, slot.face) in faces for item in slot.items
    ]


def blocked_skus(store: Store) -> frozenset[str]:
    """SKUs stocked on a rack face shoppers cannot reach."""
    return frozenset(item.sku for item in _blocked_items(store))


def is_feasible(store: Store, rules: MoveRules) -> bool:
    """No validation error and no product newly stranded on an unreachable face."""
    if any(issue.severity == "error" for issue in validate(store)):
        return False
    return Counter(item.model_dump_json() for item in _blocked_items(store)) <= rules.allowed_blocked


def apply_move(store: Store, move: Move, rules: MoveRules) -> tuple[Store, str] | None:
    """Apply `move` to a deep copy of `store`. Returns (new store, description) or None."""
    if move_kind(move) not in kind_weights(rules.scope):
        return None
    new = store.model_copy(deep=True)
    description = _apply_in_place(new, move, rules)
    if description is None or not is_feasible(new, rules):
        return None
    return new, description


def replay(baseline: Store, moves: list[Move] | tuple[Move, ...], rules: MoveRules) -> tuple[Store, list[Move], list[str]]:
    """Apply `moves` in order, skipping the ones that no longer apply.

    Returns the final store (the baseline object itself when nothing applied), the moves that
    applied and their descriptions.
    """
    store = baseline
    applied: list[Move] = []
    descriptions: list[str] = []
    for move in moves:
        result = apply_move(store, move, rules)
        if result is None:
            continue
        store, description = result
        applied.append(move)
        descriptions.append(description)
    return store, applied, descriptions


def random_move(store: Store, rng: random.Random, rules: MoveRules) -> tuple[Move, Store, str] | None:
    """Draw a random feasible move for `store`: (move, new store, description), or None if none was found."""
    weights = kind_weights(rules.scope)
    kinds = list(weights)
    kind_weight_list = [weights[k] for k in kinds]
    for _ in range(_DRAW_ATTEMPTS):
        kind = rng.choices(kinds, weights=kind_weight_list, k=1)[0]
        move = _draw(store, kind, rng, rules)
        if move is None:
            continue
        result = apply_move(store, move, rules)
        if result is not None:
            return move, result[0], result[1]
    return None


def on_border(position: Position, grid_size: Position) -> bool:
    x, y = position
    w, h = grid_size
    return x == 0 or y == 0 or x == w - 1 or y == h - 1


# ---------------------------------------------------------------------------------------------
# Applying moves (in place, on a private copy)
# ---------------------------------------------------------------------------------------------

def _apply_in_place(store: Store, move: Move, rules: MoveRules) -> str | None:
    match move:
        case SwapSlots():
            return _swap_slots(store, move, rules)
        case SwapItems():
            return _swap_items(store, move, rules)
        case SwapLevels():
            return _swap_levels(store, move, rules)
        case SwapFaces():
            return _swap_faces(store, move, rules)
        case SwapContents():
            return _swap_contents(store, move, rules)
        case SwapRacks():
            return _swap_racks(store, move, rules)
        case RelocateRack():
            return _relocate(store, move, rules)


def _swap_slots(store: Store, move: SwapSlots, rules: MoveRules) -> str | None:
    found_a, found_b = _find_slot(store, move.a), _find_slot(store, move.b)
    if found_a is None or found_b is None:
        return None
    (rack_a, slot_a), (rack_b, slot_b) = found_a, found_b
    if slot_a is slot_b or not _items_can_move(rack_a, rack_b, rules) or _skus(slot_a) == _skus(slot_b):
        return None
    description = f"Swap {_slot_label(rack_a, slot_a)} <-> {_slot_label(rack_b, slot_b)}"
    slot_a.items, slot_b.items = slot_b.items, slot_a.items
    return description


def _swap_items(store: Store, move: SwapItems, rules: MoveRules) -> str | None:
    found_a, found_b = _find_slot(store, move.a), _find_slot(store, move.b)
    if found_a is None or found_b is None:
        return None
    (rack_a, slot_a), (rack_b, slot_b) = found_a, found_b
    if slot_a is slot_b or not _items_can_move(rack_a, rack_b, rules):
        return None
    index_a, index_b = _item_index(slot_a, move.sku_a), _item_index(slot_b, move.sku_b)
    if index_a is None or index_b is None or move.sku_a == move.sku_b:
        return None
    if _item_index(slot_a, move.sku_b) is not None or _item_index(slot_b, move.sku_a) is not None:
        return None  # would put the same SKU twice into one slot
    item_a, item_b = slot_a.items[index_a], slot_b.items[index_b]
    description = (
        f"Swap '{item_a.name}' ({_place(rack_a, slot_a)}) <-> '{item_b.name}' ({_place(rack_b, slot_b)})"
    )
    slot_a.items[index_a], slot_b.items[index_b] = item_b, item_a
    return description


def _swap_levels(store: Store, move: SwapLevels, rules: MoveRules) -> str | None:
    rack = _rack(store, move.rack_id)
    if rack is None or not _editable(rack, rules) or move.level_a == move.level_b:
        return None
    if not (1 <= move.level_a <= RACK_LEVELS and 1 <= move.level_b <= RACK_LEVELS):
        return None
    slot_a = _slot_at(rack, move.block, move.face, move.level_a)
    slot_b = _slot_at(rack, move.block, move.face, move.level_b)
    items_a = slot_a.items if slot_a is not None else []
    items_b = slot_b.items if slot_b is not None else []
    if [i.sku for i in items_a] == [i.sku for i in items_b]:
        return None
    description = (
        f"Swap levels on {_label(rack)} {move.face}: {_level(move.level_a)} [{_names(items_a)}]"
        f" <-> {_level(move.level_b)} [{_names(items_b)}]"
    )
    if slot_a is not None and slot_b is not None:
        slot_a.items, slot_b.items = slot_b.items, slot_a.items
    elif slot_a is not None:
        slot_a.level = move.level_b
    elif slot_b is not None:
        slot_b.level = move.level_a
    return description


def _swap_faces(store: Store, move: SwapFaces, rules: MoveRules) -> str | None:
    rack_a, rack_b = _rack(store, move.rack_a), _rack(store, move.rack_b)
    if rack_a is None or rack_b is None or not _items_can_move(rack_a, rack_b, rules):
        return None
    if (move.rack_a, move.block_a, move.face_a) == (move.rack_b, move.block_b, move.face_b):
        return None
    levels_a = {s.level: s for s in rack_a.slots if s.block == move.block_a and s.face == move.face_a}
    levels_b = {s.level: s for s in rack_b.slots if s.block == move.block_b and s.face == move.face_b}
    if not levels_a or set(levels_a) != set(levels_b):
        return None
    if all(_skus(levels_a[level]) == _skus(levels_b[level]) for level in levels_a):
        return None
    description = f"Swap faces {_label(rack_a)} {move.face_a} <-> {_label(rack_b)} {move.face_b} (all levels)"
    for level in sorted(levels_a):
        slot_a, slot_b = levels_a[level], levels_b[level]
        slot_a.items, slot_b.items = slot_b.items, slot_a.items
    return description


def _swap_contents(store: Store, move: SwapContents, rules: MoveRules) -> str | None:
    rack_a, rack_b = _rack(store, move.rack_a), _rack(store, move.rack_b)
    if rack_a is None or rack_b is None or rack_a is rack_b or rack_a.type != rack_b.type:
        return None
    if not (_movable(rack_a, rules) and _movable(rack_b, rules)):
        return None
    if _contents_key(rack_a) == _contents_key(rack_b):
        return None
    description = f"Swap contents of {_label(rack_a)} {_at(rack_a.position)} <-> {_label(rack_b)} {_at(rack_b.position)}"
    wall_a, wall_b = _wall_backed(rack_a, store.grid_size), _wall_backed(rack_b, store.grid_size)
    rack_a.slots, rack_b.slots = rack_b.slots, rack_a.slots
    rack_a.rack_name, rack_b.rack_name = rack_b.rack_name, rack_a.rack_name
    rack_a.rack_desc, rack_b.rack_desc = rack_b.rack_desc, rack_a.rack_desc
    rack_a.rack_decoration_desc, rack_b.rack_decoration_desc = rack_b.rack_decoration_desc, rack_a.rack_decoration_desc
    if not (_orient(store, rack_a, wall_a) and _orient(store, rack_b, wall_b)):
        return None
    return description


def _swap_racks(store: Store, move: SwapRacks, rules: MoveRules) -> str | None:
    rack_a, rack_b = _rack(store, move.rack_a), _rack(store, move.rack_b)
    if rack_a is None or rack_b is None or rack_a is rack_b or rack_a.type != rack_b.type:
        return None
    if not (_movable(rack_a, rules) and _movable(rack_b, rules)) or rack_a.position == rack_b.position:
        return None
    description = f"Swap rack positions {_label(rack_a)} {_at(rack_a.position)} <-> {_label(rack_b)} {_at(rack_b.position)}"
    wall_a, wall_b = _wall_backed(rack_a, store.grid_size), _wall_backed(rack_b, store.grid_size)
    rack_a.position, rack_b.position = rack_b.position, rack_a.position
    if not (_fridge_ok(rack_a, store, rules) and _fridge_ok(rack_b, store, rules)):
        return None
    if not (_orient(store, rack_a, wall_a) and _orient(store, rack_b, wall_b)):
        return None
    return description


def _relocate(store: Store, move: RelocateRack, rules: MoveRules) -> str | None:
    rack = _rack(store, move.rack_id)
    if rack is None or not _movable(rack, rules) or rack.position == move.target:
        return None
    w, h = store.grid_size
    tx, ty = move.target
    if not (0 <= tx < w and 0 <= ty < h) or store.rack_at(tx, ty) is not None:
        return None
    description = f"Move rack {_label(rack)} from {_at(rack.position)} to {_at(move.target)}"
    wall = _wall_backed(rack, store.grid_size)
    rack.position = move.target
    if not _fridge_ok(rack, store, rules) or not _orient(store, rack, wall):
        return None
    return description


# ---------------------------------------------------------------------------------------------
# Orientation of moved racks
# ---------------------------------------------------------------------------------------------

def _turn_face(face: Face, quarter_turns: int) -> Face:
    for _ in range(quarter_turns % 4):
        face = _CLOCKWISE[face]
    return face


def _stocked_faces(rack: Rack) -> set[Face]:
    return {slot.face for slot in rack.slots if slot.items}


def _wall_backed(rack: Rack, grid_size: Position) -> bool:
    """True when an unstocked face of this 1×1 rack points out of the grid (its back is on a wall)."""
    return _backs_onto_wall(rack.position, _stocked_faces(rack), grid_size)


def _backs_onto_wall(position: Position, stocked: set[Face], grid_size: Position) -> bool:
    w, h = grid_size
    for face, (dx, dy) in FACE_OFFSETS.items():
        x, y = position[0] + dx, position[1] + dy
        if face not in stocked and not (0 <= x < w and 0 <= y < h):
            return True
    return False


def _orient(store: Store, rack: Rack, want_wall_back: bool) -> bool:
    """Turn `rack` so every stocked face opens onto in-grid, unoccupied floor. False if no turn works."""
    w, h = store.grid_size
    occupied = {
        pos for other in store.racks if other is not rack and other.type not in PASSTHROUGH_TYPES
        for pos in other.occupied_positions
    }
    stocked = _stocked_faces(rack)
    locked = {bf.face for bf in rack.locked_faces}
    best: tuple[int, int, int] | None = None
    for order, turns in enumerate(_TURN_ORDER):
        faces = {_turn_face(f, turns) for f in stocked}
        if faces & {_turn_face(f, turns) for f in locked}:
            continue
        tiles = [(rack.position[0] + FACE_OFFSETS[f][0], rack.position[1] + FACE_OFFSETS[f][1]) for f in faces]
        if any(not (0 <= x < w and 0 <= y < h) or (x, y) in occupied for x, y in tiles):
            continue
        penalty = 1 if want_wall_back and not _backs_onto_wall(rack.position, faces, store.grid_size) else 0
        candidate = (penalty, order, turns)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return False
    _turn(rack, best[2])
    return True


def _turn(rack: Rack, quarter_turns: int) -> None:
    if quarter_turns % 4 == 0:
        return
    for slot in rack.slots:
        slot.face = _turn_face(slot.face, quarter_turns)
    rack.locked_faces = [BlockFace(block=bf.block, face=_turn_face(bf.face, quarter_turns)) for bf in rack.locked_faces]
    rack.rotation = _ROTATIONS[(_ROTATIONS.index(rack.rotation) + quarter_turns) % 4]


# ---------------------------------------------------------------------------------------------
# Drawing random moves
# ---------------------------------------------------------------------------------------------

def _draw(store: Store, kind: MoveKind, rng: random.Random, rules: MoveRules) -> Move | None:
    editable = [r for r in store.racks if _editable(r, rules)]
    slots = [(r, s) for r in editable for s in r.slots]
    stocked = [(r, s) for r, s in slots if s.items]
    match kind:
        case "swap_slots":
            if not stocked:
                return None
            rack_a, slot_a = rng.choice(stocked)
            pool = [(r, s) for r, s in slots if s is not slot_a and _same_category(r, rack_a)]
            if not pool:
                return None
            rack_b, slot_b = rng.choice(pool)
            return SwapSlots(a=_ref(rack_a, slot_a), b=_ref(rack_b, slot_b))
        case "swap_items":
            if not stocked:
                return None
            rack_a, slot_a = rng.choice(stocked)
            pool = [(r, s) for r, s in stocked if s is not slot_a and _same_category(r, rack_a)]
            if not pool:
                return None
            rack_b, slot_b = rng.choice(pool)
            return SwapItems(
                a=_ref(rack_a, slot_a), sku_a=rng.choice(slot_a.items).sku,
                b=_ref(rack_b, slot_b), sku_b=rng.choice(slot_b.items).sku,
            )
        case "swap_levels":
            if not stocked:
                return None
            rack, slot = rng.choice(stocked)
            other = rng.choice([level for level in range(1, RACK_LEVELS + 1) if level != slot.level])
            return SwapLevels(rack_id=rack.id, block=slot.block, face=slot.face, level_a=slot.level, level_b=other)
        case "swap_faces":
            faces = sorted({(r.id, s.block, s.face) for r, s in stocked})
            if len(faces) < 2:
                return None
            rack_a, block_a, face_a = rng.choice(faces)
            category = _category(_must_rack(store, rack_a))
            pool = [f for f in faces if f != (rack_a, block_a, face_a) and _category(_must_rack(store, f[0])) == category]
            if not pool:
                return None
            rack_b, block_b, face_b = rng.choice(pool)
            return SwapFaces(rack_a=rack_a, block_a=block_a, face_a=face_a, rack_b=rack_b, block_b=block_b, face_b=face_b)
        case "swap_contents" | "swap_racks":
            movable = [r for r in store.racks if _movable(r, rules)]
            if kind == "swap_contents":
                movable = [r for r in movable if any(s.items for s in r.slots)]
            if len(movable) < 2:
                return None
            rack_a = rng.choice(movable)
            pool = [r for r in movable if r is not rack_a and r.type == rack_a.type]
            if not pool:
                return None
            rack_b = rng.choice(pool)
            if kind == "swap_contents":
                return SwapContents(rack_a=rack_a.id, rack_b=rack_b.id)
            return SwapRacks(rack_a=rack_a.id, rack_b=rack_b.id)
        case "relocate_rack":
            movable = [r for r in store.racks if _movable(r, rules)]
            if not movable:
                return None
            rack = rng.choice(movable)
            w, h = store.grid_size
            taken = {pos for r in store.racks for pos in r.occupied_positions}
            free = [(x, y) for y in range(h) for x in range(w) if (x, y) not in taken]
            if rules.fridges_on_walls and rack.type == RackType.FRIDGE:
                free = [p for p in free if on_border(p, store.grid_size)]
            if not free:
                return None
            return RelocateRack(rack_id=rack.id, target=rng.choice(free))


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

def _rack(store: Store, rack_id: str) -> Rack | None:
    return next((r for r in store.racks if r.id == rack_id), None)


def _must_rack(store: Store, rack_id: str) -> Rack:
    rack = _rack(store, rack_id)
    if rack is None:
        raise KeyError(rack_id)
    return rack


def _slot_at(rack: Rack, block: int, face: Face, level: int) -> Slot | None:
    return next((s for s in rack.slots if s.block == block and s.face == face and s.level == level), None)


def _find_slot(store: Store, ref: SlotRef) -> tuple[Rack, Slot] | None:
    rack = _rack(store, ref.rack_id)
    if rack is None:
        return None
    slot = _slot_at(rack, ref.block, ref.face, ref.level)
    return None if slot is None else (rack, slot)


def _ref(rack: Rack, slot: Slot) -> SlotRef:
    return SlotRef(rack_id=rack.id, block=slot.block, face=slot.face, level=slot.level)


def _item_index(slot: Slot, sku: str) -> int | None:
    return next((i for i, item in enumerate(slot.items) if item.sku == sku), None)


def _skus(slot: Slot) -> list[str]:
    return [item.sku for item in slot.items]


def _contents_key(rack: Rack) -> list[tuple[int, str, int, list[str]]]:
    return sorted((s.block, s.face.value, s.level, _skus(s)) for s in rack.slots)


def _category(rack: Rack) -> tuple[RackType, str]:
    """Rack type plus its label without a trailing counter: 'Drink 2' and 'drink 1' share a category."""
    return rack.type, re.sub(r"[\s\d#_\-]+$", "", rack.rack_name.strip().lower())


def _same_category(a: Rack, b: Rack) -> bool:
    return _category(a) == _category(b)


def _editable(rack: Rack, rules: MoveRules) -> bool:
    return rack.id not in rules.locked and rack.type in SLOT_CAPABLE_TYPES


def _items_can_move(a: Rack, b: Rack, rules: MoveRules) -> bool:
    return _editable(a, rules) and _editable(b, rules) and _same_category(a, b)


def _movable(rack: Rack, rules: MoveRules) -> bool:
    return rack.id not in rules.locked and rack.type in MOVABLE_TYPES and len(rack.block_cells) == 1


def _fridge_ok(rack: Rack, store: Store, rules: MoveRules) -> bool:
    return not (rules.fridges_on_walls and rack.type == RackType.FRIDGE and not on_border(rack.position, store.grid_size))


def _at(position: tuple[int, int]) -> str:
    """A grid cell as the floor editor names it: counted from 1."""
    return f"(column {position[0] + 1}, row {position[1] + 1})"


def _label(rack: Rack) -> str:
    return f"'{rack.rack_name or rack.id}'"


def _level(level: int) -> str:
    return f"L{level} ({LEVEL_NAMES.get(level, '?')})"


def _names(items: list[SlotItem]) -> str:
    if not items:
        return "empty"
    names = [item.name for item in items[:2]]
    extra = f" +{len(items) - 2}" if len(items) > 2 else ""
    return ", ".join(names) + extra


def _place(rack: Rack, slot: Slot) -> str:
    return f"{_label(rack)} {slot.face}/{_level(slot.level)}"


def _slot_label(rack: Rack, slot: Slot) -> str:
    return f"{_place(rack, slot)} [{_names(slot.items)}]"
