import math
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import PerceptionConfig, RouteOrdering
from store_emulator.domain.rack import Rack, RackType, Slot
from store_emulator.domain.types import Action, CARDINAL_DIRECTIONS, FACE_OFFSETS, Face, PathFinder, Position
from store_emulator.domain.store import Store
from .store_lookup import rack_id_at, resolve_buy_placement

_MAX_AREA_DWELL = 120  # The action-generation prompt's per-action time limit.


class JourneyStep(BaseModel):
    action: CustomerAction
    path: list[Position] = []


def build_journey(
    store: Store,
    actions: list[CustomerAction],
    pathfinder: PathFinder,
    block_move_sec: float = 1,
) -> list[JourneyStep]:
    grid = store.walkable_grid()
    w, h = store.grid_size
    current = entrance_position(store)
    journey: list[JourneyStep] = []

    for raw_action in actions:
        action = _sanitize_action(raw_action, grid, w, h, store)
        path = _calculate_path(store, grid, pathfinder, current, action, block_move_sec)
        if action.action == Action.PAY and path:
            action = action.model_copy(update={"target": path[-1]})
        # A failed point route must not record a remote stop at the previous position.
        if action.nav == "path" and action.target is not None:
            reached = path[-1] if path else current
            if reached != action.target:
                continue
        if action.action == Action.BUY:
            placement = resolve_buy_placement(
                store, target=action.target, face=action.face, sku=action.product_sku,
                block=action.product_block, level=action.product_level,
            ) if action.product_sku else None
            if placement is None or action.target is None:
                continue
            rack, slot = placement
            reached = path[-1] if path else current
            if (reached != action.target
                    or not rack.accepts_face_at(reached, slot.face, store.grid_size, block=slot.block)
                    or any(lock.block == slot.block and lock.face == slot.face for lock in rack.locked_faces)):
                continue
        journey.append(JourneyStep(action=action, path=path))
        if path:
            current = path[-1]

    return journey


def integrate_actions(
    store: Store,
    intent_actions: list[CustomerAction],
    impulse_actions: list[CustomerAction],
    *,
    ordering: RouteOrdering = "nearest",
) -> list[CustomerAction]:
    """Merge intent + impulse actions into one ENTER → visits → PAY → EXIT sequence.

    ordering="nearest" (legacy): every visit is re-ordered by greedy nearest-neighbor
    Manhattan distance from the entrance. BUY is only eligible after a BROWSE on the
    same rack.

    ordering="planned": the shopper's own visit order is kept. Impulse visits are
    grouped per rack and inserted where they add the least detour, which is how an
    unplanned stop happens in practice — on the way, not as a re-plan of the trip.
    """
    enter: CustomerAction | None = None
    exit_action: CustomerAction | None = None
    pay: CustomerAction | None = None
    middle: list[CustomerAction] = []

    for a in intent_actions:
        if a.nav == "leave":
            exit_action = a
        elif a.action == Action.PAY:
            pay = a
        elif a.action == Action.ENTER:
            enter = a
        else:
            middle.append(a)

    if ordering == "planned":
        ordered_planned = _insert_impulses(store, middle, impulse_actions, pay)
        return _frame(enter, ordered_planned, pay, exit_action)

    middle.extend(impulse_actions)

    if not middle:
        result: list[CustomerAction] = []
        if enter:
            result.append(enter)
        if pay:
            result.append(pay)
        if exit_action:
            result.append(exit_action)
        return result

    current = entrance_position(store)
    ordered: list[CustomerAction] = []
    remaining = list(middle)
    browsed_racks: set[str] = set()

    while remaining:
        best_idx = -1
        best_dist = 9999

        for i, a in enumerate(remaining):
            # Precedence: BUY is eligible only after BROWSE on the same rack is complete.
            if a.action == Action.BUY and _has_pending_browse(a, remaining, browsed_racks, store):
                continue
            dist = _manhattan(current, _action_position(a, store))
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx == -1:
            # All remaining actions are blocked — force the first to break the deadlock.
            best_idx = 0

        picked = remaining.pop(best_idx)
        ordered.append(picked)
        current = _action_position(picked, store)

        if picked.action == Action.BROWSE and picked.target is not None:
            rack_id = rack_id_at(store, picked.target, picked.face)
            if rack_id:
                browsed_racks.add(rack_id)

    return _frame(enter, ordered, pay, exit_action)


