from store_emulator.domain.rack import Rack, Slot
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face, Position


def rack_id_at(store: Store, target: Position, face: Face | None = None) -> str:
    """Return the rack ID at `target`.

    Lookup order:
    1. If a rack body occupies the tile, return its id. This precedence is
       intentional: a target *inside* a rack body is unambiguous, regardless
       of any face the LLM may have supplied. BROWSE/BUY routes are
       sanitized to access tiles upstream, so this branch normally only fires
       on a few legitimate cases (e.g., PAY at the counter).
    2. Otherwise, look for racks whose access tiles include `target`.
       - If `face` is given and at least one candidate accepts the tile on
         that face, return the first such candidate.
       - Otherwise, return the first candidate (preserves prior behavior).
    3. Return "" if no rack owns the tile.
    """
    rack = store.rack_at(target[0], target[1])
    if rack:
        return rack.id
    candidates = [r for r in store.racks if target in r.access_tiles(store.grid_size)]
    if not candidates:
        return ""
    if face is not None:
        for r in candidates:
            if r.accepts_face_at(target, face, store.grid_size):
                return r.id
    return candidates[0].id


def find_racks_by_sku(store: Store, sku: str) -> list[tuple[Rack, Slot]]:
    """Return every (rack, slot) carrying `sku`, including different faces of one rack.

    Each placement can have its own price and face stock. Keep them available
    until the customer's stance selects which offer they reached.
    """
    found: list[tuple[Rack, Slot]] = []
    for rack in store.racks:
        for slot in rack.slots:
            if sku in {i.sku for i in slot.items}:
                found.append((rack, slot))
    return found


def resolve_buy_placement(
    store: Store,
    *,
    target: Position | None,
    face: Face | None,
    sku: str,
    block: int | None = None,
    level: int | None = None,
) -> tuple[Rack, Slot] | None:
    """Pick the (rack, slot) the customer reached for a BUY action.

    Resolution — each later stage is strictly weaker, so we keep
    the most precise match available without ever throwing away the SKU
    information:

    1. **target + face match**: rack accepts `target` as an access tile AND
       the LLM-supplied `face` lines up with the rack's face at that tile.
       This is the strongest signal.
    2. **visible placement**: the slot's face accepts `target`, even when the
       supplied face is missing or incorrect.
    3. **target-only rack match**: retain the owning rack when the customer
       reached a side without this SKU; routing will move them to its placement.
    4. **first SKU placement**: no spatial match at all — fall back to the
       first rack carrying the SKU. Item-level attribution stays correct
       even if the exact rack is uncertain. See Risk Notes.

    Returns None only when no rack carries the SKU.
    """
    candidates = find_racks_by_sku(store, sku)
    if not candidates:
        return None
    if block is not None or level is not None:
        selected = [(rack, slot) for rack, slot in candidates
                    if (block is None or slot.block == block) and (level is None or slot.level == level)]
        if selected:
            candidates = selected
    if target is not None:
        grid = store.grid_size
        target_matches = [
            (rack, slot)
            for rack, slot in candidates
            if target in rack.access_tiles(grid)
        ]
        if face is not None:
            for rack, slot in target_matches:
                if slot.face == face and rack.accepts_face_at(target, slot.face, grid, block=slot.block):
                    return (rack, slot)
        for rack, slot in target_matches:
            if rack.accepts_face_at(target, slot.face, grid, block=slot.block):
                return (rack, slot)
        if target_matches:
            return target_matches[0]
    return candidates[0]
