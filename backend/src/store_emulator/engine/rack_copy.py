"""Exact same-footprint rack reuse; never truncate or overwrite products."""
from store_emulator.domain.product_edits import MAX_PRICE
from store_emulator.domain.rack import Rack, RackType
from store_emulator.domain.rack_copy import RackCopyChoice, RackCopyPreview, RackCopyReason
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.starter_fill import available_faces


REASON_TEXT: dict[RackCopyReason, str] = {
    "choose_stocked": "Choose a stocked shelf or fridge",
    "source_inaccessible": "Source products include blocked, locked or unreachable faces; repair them first",
    "source_invalid_products": "Source products need valid SKUs and safe integer prices",
    "source_rack": "This is the source rack",
    "occupied": "Already contains products; kept unchanged",
    "fixture_mismatch": "Needs the same fixture type and footprint in the same orientation",
    "target_inaccessible": "A copied product face would be blocked, locked or unreachable",
}


def _count(rack: Rack) -> int:
    return sum(len(slot.items) for slot in rack.slots)


def _source_reason(rack: Rack, faces: dict[str, list[tuple[int, Face]]]) -> RackCopyReason | None:
    if rack.id not in faces or not _count(rack):
        return "choose_stocked"
    if any((slot.block, slot.face) not in faces[rack.id] for slot in rack.slots if slot.items):
        return "source_inaccessible"
    if any(not item.sku.strip() or item.price > MAX_PRICE or item.regular_price > MAX_PRICE
           for slot in rack.slots for item in slot.items):
        return "source_invalid_products"
    return None


def _target_reason(source: Rack, target: Rack, faces: dict[str, list[tuple[int, Face]]]) -> RackCopyReason | None:
    if source.id == target.id:
        return "source_rack"
    if _count(target):
        return "occupied"
    if source.type != target.type or source.rotated_shape != target.rotated_shape:
        return "fixture_mismatch"
    if any((slot.block, slot.face) not in faces.get(target.id, []) for slot in source.slots if slot.items):
        return "target_inaccessible"
    return None


def _choice(rack: Rack, placements: int, reason: RackCopyReason | None) -> RackCopyChoice:
    return RackCopyChoice(id=rack.id, name=rack.rack_name or rack.id, type=rack.type.value,
                          placements=placements, reason=REASON_TEXT[reason] if reason else None,
                          reason_code=reason)


def choices(store: Store, source_id: str | None) -> tuple[list[RackCopyChoice], list[RackCopyChoice]]:
    faces = available_faces(store)
    racks = [rack for rack in store.racks if rack.type in {RackType.SHELF, RackType.FRIDGE}]
    sources = [_choice(r, _count(r), _source_reason(r, faces)) for r in racks if _count(r)]
    if source_id is None:
        return sources, []
    source = next((r for r in racks if r.id == source_id), None)
    if source is None:
        raise ValueError("The source shelf no longer exists")
    reason = _source_reason(source, faces)
    if reason:
        raise ValueError(REASON_TEXT[reason])
    return sources, [_choice(r, _count(source), _target_reason(source, r, faces)) for r in racks]


def copy_products(store: Store, source_id: str, target_ids: list[str]) -> tuple[Store, RackCopyPreview]:
    _, targets = choices(store, source_id)
    selected: list[RackCopyChoice] = []
    for rid in target_ids:
        target = next((r for r in targets if r.id == rid), None)
        if target is None:
            raise ValueError(f"Choose an existing shelf or fridge: {rid}")
        if target.reason:
            raise ValueError(f"{target.name}: {target.reason}")
        selected.append(target)
    added = sum(r.placements for r in selected)
    if sum(_count(r) for r in store.racks) + added > 50_000:
        raise ValueError("The result would exceed 50,000 product placements")
    source = next(r for r in store.racks if r.id == source_id)
    slots = [slot for slot in source.slots if slot.items]
    result = store.model_copy(deep=True)
    for target in result.racks:
        if target.id not in target_ids:
            continue
        merged = {(s.block, s.face, s.level): s for s in target.slots}
        for slot in slots:
            merged[(slot.block, slot.face, slot.level)] = slot.model_copy(deep=True)
        target.slots = list(merged.values())
    return result, RackCopyPreview(source_name=source.rack_name or source.id, slots=slots, targets=selected,
                                   placements_added=added)