def _frame(
    enter: CustomerAction | None,
    middle: list[CustomerAction],
    pay: CustomerAction | None,
    exit_action: CustomerAction | None,
) -> list[CustomerAction]:
    result: list[CustomerAction] = []
    if enter:
        result.append(enter)
    result.extend(middle)
    if pay:
        result.append(pay)
    if exit_action:
        result.append(exit_action)
    return result


def _insert_impulses(
    store: Store,
    planned: list[CustomerAction],
    impulse: list[CustomerAction],
    pay: CustomerAction | None,
) -> list[CustomerAction]:
    """Cheapest-insertion of per-rack impulse groups into the planned visit order."""
    grid = store.walkable_grid()
    w, h = store.grid_size
    seq = list(planned)
    start = entrance_position(store)
    end = _sanitize_action(pay, grid, w, h, store).target if pay and pay.target else None
    end = end or _exit_position(store)

    for group in _group_by_rack(store, [_sanitize_action(a, grid, w, h, store) for a in impulse]):
        first = _action_position(group[0], store)
        last = _action_position(group[-1], store)
        best_i, best_cost = len(seq), 10**9
        for i in range(len(seq) + 1):
            prev = start if i == 0 else _action_position(seq[i - 1], store)
            nxt = end if i == len(seq) else _action_position(seq[i], store)
            cost = _manhattan(prev, first) + _manhattan(last, nxt) - _manhattan(prev, nxt)
            if cost < best_cost:
                best_i, best_cost = i, cost
        seq[best_i:best_i] = group
    return seq


def _group_by_rack(store: Store, actions: list[CustomerAction]) -> list[list[CustomerAction]]:
    """Group actions by the rack they target, preserving first-seen and in-group order."""
    groups: dict[str, list[CustomerAction]] = {}
    for idx, a in enumerate(actions):
        rack_id = ""
        if a.action == Action.BUY and a.product_sku:
            placement = resolve_buy_placement(store, target=a.target, face=a.face, sku=a.product_sku,
                                              block=a.product_block, level=a.product_level)
            if placement is not None:
                rack_id = placement[0].id
        if not rack_id and a.target is not None:
            rack_id = rack_id_at(store, a.target, a.face)
        groups.setdefault(rack_id or f"__unanchored_{idx}", []).append(a)
    return list(groups.values())


@dataclass(frozen=True)
class ExposedProduct:
    """A product the shopper could plausibly have noticed along the walked route."""
    rack: Rack
    slot: Slot
    sku: str
    visibility: float  # 0–1, combined over every visible facing of the SKU
    facings: int       # number of visible slots carrying the SKU


def perceive_products(
    store: Store,
    journey: list[JourneyStep],
    perception: PerceptionConfig,
) -> list[ExposedProduct]:
    """Visibility-based exposure.

    A slot is visible from a path tile when the tile is in front of the slot's face
    (within `view_distance` tiles, inside a 45° cone) and nothing walkable-blocking
    sits in between. Its score is shelf-level attention × a distance falloff. A SKU
    stocked on several visible facings is noticed with probability 1 − Π(1 − v).
    Opposite faces of a rack the shopper never walks past are therefore not seen,
    unlike the legacy adjacency model.
    """
    tiles: list[Position] = []
    seen_tiles: set[Position] = set()
    for step in journey:
        for pos in step.path:
            if pos not in seen_tiles:
                seen_tiles.add(pos)
                tiles.append(pos)
    if not tiles:
        return []

    grid = store.walkable_grid()
    miss: dict[str, float] = {}
    facings: dict[str, int] = {}
    anchor: dict[str, tuple[Rack, Slot, float]] = {}
    for rack in store.product_racks:
        cells = rack.occupied_positions
        for slot in rack.slots:
            if not slot.items:
                continue
            cell = cells[slot.block] if 0 <= slot.block < len(cells) else cells[0]
            v = max(_slot_visibility(grid, cell, slot, t, perception) for t in tiles)
            if v <= 0.0:
                continue
            for item in slot.items:
                miss[item.sku] = miss.get(item.sku, 1.0) * (1.0 - v)
                facings[item.sku] = facings.get(item.sku, 0) + 1
                best = anchor.get(item.sku)
                if best is None or v > best[2]:
                    anchor[item.sku] = (rack, slot, v)

    exposed = [
        ExposedProduct(rack=anchor[sku][0], slot=anchor[sku][1], sku=sku,
                       visibility=round(1.0 - m, 4), facings=facings[sku])
        for sku, m in miss.items()
        if 1.0 - m >= perception.min_visibility
    ]
    exposed.sort(key=lambda e: (-e.visibility, e.sku))
    return exposed[:perception.max_exposed_items]


