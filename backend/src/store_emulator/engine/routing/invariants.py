"""Post-simulation invariants on rack / face / SKU consistency.

A clean run should satisfy: every BUY event names a (target_rack, face) pair
whose actual slot carries the bought product_sku, and the event's product_name
and price match the slot's item. Violations indicate that the LLM-generated
action triple was not re-anchored against ground truth.
"""

from dataclasses import dataclass

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.rack import Rack, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, FACE_OFFSETS, Face


@dataclass(frozen=True)
class BuyViolation:
    persona_id: str
    elapsed_sec: int
    target_rack: str
    face: Face | None
    product_sku: str
    kind: str  # see VIOLATION_KINDS
    detail: str = ""


VIOLATION_KINDS = frozenset({
    "unknown_rack",       # target_rack not in store
    "sku_not_in_store",   # product_sku not in any slot
    "face_none",          # face is None — couldn't attribute a side
    "sku_not_on_face",    # (target_rack, face) carries no slot with this sku
    "name_mismatch",      # event.product_name diverges from slot item
    "price_mismatch",     # event.price diverges from slot item
    "locked_face",        # buy occurred on a locked face
})


def check_buy_consistency(store: Store, results: list[CustomerResult]) -> list[BuyViolation]:
    """Walk every BUY event and report violations of the rack/face/sku contract."""
    racks_by_id: dict[str, Rack] = {r.id: r for r in store.racks}
    face_sku: dict[tuple[str, Face, int | None], dict[str, list[SlotItem]]] = {}
    sku_to_racks: dict[str, set[str]] = {}
    for r in store.racks:
        for slot in r.slots:
            bucket = face_sku.setdefault((r.id, slot.face, slot.block), {})
            legacy_bucket = face_sku.setdefault((r.id, slot.face, None), {})
            for it in slot.items:
                bucket.setdefault(it.sku, []).append(it)
                legacy_bucket.setdefault(it.sku, []).append(it)
                sku_to_racks.setdefault(it.sku, set()).add(r.id)

    violations: list[BuyViolation] = []
    for cr in results:
        for ev in cr.timeline:
            if ev.action != Action.BUY:
                continue
            violations.extend(_check_event(cr.persona_id, ev, racks_by_id, face_sku, sku_to_racks))
    return violations


def _check_event(
    persona_id: str,
    ev: TimelineEvent,
    racks_by_id: dict[str, Rack],
    face_sku: dict[tuple[str, Face, int | None], dict[str, list[SlotItem]]],
    sku_to_racks: dict[str, set[str]],
) -> list[BuyViolation]:
    out: list[BuyViolation] = []
    if ev.target_rack not in racks_by_id:
        out.append(BuyViolation(persona_id, ev.elapsed_sec, ev.target_rack, ev.face, ev.product_sku, "unknown_rack"))
        return out
    if ev.product_sku and ev.product_sku not in sku_to_racks:
        out.append(BuyViolation(persona_id, ev.elapsed_sec, ev.target_rack, ev.face, ev.product_sku, "sku_not_in_store"))
        return out

    rack = racks_by_id[ev.target_rack]
    if ev.face is None:
        out.append(BuyViolation(persona_id, ev.elapsed_sec, ev.target_rack, ev.face, ev.product_sku, "face_none"))
        return out

    dx, dy = FACE_OFFSETS[ev.face]
    block = next((idx for idx, position in enumerate(rack.occupied_positions)
                  if position == (ev.x - dx, ev.y - dy)), None)
    # Older saved timelines can lack a usable stance; retain their face-level check.
    if any(bf.face == ev.face and (block is None or bf.block == block) for bf in rack.locked_faces):
        out.append(BuyViolation(persona_id, ev.elapsed_sec, ev.target_rack, ev.face, ev.product_sku, "locked_face"))

    items = face_sku.get((ev.target_rack, ev.face, block), {}).get(ev.product_sku)
    if not items:
        out.append(BuyViolation(persona_id, ev.elapsed_sec, ev.target_rack, ev.face, ev.product_sku, "sku_not_on_face"))
        return out

    # Several levels can offer the same SKU with different names/prices. Match
    # one actual offer; do not combine a name from one with a price from another.
    item = min(items, key=lambda item: int(bool(ev.product_name) and item.name != ev.product_name)
               + int(item.price != ev.price))
    if ev.product_name and item.name != ev.product_name:
        out.append(BuyViolation(
            persona_id, ev.elapsed_sec, ev.target_rack, ev.face, ev.product_sku,
            "name_mismatch", detail=f"event={ev.product_name!r} slot={item.name!r}",
        ))
    if item.price != ev.price:
        out.append(BuyViolation(
            persona_id, ev.elapsed_sec, ev.target_rack, ev.face, ev.product_sku,
            "price_mismatch", detail=f"event={ev.price} slot={item.price}",
        ))
    return out
