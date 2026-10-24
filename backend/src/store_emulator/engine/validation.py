import logging
from collections import deque

from store_emulator.domain.rack import Rack, RackType, PASSTHROUGH_TYPES, Slot
from store_emulator.domain.store import Store
from store_emulator.domain.types import CARDINAL_DIRECTIONS, FACE_OFFSETS, Face, Position

from .validation_models import (
    BlockReason, BlockedFaceDetail, ClearedSlot, Issue,
)

__all__ = [
    "BlockReason", "BlockedFaceDetail", "ClearedSlot", "Issue",
    "validate", "list_blocked_faces", "clear_blocked_slots", "log_cleared",
]


def log_cleared(logger: logging.Logger, prefix: str, cleared: list[ClearedSlot]) -> None:
    for c in cleared:
        logger.info(f"{prefix} auto-cleared unreachable slot: {c.description} [{','.join(c.reasons)}]")


def validate(store: Store) -> list[Issue]:
    issues: list[Issue] = []
    issues += _check_bounds(store)
    issues += _check_overlap(store)
    issues += _check_route(store)
    issues += _check_accessibility(store)
    return issues


def _check_bounds(store: Store) -> list[Issue]:
    w, h = store.grid_size
    issues: list[Issue] = []
    for f in store.racks:
        oob = [(x, y) for x, y in f.occupied_positions if x < 0 or x >= w or y < 0 or y >= h]
        if oob:
            issues.append(Issue(
                severity="error",
                code="out_of_bounds",
                message=f"rack '{f.id}' exceeds the grid",
            ))
    return issues


def _check_overlap(store: Store) -> list[Issue]:
    issues: list[Issue] = []
    cell_owners: dict[Position, str] = {}
    passthrough = PASSTHROUGH_TYPES
    for f in store.racks:
        if f.type in passthrough:
            continue
        for pos in f.occupied_positions:
            if pos in cell_owners:
                other_id = cell_owners[pos]
                issues.append(Issue(
                    severity="error",
                    code="overlap",
                    message=f"rack '{f.id}' overlaps with '{other_id}'",
                ))
            else:
                cell_owners[pos] = f.id
    return issues


def _check_route(store: Store) -> list[Issue]:
    issues: list[Issue] = []

    if not store.entrances:
        issues.append(Issue(severity="warning", code="no_entrance", message="no entrance"))
        return issues
    if not store.exits:
        issues.append(Issue(severity="error", code="no_exit", message="no exit"))
        return issues
    if not store.counters:
        issues.append(Issue(severity="warning", code="no_counter", message="no counter (payment unavailable)"))

    grid = store.walkable_grid()
    entrance_tiles = _rack_walkable_positions(store.entrances)
    if not entrance_tiles:
        issues.append(Issue(severity="error", code="entrance_blocked", message="cannot enter the store from the entrance"))
        return issues

    reachable = _flood_fill(grid, entrance_tiles)

    for counter in store.counters:
        counter_access = counter.service_access_tiles(store.grid_size)
        if not counter_access & reachable:
            issues.append(Issue(
                severity="error",
                code="no_route",
                message=f"cannot reach counter '{counter.id}' from the entrance",
            ))

    exit_tiles = _rack_walkable_positions(store.exits)
    if exit_tiles and not exit_tiles & reachable:
        issues.append(Issue(
            severity="error",
            code="no_route",
            message="cannot reach the exit from the counter",
        ))

    return issues


def _check_accessibility(store: Store) -> list[Issue]:
    issues: list[Issue] = []
    grid = store.walkable_grid()
    w, h = store.grid_size
    occupied = _all_occupied(store)

    entrance_tiles = _rack_walkable_positions(store.entrances)
    if not entrance_tiles:
        return issues
    reachable = _flood_fill(grid, entrance_tiles)

    for f in store.racks:
        if f.type in {RackType.ENTRANCE, RackType.EXIT}:
            continue

        if not f.access_tiles(store.grid_size) & reachable:
            issues.append(Issue(
                severity="error",
                code="unreachable_rack",
                message=f"cannot reach rack '{f.id}' from the entrance",
            ))
            continue

        if not f.slots:
            continue

        locked = {(bf.block, bf.face) for bf in f.locked_faces}
        block_cells = f.block_cells
        px, py = f.position
        for slot in f.slots:
            if not slot.items or slot.block >= len(block_cells):
                continue
            r, c = block_cells[slot.block]
            _tile, reasons = _classify_face(
                slot.block, slot.face, locked, px + c, py + r, w, h, occupied, reachable,
            )
            if reasons:
                sku_str = ", ".join(i.sku for i in slot.items)
                issues.append(Issue(
                    severity="warning",
                    code="blocked_slot",
                    message=f"rack '{f.id}' slot (block={slot.block}, face={slot.face}, level={slot.level}) has item '{sku_str}' but is unreachable",
                ))

    return issues