def _slot_visibility(
    grid: list[list[bool]],
    cell: Position,
    slot: Slot,
    tile: Position,
    perception: PerceptionConfig,
) -> float:
    dx, dy = FACE_OFFSETS[slot.face]
    vx, vy = tile[0] - cell[0], tile[1] - cell[1]
    depth = vx * dx + vy * dy
    if depth < 1 or depth > perception.view_distance:
        return 0.0
    lateral = abs(vx) if dx == 0 else abs(vy)
    if lateral > max(1, depth):
        return 0.0
    if not _line_of_sight(grid, cell, tile):
        return 0.0
    falloff = 1.0 / (1.0 + 0.5 * (depth - 1) + 0.5 * lateral)
    return perception.level_attention.get(slot.level, 0.7) * falloff


def _line_of_sight(grid: list[list[bool]], src: Position, dst: Position) -> bool:
    """True when every cell strictly between `src` (the shelf) and `dst` is walkable."""
    steps = max(abs(dst[0] - src[0]), abs(dst[1] - src[1])) * 2
    for k in range(1, steps):
        x = round(src[0] + (dst[0] - src[0]) * k / steps)
        y = round(src[1] + (dst[1] - src[1]) * k / steps)
        if (x, y) in (src, dst):
            continue
        if not grid[y][x]:
            return False
    return True


def find_exposed_products(
    store: Store,
    journey: list[JourneyStep],
) -> list[tuple[Rack, Slot, str]]:
    path_tiles: set[Position] = set()
    for step in journey:
        for pos in step.path:
            path_tiles.add(pos)

    exposed: list[tuple[Rack, Slot, str]] = []
    seen_skus: set[str] = set()
    for f in store.product_racks:
        if not f.access_tiles(store.grid_size) & path_tiles:
            continue
        for slot in f.slots:
            for item in slot.items:
                if item.sku in seen_skus:
                    continue
                exposed.append((f, slot, item.sku))
                seen_skus.add(item.sku)
    return exposed


def _manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _has_pending_browse(
    buy_action: CustomerAction,
    remaining: list[CustomerAction],
    browsed_racks: set[str],
    store: Store,
) -> bool:
    """True if a BROWSE for the BUY's rack is still pending in remaining."""
    if buy_action.target is None:
        return False
    rack_id = ""
    if buy_action.product_sku:
        placement = resolve_buy_placement(
            store,
            target=buy_action.target,
            face=buy_action.face,
            sku=buy_action.product_sku,
            block=buy_action.product_block, level=buy_action.product_level,
        )
        if placement is not None:
            rack_id = placement[0].id
    if not rack_id:
        rack_id = rack_id_at(store, buy_action.target, buy_action.face)
    if not rack_id or rack_id in browsed_racks:
        return False
    return any(
        a.action == Action.BROWSE
        and a.target is not None
        and rack_id_at(store, a.target, a.face) == rack_id
        for a in remaining
    )


def _action_position(action: CustomerAction, store: Store) -> Position:
    """Resolve an action's destination tile. wander → area center; leave → exit."""
    if action.target:
        return action.target
    if action.nav == "area" and action.area:
        x1, y1, x2, y2 = action.area
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    if action.nav == "leave":
        return _exit_position(store)
    return entrance_position(store)


