"""Fill empty racks deterministically using existing catalog identities and reachable faces."""
from store_emulator.domain.rack import RackType, Slot, SlotItem
from store_emulator.domain.starter_fill import FilledRack, RackFill, StarterPreview, StarterRack
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.validation import list_blocked_faces, validate


def available_faces(store: Store) -> dict[str, list[tuple[int, Face]]]:
    if not store.entrances or not any(rack.occupied_positions for rack in store.entrances):
        raise ValueError("Add an entrance in Step 1 before filling shelves")
    if store.grid_size[0] * store.grid_size[1] > 65_536 or len(store.racks) > 1_000:
        raise ValueError("Use at most 65,536 floor cells and 1,000 racks")
    if sum(len(rack.block_cells) for rack in store.racks) > 10_000:
        raise ValueError("Use at most 10,000 occupied rack cells")
    if sum(len(row) for rack in store.racks for row in rack.shape) > 50_000:
        raise ValueError("Use at most 50,000 rack shape cells")
    geometry_errors = [issue.message for issue in validate(store) if issue.code in {"out_of_bounds", "overlap"}]
    if geometry_errors:
        raise ValueError("Fix the floor in Step 1 before filling shelves: " + geometry_errors[0])
    blocked = {(row.rack_id, row.block, row.face) for row in list_blocked_faces(store)}
    return {rack.id: [(block, face) for block in range(len(rack.block_cells)) for face in rack.valid_faces(block)
                      if (rack.id, block, face) not in blocked]
            for rack in store.racks if rack.type in {RackType.SHELF, RackType.FRIDGE}}


def rack_choices(store: Store) -> list[StarterRack]:
    faces = available_faces(store)
    result: list[StarterRack] = []
    for rack in store.racks:
        if rack.id not in faces:
            continue
        stocked = any(slot.items for slot in rack.slots)
        reason = "Already contains products; kept unchanged" if stocked else (
            None if faces[rack.id] else "No accessible, unlocked product face")
        result.append(StarterRack(id=rack.id, name=rack.rack_name or rack.id, type=rack.type.value,
                                  available_slots=0 if reason else len(faces[rack.id]) * 4,
                                  suggested_category=rack.rack_desc if rack.rack_desc in CATALOG else None,
                                  reason=reason))
    return result


def fill_empty_racks(store: Store, assignments: list[RackFill], per_slot: int) -> tuple[Store, StarterPreview]:
    faces = available_faces(store)
    racks = {rack.id: rack for rack in store.racks}
    existing: dict[str, SlotItem] = {}
    ambiguous: set[str] = set()
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                if item.sku in existing and existing[item.sku] != item:
                    ambiguous.add(item.sku)
                existing[item.sku] = item
    planned = 0
    for row in assignments:
        if row.rack_id in faces and row.category in CATALOG:
            planned += len(faces[row.rack_id]) * 4 * min(per_slot, len(set(CATALOG[row.category])))
    current = sum(len(slot.items) for rack in store.racks for slot in rack.slots)
    if current + planned > 50_000:
        raise ValueError("The result would exceed 50,000 product placements")
    result = store.model_copy(deep=True)
    targets = {rack.id: rack for rack in result.racks}
    reports: list[FilledRack] = []
    added: set[str] = set()
    reused: set[str] = set()
    offsets: dict[str, int] = {}
    for row in sorted(assignments, key=lambda entry: entry.rack_id):
        rack = racks.get(row.rack_id)
        if rack is None or rack.id not in faces:
            raise ValueError(f"Choose an existing shelf or fridge: {row.rack_id}")
        if any(slot.items for slot in rack.slots):
            raise ValueError(f"Rack '{rack.id}' already contains products; it will not be replaced")
        if not faces[rack.id]:
            raise ValueError(f"Rack '{rack.id}' has no accessible, unlocked product face")
        if row.category not in CATALOG or not CATALOG[row.category]:
            raise ValueError(f"Choose a known starter category: {row.category}")
        pool = list({item.sku: item for item in (catalog_slot_item(p, store.currency or "USD") for p in CATALOG[row.category])}.values())
        used: dict[str, SlotItem] = {}
        reused_here: set[str] = set()
        slots: dict[tuple[int, Face, int], Slot] = {(s.block, s.face, s.level): s for s in targets[rack.id].slots}
        placements = 0
        for block, face in faces[rack.id]:
            for level in (3, 2, 4, 1):
                items: list[SlotItem] = []
                for _ in range(min(per_slot, len(pool))):
                    offset = offsets.get(row.category, 0)
                    item = pool[offset % len(pool)]
                    offsets[row.category] = offset + 1
                    if item.sku in ambiguous:
                        raise ValueError(f"SKU '{item.sku}' has mixed existing values. Resolve them in Edit products together first")
                    if item.sku in existing:
                        item = existing[item.sku]
                        reused.add(item.sku)
                        reused_here.add(item.sku)
                    else:
                        added.add(item.sku)
                    items.append(item.model_copy(deep=True))
                    used[item.sku] = item
                slots[(block, face, level)] = Slot(block=block, face=face, level=level, items=items)
                placements += len(items)
        targets[rack.id].slots = list(slots.values())
        reports.append(FilledRack(id=rack.id, name=rack.rack_name or rack.id, category=row.category,
                                  slots_added=len(faces[rack.id]) * 4, placements_added=placements,
                                  products=list(used.values()), reused_skus=sorted(reused_here)))
    if sum(len(slot.items) for rack in result.racks for slot in rack.slots) > 50_000:
        raise ValueError("The result would exceed 50,000 product placements")
    return result, StarterPreview(racks=reports, placements_added=sum(r.placements_added for r in reports),
                                  new_skus=len(added), reused_skus=len(reused))
