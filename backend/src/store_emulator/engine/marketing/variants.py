"""Variant layouts for marketing A/B tests: the control store with one or more changes applied.

Every function returns a new Store; the control is never modified. Changes that cannot apply (an
unknown SKU, a full shelf with nothing to swap) are reported as warnings instead of failing the test.
"""

import math
from collections.abc import Mapping

from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.validation import list_blocked_faces

MAX_ITEMS_PER_SLOT = 4


def _occurrences(store: Store, sku: str) -> list[tuple[Rack, Slot, int]]:
    return [(rack, slot, i) for rack in store.racks for slot in rack.slots for i, item in enumerate(slot.items) if item.sku == sku]


def _name(store: Store, sku: str) -> str:
    occ = _occurrences(store, sku)
    return occ[0][1].items[occ[0][2]].name if occ else sku


def charm_price(price: int, minor_per_major: int = 100, *, up: bool = False) -> int:
    """The price ending in .99 at or just below `price` (at or just above it with `up`), for currencies with cents.
    A price under .99 (a free product among them) stays as it is."""
    if minor_per_major <= 1 or price < minor_per_major - 1:
        return price
    if up:
        return math.ceil((price + 1) / minor_per_major) * minor_per_major - 1
    return (price + 1) // minor_per_major * minor_per_major - 1


def _busiest_face(rack: Rack, blocked: set[tuple[int, Face]] | None = None) -> Face | None:
    counts: dict[Face, int] = {}
    for s in rack.slots:
        if blocked and (s.block, s.face) in blocked:
            continue
        counts[s.face] = counts.get(s.face, 0) + len(s.items)
    return max(counts, key=lambda f: counts[f]) if counts else None


_BLOCKED = {
    "locked": "the face is locked",
    "out_of_bounds": "it faces the outer wall",
    "occupied": "another fixture stands in front of it",
    "unreachable": "no aisle leads to it",
}


def _target_slots(store: Store, rack: Rack, face: Face, level: int) -> tuple[list[Slot], list[str]]:
    """Slots at `face` / `level` of every block that has that face and whose face shoppers can reach, plus detached
    empty slots when missing, and why the face cannot be reached on the other blocks. The simulation clears products from faces
    nobody can reach (validation.clear_blocked_slots), so a product moved there would leave the test."""
    blocked = {(b.block, b.face): b.reasons for b in list_blocked_faces(store) if b.rack_id == rack.id}
    out: list[Slot] = []
    reasons: list[str] = []
    for block in range(len(rack.block_cells)):
        if face not in rack.valid_faces(block):
            continue
        if why := blocked.get((block, face)):
            reasons.extend(_BLOCKED.get(r, r) for r in why if _BLOCKED.get(r, r) not in reasons)
            continue
        slot = next((s for s in rack.slots if s.block == block and s.face == face and s.level == level), None)
        if slot is None:
            slot = Slot(block=block, face=face, level=level)
        out.append(slot)
    return out, reasons


def _move(store: Store, change: VariantChange) -> tuple[str, list[str]]:
    rack = next((r for r in store.racks if r.id == change.rack_id), None)
    if rack is None:
        return "", [f"move: rack {change.rack_id or '(none)'} not found"]
    blocked_sources = {(b.rack_id, b.block, b.face) for b in list_blocked_faces(store)}
    # Drafts choose a shelf, not a face. Prefer an existing reachable side;
    # retain the usual blocked-face diagnostic when no such side exists.
    face = Face(change.face) if change.face else (
        _busiest_face(rack, {(block, side) for rid, block, side in blocked_sources if rid == rack.id}) or _busiest_face(rack))
    if face is None:
        return "", [f"move: rack {rack.rack_name or rack.id} has no shelves to move to"]
    level = change.level or 3
    targets, blocked = _target_slots(store, rack, face, level)
    if not targets and blocked:
        return "", [(f"move: shoppers cannot reach the {face.value} face of {rack.rack_name or rack.id} ({'; '.join(blocked)}), "
                     f"so {_name(store, change.sku)} stays where it is: pick a face along an aisle")]
    if not targets:
        return "", [f"move: rack {rack.rack_name or rack.id} has no {face.value} face"]
    warnings: list[str] = []
    moved = 0
    for dst in targets:
        # one facing per target slot, taken from wherever the product stands outside the targets
        sources = [(r, s, i) for r, s, i in _occurrences(store, change.sku) if all(s is not t for t in targets)]
        if not sources:
            break
        # A full destination swaps its last product back into the source. That
        # source must be accessible too, or the swap silently delists another SKU.
        src = next(((s, i) for r, s, i in sources if len(dst.items) < MAX_ITEMS_PER_SLOT
                    or (r.id, s.block, s.face) not in blocked_sources), None)
        if src is None:
            warnings.append(f"move: {rack.rack_name or rack.id} block {dst.block} {face.value} level {level} is full; "
                            "no accessible source can hold the displaced product, so this slot was left unchanged")
            continue
        src_slot, idx = src
        item = src_slot.items[idx]
        if len(dst.items) < MAX_ITEMS_PER_SLOT:
            src_slot.items.pop(idx)
            dst.items.append(item)
        else:
            # Full shelf: the product trades places with the last product there, so both keep their facings.
            displaced = dst.items[-1]
            dst.items[-1] = item
            src_slot.items[idx] = displaced
        if all(dst is not existing for existing in rack.slots):
            rack.slots.append(dst)
        moved += 1
    if not moved:
        return "", warnings or [f"move: {change.sku} is already there or not in the store"]
    where = f"{rack.rack_name or rack.id} · {face.value} · level {level}"
    return f"moved {_name(store, change.sku)} to {where} ({moved} facing{'s' if moved > 1 else ''})", warnings


