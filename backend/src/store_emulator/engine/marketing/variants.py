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

MAX_ITEMS_PER_SLOT = 4


def _occurrences(store: Store, sku: str) -> list[tuple[Rack, Slot, int]]:
    return [(rack, slot, i) for rack in store.racks for slot in rack.slots for i, item in enumerate(slot.items) if item.sku == sku]


def _name(store: Store, sku: str) -> str:
    occ = _occurrences(store, sku)
    return occ[0][1].items[occ[0][2]].name if occ else sku


def charm_price(price: int, minor_per_major: int = 100) -> int:
    """The price ending in .99 at or just above `price` (only for currencies with cents)."""
    if minor_per_major <= 1:
        return price
    return max(minor_per_major - 1, math.ceil((price + 1) / minor_per_major) * minor_per_major - 1)


def _busiest_face(rack: Rack) -> Face | None:
    counts: dict[Face, int] = {}
    for s in rack.slots:
        counts[s.face] = counts.get(s.face, 0) + len(s.items)
    return max(counts, key=lambda f: counts[f]) if counts else None


def _target_slots(rack: Rack, face: Face, level: int) -> list[Slot]:
    """Slots at `face` / `level` of every block that has that face, created when missing."""
    out: list[Slot] = []
    for block in range(len(rack.block_cells)):
        if face not in rack.valid_faces(block):
            continue
        slot = next((s for s in rack.slots if s.block == block and s.face == face and s.level == level), None)
        if slot is None:
            slot = Slot(block=block, face=face, level=level)
            rack.slots.append(slot)
        out.append(slot)
    return out


def _move(store: Store, change: VariantChange) -> tuple[str, list[str]]:
    rack = next((r for r in store.racks if r.id == change.rack_id), None)
    if rack is None:
        return "", [f"move: rack {change.rack_id or '(none)'} not found"]
    face = Face(change.face) if change.face else _busiest_face(rack)
    if face is None:
        return "", [f"move: rack {rack.rack_name or rack.id} has no shelves to move to"]
    level = change.level or 3
    targets = _target_slots(rack, face, level)
    if not targets:
        return "", [f"move: rack {rack.rack_name or rack.id} has no {face.value} face"]
    moved = 0
    for dst in targets:
        # one facing per target slot, taken from wherever the product stands outside the targets
        src = next(((s, i) for _, s, i in _occurrences(store, change.sku) if all(s is not t for t in targets)), None)
        if src is None:
            break
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
        moved += 1
    if not moved:
        return "", [f"move: {change.sku} is already there or not in the store"]
    where = f"{rack.rack_name or rack.id} · {face.value} · level {level}"
    return f"moved {_name(store, change.sku)} to {where} ({moved} facing{'s' if moved > 1 else ''})", []


def apply_changes(
    control: Store,
    changes: list[VariantChange],
    *,
    package_uris: Mapping[str, str] | None = None,
    minor_per_major: int = 100,
) -> tuple[Store, list[str], list[str]]:
    """The control with `changes` applied in order, what changed (in words) and warnings.

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
            for item in items:
                new = max(0, round(item.price * (1 + change.percent / 100)))
                item.price = charm_price(new, minor_per_major) if change.charm else new
                item.regular_price = 0
            applied.append(f"{change.category}: every price {change.percent:+g} %{' and ending in .99' if change.charm else ''} ({len(items)} items)")
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
                    item.price, item.regular_price = change.price, 0
                applied.append(f"{name}: price {old} → {change.price}")
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