def _sanitize_action(
    action: CustomerAction,
    grid: list[list[bool]],
    w: int,
    h: int,
    store: Store,
) -> CustomerAction:
    """Snap action.target to a walkable tile; prefer the rack's access_tile when target sits on a rack."""
    # Area navigation uses dwell to plan movement before rack dwell limits apply.
    if action.nav == "area" and not 0 <= action.dwell <= _MAX_AREA_DWELL:
        action = action.model_copy(update={"dwell": max(0, min(_MAX_AREA_DWELL, action.dwell))})
    # PAY: snap into a counter's service_access_tiles.
    if action.action == Action.PAY:
        target = action.target
        if target is not None:
            target = (max(0, min(target[0], w - 1)), max(0, min(target[1], h - 1)))
        fallback: Position | None = None
        for counter in store.counters:
            service = [t for t in counter.service_access_tiles(store.grid_size) if grid[t[1]][t[0]]]
            if service:
                if fallback is None:
                    fallback = service[0]
                if target in service:
                    return action if target == action.target else action.model_copy(update={"target": target})
                if target in counter.occupied_positions:
                    return action.model_copy(update={"target": service[0]})
        if fallback is not None:
            return action.model_copy(update={"target": fallback})

    # BUY: re-anchor target + face against the SKU's actual placement so the
    # persona walks to the face that actually carries the product. Skips when
    # the SKU is empty or resolves to nothing — falls through to generic logic.
    if action.action == Action.BUY and action.product_sku:
        placement = resolve_buy_placement(
            store, target=action.target, face=action.face, sku=action.product_sku,
            block=action.product_block, level=action.product_level,
        )
        if placement is not None:
            rack, slot = placement
            snapped = face_access_tile(rack, slot.face, store.grid_size, grid, block=slot.block)
            # An unavailable offer must not fall through to generic floor snapping.
            return action.model_copy(update={
                "target": snapped, "face": slot.face,
                "product_block": slot.block, "product_level": slot.level,
            })

    if action.target is None:
        return action
    tx, ty = action.target
    cx = max(0, min(tx, w - 1))
    cy = max(0, min(ty, h - 1))
    if grid[cy][cx]:
        if (cx, cy) == action.target:
            return action
        return action.model_copy(update={"target": (cx, cy)})
    for rack in store.racks:
        if (cx, cy) in set(rack.occupied_positions):
            access = [t for t in rack.access_tiles(store.grid_size) if grid[t[1]][t[0]]]
            if access:
                return action.model_copy(update={"target": access[0]})
            break
    clamped = _clamp_to_walkable(action.target, grid, w, h)
    if clamped == action.target:
        return action
    return action.model_copy(update={"target": clamped})


def _calculate_path(
    store: Store,
    grid: list[list[bool]],
    pathfinder: PathFinder,
    current: Position,
    action: CustomerAction,
    block_move_sec: float = 1,
) -> list[Position]:
    if action.nav == "leave":
        exits = [tile for gate in store.exits for tile in gate.occupied_positions]
        path = _reachable_path(grid, pathfinder, current, exits or [entrance_position(store)])
        if not path:
            raise ValueError("No reachable exit from the shopper's current position")
        return path
    if action.action == Action.PAY:
        # Keep the selected counter and exact stance when reachable, then try its
        # other service tiles before another counter. Walkability alone is not connectivity.
        counters = sorted(store.counters, key=lambda counter:
                          action.target not in counter.service_access_tiles(store.grid_size))
        tiles = [tile for counter in counters for tile in sorted(
            counter.service_access_tiles(store.grid_size),
            key=lambda tile: (tile != action.target, _manhattan(current, tile), tile),
        )]
        path = _reachable_path(grid, pathfinder, current, tiles)
        if not path:
            raise ValueError("No reachable checkout from the shopper's current position")
        return path
    if action.nav == "area" and action.area:
        return _wander_path(store, grid, pathfinder, current, action.area, action.dwell, block_move_sec)
    if action.nav == "path" and action.target:
        return pathfinder.find_path(grid, current, action.target)
    return []


def _reachable_path(
    grid: list[list[bool]], pathfinder: PathFinder, current: Position, targets: Iterable[Position],
) -> list[Position]:
    for target in targets:
        x, y = target
        if not (0 <= y < len(grid) and 0 <= x < len(grid[y]) and grid[y][x]):
            continue
        if target == current:
            return [current]
        path = pathfinder.find_path(grid, current, target)
        if path and path[-1] == target:
            return path
    return []


def face_access_tile(
    rack: Rack, face: Face, grid_size: tuple[int, int], grid: list[list[bool]],
    *, block: int | None = None,
) -> Position | None:
    """Walkable stance on `face`, restricted to the selected block when supplied."""
    for tile in rack.access_tiles(grid_size):
        if rack.accepts_face_at(tile, face, grid_size, block=block) and grid[tile[1]][tile[0]]:
            return tile
    return None