def apply_changes(
    control: Store,
    changes: list[VariantChange],
    *,
    package_uris: Mapping[str, str] | None = None,
    minor_per_major: int = 100,
    remember_old_prices: bool = True,
) -> tuple[Store, list[str], list[str]]:
    """The control with `changes` applied in order, what changed (in words) and warnings.

    `remember_old_prices`: a category price change keeps the old price as the reference shoppers compare with (a
    test of a price change); off for a layout saved with new everyday prices, which shoppers take as they are.

    `package_uris` maps product image ids to the URI stored on the slot item (`image_url`), which the
    vision shoppers' shelf renderer draws instead of the plain package.
    """
    store = control.model_copy(deep=True)
    applied: list[str] = []
    warnings: list[str] = []
    for change in changes:
        if change.kind == "category_price":
            if change.percent is None:
                warnings.append("category price: no percentage given")
                continue
            key = change.category.strip().lower()
            racks = [r for r in store.racks if key and (key in r.rack_desc.lower() or key in r.rack_name.lower())]
            items = [item for r in racks for s in r.slots for item in s.items]
            if not items:
                warnings.append(f"category price: no products under '{change.category}'")
                continue
            changed: dict[str, tuple[int, int]] = {}
            for item in items:
                old = item.price
                new = max(0, round(old * (1 + change.percent / 100)))
                if change.charm:
                    charmed = charm_price(new, minor_per_major)
                    # Rounding down must not turn a rise into a cut (or no change): a rise ends on the next .99 up.
                    new = charm_price(new, minor_per_major, up=True) if change.percent > 0 and charmed <= old else charmed
                if new != old and remember_old_prices:
                    # Shoppers remember the old price, as with a discount: rule shoppers weigh the new price against
                    # it and a cut shows it on the tag; without it a category price change looked free to them.
                    item.regular_price = item.regular_price or old
                elif new != old:
                    item.regular_price = 0   # the new everyday price: nothing to compare it with
                item.price = new
                changed.setdefault(item.sku, (old, new))
            actual = ""
            if change.charm:
                ratios = [new / old - 1 for old, new in changed.values() if old > 0]
                if ratios:
                    actual = f", {sum(ratios) / len(ratios) * 100:+.1f} % on average"
            remembered = "; shoppers remember the old prices" if remember_old_prices else ""
            applied.append(f"{change.category}: every price {change.percent:+g} %{' and ending in .99' if change.charm else ''}"
                           f"{actual} ({len(items)} items{remembered})")
            continue

        occ = _occurrences(store, change.sku)
        if change.kind != "move" and not occ:
            warnings.append(f"{change.kind}: product {change.sku or '(none)'} is not in this layout")
            continue
        items: list[SlotItem] = [slot.items[i] for _, slot, i in occ]
        name = items[0].name if items else change.sku
        match change.kind:
            case "price":
                if change.price is None:
                    warnings.append(f"price: no price given for {name}")
                    continue
                old = items[0].price
                for item in items:
                    reference = (item.regular_price or item.price) if change.keep_reference else 0
                    item.price, item.regular_price = change.price, reference
                applied.append(f"{name}: price {old} → {change.price}{' (shoppers remember ' + str(old) + ')' if change.keep_reference else ''}")
            case "discount":
                if change.percent is None or change.percent >= 0:
                    warnings.append(f"discount: give a negative percentage for {name}")
                    continue
                for item in items:
                    regular = item.regular_price or item.price
                    item.price = max(0, round(regular * (1 + change.percent / 100)))
                    item.regular_price = regular
                applied.append(f"{name}: {change.percent:g} % off, tag shows the was-price")
            case "promo":
                text = change.promo.strip() or "SALE"
                for item in items:
                    item.promo = text
                applied.append(f"{name}: '{text}' sign")
            case "package":
                uri = (package_uris or {}).get(change.asset_id)
                if uri is None:
                    warnings.append(f"package: product image {change.asset_id or '(none)'} not found")
                    continue
                for item in items:
                    item.image_url = uri
                applied.append(f"{name}: new package ({change.asset_id})")
            case "move":
                text, warn = _move(store, change)
                warnings.extend(warn)
                if text:
                    applied.append(text)
    return store, applied, warnings