def list_blocked_faces(store: Store) -> list[BlockedFaceDetail]:
    """Detail every (rack, block, face) that is unreachable, with up to 4 reasons.

    Checks all faces regardless of slot fill (used to pre-filter the Excel template).
    """
    out: list[BlockedFaceDetail] = []
    grid = store.walkable_grid()
    w, h = store.grid_size
    occupied = _all_occupied(store)
    entrance_tiles = _rack_walkable_positions(store.entrances)
    if not entrance_tiles:
        return out
    reachable = _flood_fill(grid, entrance_tiles)

    for rack in store.racks:
        if rack.type in {RackType.ENTRANCE, RackType.EXIT, RackType.TABLE}:
            continue
        locked = {(bf.block, bf.face) for bf in rack.locked_faces}
        block_cells = rack.block_cells
        shape_cells = set(block_cells)
        px, py = rack.position
        for block_idx, (r, c) in enumerate(block_cells):
            for face in (Face.N, Face.S, Face.E, Face.W):
                dx, dy = FACE_OFFSETS[face]
                if (r + dy, c + dx) in shape_cells:
                    # Face occluded by an adjacent cell of the same rack. replace_slots
                    # already rejects this via its valid_faces check; pre-exclude it from
                    # the download template too.
                    out.append(BlockedFaceDetail(
                        rack_id=rack.id, block=block_idx, face=face, reasons=["occluded"],
                    ))
                    continue
                _, reasons = _classify_face(
                    block_idx, face, locked, px + c, py + r, w, h, occupied, reachable,
                )
                if reasons:
                    out.append(BlockedFaceDetail(
                        rack_id=rack.id, block=block_idx, face=face, reasons=reasons,
                    ))
    return out


def clear_blocked_slots(store: Store) -> list[ClearedSlot]:
    """Clear products on unreachable faces and return the removed slot details. Mutates `store` in place."""
    grid = store.walkable_grid()
    w, h = store.grid_size
    occupied = _all_occupied(store)
    entrance_tiles = _rack_walkable_positions(store.entrances)
    if not entrance_tiles:
        return []
    reachable = _flood_fill(grid, entrance_tiles)

    cleared: list[ClearedSlot] = []
    for rack in store.racks:
        if rack.type in {RackType.ENTRANCE, RackType.EXIT}:
            continue
        if not rack.slots:
            continue
        locked = {(bf.block, bf.face) for bf in rack.locked_faces}
        block_cells = rack.block_cells
        px, py = rack.position
        kept: list[Slot] = []
        for slot in rack.slots:
            if not slot.items or slot.block >= len(block_cells):
                kept.append(slot)
                continue
            r, c = block_cells[slot.block]
            _, reasons = _classify_face(
                slot.block, slot.face, locked, px + c, py + r, w, h, occupied, reachable,
            )
            if reasons:
                cleared.append(ClearedSlot(
                    rack_id=rack.id, block=slot.block, face=slot.face, level=slot.level,
                    cleared_skus=[i.sku for i in slot.items],
                    name=", ".join(i.name for i in slot.items),
                    reasons=reasons,
                ))
                continue  # Drop the slot.
            kept.append(slot)
        rack.slots = kept
    return cleared


def _classify_face(
    block_idx: int,
    face: Face,
    locked: set[tuple[int, Face]],
    block_x: int,
    block_y: int,
    w: int,
    h: int,
    occupied: set[Position],
    reachable: set[Position],
) -> tuple[Position, list[BlockReason]]:
    """Return the face's adjacent tile and the list of reasons it is unreachable.

    Empty reason list means reachable. Multiple reasons may apply at once (e.g. locked + unreachable).
    """
    offsets = {Face.N: (0, -1), Face.S: (0, 1), Face.W: (-1, 0), Face.E: (1, 0)}
    dx, dy = offsets[face]
    tile: Position = (block_x + dx, block_y + dy)
    reasons: list[BlockReason] = []
    if (block_idx, face) in locked:
        reasons.append("locked")
    if tile[0] < 0 or tile[0] >= w or tile[1] < 0 or tile[1] >= h:
        reasons.append("out_of_bounds")
    elif tile in occupied:
        reasons.append("occupied")
    elif tile not in reachable:
        reasons.append("unreachable")
    return tile, reasons


def _flood_fill(grid: list[list[bool]], starts: set[Position]) -> set[Position]:
    reachable: set[Position] = set()
    queue: deque[Position] = deque()
    height = len(grid)
    width = len(grid[0]) if height > 0 else 0
    for pos in starts:
        x, y = pos
        if 0 <= x < width and 0 <= y < height and grid[y][x]:
            queue.append(pos)
            reachable.add(pos)

    directions = CARDINAL_DIRECTIONS
    while queue:
        x, y = queue.popleft()
        for dx, dy in directions:
            next_x, next_y = x + dx, y + dy
            npos: Position = (next_x, next_y)
            if 0 <= next_x < width and 0 <= next_y < height and grid[next_y][next_x] and npos not in reachable:
                reachable.add(npos)
                queue.append(npos)
    return reachable


def _rack_walkable_positions(rack_list: list[Rack]) -> set[Position]:
    positions: set[Position] = set()
    for f in rack_list:
        for pos in f.occupied_positions:
            positions.add(pos)
    return positions


def _all_occupied(store: Store) -> set[Position]:
    occupied: set[Position] = set()
    passthrough = PASSTHROUGH_TYPES
    for f in store.racks:
        if f.type in passthrough:
            continue
        for pos in f.occupied_positions:
            occupied.add(pos)
    return occupied