def _clamp_to_walkable(pos: Position, grid: list[list[bool]], w: int, h: int) -> Position:
    x = max(0, min(pos[0], w - 1))
    y = max(0, min(pos[1], h - 1))
    if grid[y][x]:
        return (x, y)
    for dx, dy in CARDINAL_DIRECTIONS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and grid[ny][nx]:
            return (nx, ny)
    return (x, y)


def entrance_position(store: Store) -> Position:
    if store.entrances and store.entrances[0].occupied_positions:
        return store.entrances[0].occupied_positions[0]
    return (0, 0)


def _exit_position(store: Store) -> Position:
    if store.exits and store.exits[0].occupied_positions:
        return store.exits[0].occupied_positions[0]
    return entrance_position(store)


def _wander_path(
    store: Store,
    grid: list[list[bool]],
    pathfinder: PathFinder,
    start: Position,
    area: tuple[int, int, int, int],
    dwell: int,
    block_move_sec: float = 1,
) -> list[Position]:
    """Build a wander path visiting rack access tiles inside `area` as waypoints.

    Generates a generous path, then trims it via a dwell-budget simulation to the
    estimated reach. Precise time accounting (pause insertion) belongs to timeline_builder.
    """
    waypoints = _collect_waypoints(store, grid, area)
    if not waypoints:
        return [start]

    generous_limit = max(8, int(dwell / max(0.5, block_move_sec)) * 2)
    ordered = _order_nearest(start, waypoints)

    path: list[Position] = [start]
    current = start
    for wp in ordered:
        segment = pathfinder.find_path(grid, current, wp)
        if len(segment) < 2:
            continue
        path.extend(segment[1:])
        current = wp
        if len(path) >= generous_limit:
            break

    skip_types = {RackType.ENTRANCE, RackType.EXIT}
    rack_access: set[Position] = set()
    for rack in store.racks:
        if rack.type not in skip_types:
            rack_access |= rack.access_tiles(store.grid_size)

    budget: float = dwell
    _PAUSE_ESTIMATE = 2  # Conservative estimate of timeline_builder pause duration (actual: 2–4s).
    for i, pos in enumerate(path[1:], 1):
        movement = math.dist(path[i - 1], pos) * block_move_sec
        if movement > budget:
            return path[:i]
        budget -= movement
        if pos in rack_access:
            budget -= _PAUSE_ESTIMATE
        if budget <= 0:
            return path[:i + 1]

    return path


def _collect_waypoints(
    store: Store,
    grid: list[list[bool]],
    area: tuple[int, int, int, int],
) -> list[Position]:
    """Collect rack access tiles inside area; backfill from walkable tiles if too few."""
    x1, y1, x2, y2 = area
    skip_types = {RackType.ENTRANCE, RackType.EXIT}

    access_tiles: list[Position] = []
    for rack in store.racks:
        if rack.type in skip_types:
            continue
        for tile in rack.access_tiles(store.grid_size):
            if x1 <= tile[0] <= x2 and y1 <= tile[1] <= y2 and grid[tile[1]][tile[0]]:
                access_tiles.append(tile)
                break  # One tile per rack.

    if len(access_tiles) >= 2:
        return access_tiles

    walkable: list[Position] = []
    height = len(grid)
    width = len(grid[0]) if height > 0 else 0
    for y in range(max(0, y1), min(height, y2 + 1)):
        for x in range(max(0, x1), min(width, x2 + 1)):
            if grid[y][x]:
                walkable.append((x, y))

    if not walkable:
        return access_tiles

    count = min(5, len(walkable))
    step = max(1, len(walkable) // count)
    sampled = [walkable[i * step] for i in range(count)]
    return access_tiles + [t for t in sampled if t not in set(access_tiles)]


def _order_nearest(start: Position, points: list[Position]) -> list[Position]:
    remaining = list(points)
    ordered: list[Position] = []
    current = start
    while remaining:
        best_idx = min(range(len(remaining)), key=lambda i: _manhattan(current, remaining[i]))
        picked = remaining.pop(best_idx)
        ordered.append(picked)
        current = picked
    return ordered
