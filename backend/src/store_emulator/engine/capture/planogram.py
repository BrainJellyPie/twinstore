"""Recognised shelf → Parastore planogram: rack slots, a replaced rack face, or new racks on the floor.

A Parastore rack face has RACK_LEVELS levels and at most 4 items per (block, face, level) slot;
facings are expressed the way the rest of the app does it — the same SKU repeated in a slot. A
photo usually shows more than that: levels are merged by height (see `bands.band_levels`), and
per level the products with the most facings are kept, their facings scaled down proportionally
(largest remainder, at least one each). New racks split the photo left→right, so a wide gondola
becomes several neighbouring racks with every product kept.
"""

import difflib
import hashlib
import math
from dataclasses import dataclass, field
from typing import Literal

from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.domain.rack import (
    RACK_LEVELS,
    SLOT_CAPABLE_TYPES,
    Rack,
    RackType,
    Slot,
    SlotItem,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import FACE_OFFSETS, Face
from store_emulator.engine.layout_gen.catalog import CATALOG, category_label
from store_emulator.engine.validation import list_blocked_faces, validate

from .catalog_match import normalize_text, typical_price

SLOT_CAPACITY = 4
# Front face → rack rotation, following the grid editor (rotation 0 ⇒ front S; 90:W, 180:N, 270:E).
_ROTATION_FOR_FACE: dict[Face, Literal[0, 90, 180, 270]] = {Face.S: 0, Face.W: 90, Face.N: 180, Face.E: 270}


def sku_for(name: str, brand: str, size: str) -> str:
    """Stable SKU id for a recognised product (same name/brand/size → same SKU across captures)."""
    key = "|".join(normalize_text(v) for v in (name, brand, size))
    return "cap_" + hashlib.sha1(key.encode()).hexdigest()[:10]


def display_name(item: CaptureItem) -> str:
    """Name as stored on the planogram: brand + name + size, without repeating parts."""
    name = item.name.strip()
    lowered = name.lower()
    if item.brand and item.brand.lower() not in lowered:
        name = f"{item.brand.strip()} {name}".strip()
    if item.size and item.size.lower().replace(" ", "") not in lowered.replace(" ", ""):
        name = f"{name} {item.size.strip()}".strip()
    return name or "Unknown product"


def item_center(item: CaptureItem) -> float:
    if not item.boxes:
        return float(item.order)
    return sum(b.cx for b in item.boxes) / len(item.boxes)


def level_rows(result: CaptureResult) -> dict[int, list[CaptureItem]]:
    """Items per Parastore level, left → right (bands merged into one level are interleaved by position)."""
    rows: dict[int, list[CaptureItem]] = {}
    for item in result.items:
        rows.setdefault(item.level, []).append(item)
    for items in rows.values():
        items.sort(key=item_center)
    return rows


def fit_row(items: list[CaptureItem], capacity: int) -> tuple[list[tuple[CaptureItem, int]], list[CaptureItem]]:
    """Fit a row of products into `capacity` positions: (item, facings) in shelf order, and the dropped items."""
    if capacity <= 0:
        return [], list(items)
    kept = list(items)
    dropped: list[CaptureItem] = []
    if len(kept) > capacity:
        ranked = sorted(range(len(kept)), key=lambda i: (-kept[i].facings, i))
        keep_idx = set(ranked[:capacity])
        dropped = [it for i, it in enumerate(kept) if i not in keep_idx]
        kept = [it for i, it in enumerate(kept) if i in keep_idx]
    total = sum(it.facings for it in kept)
    if total <= capacity:
        return [(it, it.facings) for it in kept], dropped
    # Largest remainder, at least one facing each.
    spare = capacity - len(kept)
    extra = [(it.facings - 1) * spare / max(1, total - len(kept)) for it in kept]
    base = [math.floor(e) for e in extra]
    left = spare - sum(base)
    order = sorted(range(len(kept)), key=lambda i: -(extra[i] - base[i]))
    for i in order[:left]:
        base[i] += 1
    return [(it, 1 + b) for it, b in zip(kept, base, strict=True)], dropped


def slot_entries(fitted: list[tuple[CaptureItem, int]]) -> list[SlotItem]:
    out: list[SlotItem] = []
    for item, n in fitted:
        entry = SlotItem(sku=item.sku, name=display_name(item), price=max(0, item.price or 0))
        # Facings are independently editable placements. Sharing one model makes
        # later in-place price changes compound once per occurrence of that model.
        out.extend(entry.model_copy(deep=True) for _ in range(n))
    return out


@dataclass
class PlacementReport:
    rack_ids: list[str] = field(default_factory=list[str])
    face: Face = Face.S
    placed_items: int = 0
    placed_facings: int = 0
    dropped: list[str] = field(default_factory=list[str])
    notes: list[str] = field(default_factory=list[str])


def _blocks_along(rack: Rack, face: Face) -> list[int]:
    """Blocks of `rack` exposing `face`, in the order the face is read (left → right)."""
    cells = rack.block_cells
    blocks = [i for i in range(len(cells)) if face in rack.valid_faces(i)]
    return sorted(blocks, key=lambda i: cells[i][1] if face in (Face.N, Face.S) else cells[i][0])


def face_slots_from_capture(
    result: CaptureResult, blocks: list[int], face: Face, report: PlacementReport,
) -> list[Slot]:
    capacity = SLOT_CAPACITY * len(blocks)
    slots: list[Slot] = []
    for level, items in sorted(level_rows(result).items()):
        fitted, dropped = fit_row(items, capacity)
        report.dropped += [display_name(d) for d in dropped]
        report.placed_items += len(fitted)
        entries = slot_entries(fitted)
        report.placed_facings += len(entries)
        for k, block in enumerate(blocks):
            chunk = entries[k * SLOT_CAPACITY:(k + 1) * SLOT_CAPACITY]
            if chunk:
                slots.append(Slot(block=block, face=face, level=min(RACK_LEVELS, max(1, level)), items=chunk))
    return slots


def _reachable_face(store: Store, rack: Rack) -> Face | None:
    blocked = {(b.block, b.face) for b in list_blocked_faces(store) if b.rack_id == rack.id}
    locked = {(b.block, b.face) for b in rack.locked_faces}
    for face in (Face.S, Face.N, Face.W, Face.E):
        if face in rack.valid_faces(0) and (0, face) not in blocked and (0, face) not in locked:
            return face
    return None


def match_store_skus(store: Store, result: CaptureResult, report: PlacementReport, *, exact: bool = False) -> CaptureResult:
    """Products the store already sells keep their SKU and name, so sales of one product roll up
    across racks (and POS data still matches). Matching is by name (+ size), exact or ≥ 0.92 similar.
    With exact=True, only the complete display name (including brand/size) is matched.
    The price read off the tag wins over the stored one unless it was only estimated."""
    known: dict[str, SlotItem] = {}
    for _, slot in store.all_slots:
        for entry in slot.items:
            known.setdefault(normalize_text(entry.name), entry)
    if not known:
        return result
    names = list(known)
    items: list[CaptureItem] = []
    matched = 0
    for item in result.items:
        if not item.labeled:
            items.append(item)
            continue
        key = normalize_text(display_name(item))
        hit = known.get(key) if exact else known.get(key) or known.get(normalize_text(item.name))
        if hit is None and not exact:
            close = difflib.get_close_matches(key, names, n=1, cutoff=0.92)
            hit = known[close[0]] if close else None
        if hit is None:
            items.append(item)
            continue
        matched += 1
        price = hit.price if item.price_estimated or item.price is None else item.price
        items.append(item.model_copy(update={"sku": hit.sku, "name": hit.name, "brand": "", "size": "", "price": price}))
    if matched:
        report.notes.append(f"{matched} product(s) matched items the store already sells and keep their SKU")
    return result.model_copy(update={"items": items})


def _fill_missing_prices(result: CaptureResult, category: str, report: PlacementReport) -> CaptureResult:
    """Unread products without any category hint get the typical price of the target rack's category."""
    missing = [i for i in result.items if i.price is None]
    if not missing:
        return result
    typical, _ = typical_price(category, "", result.currency) if category in CATALOG else (None, "")
    if typical is None:
        report.notes.append(f"{len(missing)} product(s) have no price; set prices before simulating")
        return result
    items = [i.model_copy(update={"price": typical, "price_estimated": True}) if i.price is None else i for i in result.items]
    return result.model_copy(update={"items": items})


def replace_rack_face(store: Store, result: CaptureResult, rack_id: str, face: Face | None = None) -> tuple[Store, PlacementReport]:
    """Copy of `store` whose rack `rack_id` shows the captured planogram on `face`.

    Without `face`, the face currently holding the most items is replaced (or, for an empty rack,
    the first reachable one). Slots on the rack's other faces are kept.
    """
    new = store.model_copy(deep=True)
    rack = next((r for r in new.racks if r.id == rack_id), None)
    if rack is None:
        raise ValueError(f"rack not found: {rack_id}")
    if rack.type not in SLOT_CAPABLE_TYPES:
        raise ValueError(f"rack '{rack_id}' ({rack.type.value}) cannot hold products")
    if face is None:
        counts: dict[Face, int] = {}
        for s in rack.slots:
            counts[s.face] = counts.get(s.face, 0) + len(s.items)
        face = max(counts, key=lambda f: counts[f]) if counts else _reachable_face(new, rack)
    if face is None:
        raise ValueError(f"rack '{rack_id}' has no reachable face")
    blocks = _blocks_along(rack, face)
    if not blocks:
        raise ValueError(f"rack '{rack_id}' has no exposed {face.value} face")
    if any(bf.face == face and bf.block in blocks for bf in rack.locked_faces):
        raise ValueError(f"face {face.value} of rack '{rack_id}' is locked")
    report = PlacementReport(rack_ids=[rack.id], face=face)
    result = _fill_missing_prices(match_store_skus(store, result, report), rack.rack_desc, report)
    kept = [s for s in rack.slots if s.face != face]
    rack.slots = kept + face_slots_from_capture(result, blocks, face, report)
    if report.dropped:
        report.notes.append(
            f"{len(report.dropped)} product(s) did not fit the {SLOT_CAPACITY}-per-level face; "
            "add the photo as new racks to keep every product"
        )
    return new, report


# ── new racks on free floor ──────────────────────────────────────────────────────

def _issue_keys(store: Store) -> set[tuple[str, str]]:
    return {(i.code, i.message) for i in validate(store)}


def _candidate_runs(store: Store, k: int) -> list[tuple[list[tuple[int, int]], Face]]:
    """Runs of k free tiles with the face looking into the room; wall runs first."""
    w, h = store.grid_size
    occupied = {p for r in store.racks for p in r.occupied_positions}
    runs: list[tuple[int, list[tuple[int, int]], Face]] = []
    for face in (Face.S, Face.W, Face.E, Face.N):
        dx, dy = FACE_OFFSETS[face]
        horizontal = face in (Face.N, Face.S)
        for y in range(h):
            for x in range(w):
                tiles = [(x + i, y) if horizontal else (x, y + i) for i in range(k)]
                if any(not (0 <= tx < w and 0 <= ty < h) or (tx, ty) in occupied for tx, ty in tiles):
                    continue
                fronts = [(tx + dx, ty + dy) for tx, ty in tiles]
                if any(not (0 <= fx < w and 0 <= fy < h) or (fx, fy) in occupied for fx, fy in fronts):
                    continue
                back = [(tx - dx, ty - dy) for tx, ty in tiles]
                against_wall = all(not (0 <= bx < w and 0 <= by < h) for bx, by in back)
                touching = sum(1 for bx, by in back if (bx, by) in occupied)
                rank = 0 if against_wall else (1 if touching == k else 2)
                runs.append((rank, tiles, face))
    runs.sort(key=lambda r: r[0])
    return [(tiles, face) for _, tiles, face in runs]


def _new_rack_id(store: Store) -> str:
    taken = {r.id for r in store.racks}
    n = 1
    while f"r_cap_{n:02d}" in taken:
        n += 1
    return f"r_cap_{n:02d}"


def add_capture_racks(
    store: Store, results: list[CaptureResult], *, max_racks_per_photo: int = 4, exact_sku_match: bool = False,
) -> tuple[Store, PlacementReport]:
    """Copy of `store` with each captured shelf added as new rack(s) on free floor.

    A photo whose widest level holds more than 4 facings becomes ceil(facings / 4) neighbouring racks
    (at most `max_racks_per_photo`), products assigned by their position across the photo.
    """
    new = store.model_copy(deep=True)
    report = PlacementReport()
    for result in results:
        result = match_store_skus(new, result, report, exact=exact_sku_match)
        rows = level_rows(result)
        widest = max((sum(i.facings for i in items) for items in rows.values()), default=0)
        k = max(1, min(max_racks_per_photo, math.ceil(widest / SLOT_CAPACITY)))
        placed = _place_photo(new, result, k, report)
        if placed is None and k > 1:
            report.notes.append(f"no free run of {k} tiles; placing the photo on a single rack")
            placed = _place_photo(new, result, 1, report)
        if placed is None:
            raise ValueError("no free floor position with an aisle in front of it for a new rack")
        new = placed
    return new, report


def _split_columns(result: CaptureResult, k: int) -> list[CaptureResult]:
    """Split a capture into k left→right parts by product position."""
    if k == 1:
        return [result]
    xs = [b.x1 for i in result.items for b in i.boxes] + [b.x2 for i in result.items for b in i.boxes]
    lo, hi = (min(xs), max(xs)) if xs else (0.0, 1.0)
    parts: list[list[CaptureItem]] = [[] for _ in range(k)]
    for item in result.items:
        pos = (item_center(item) - lo) / max(1e-6, hi - lo)
        parts[min(k - 1, max(0, math.floor(pos * k)))].append(item)
    return [result.model_copy(update={"items": items}) for items in parts]


def _place_photo(store: Store, result: CaptureResult, k: int, report: PlacementReport) -> Store | None:
    before = _issue_keys(store)
    category = result.dominant_category
    label = category_label(category, result.currency) if category else "Captured shelf"
    rack_type = RackType.FRIDGE if result.rack_type == "fridge" else RackType.SHELF
    parts = _split_columns(result, k)
    for tiles, face in _candidate_runs(store, k):
        trial = store.model_copy(deep=True)
        trial_report = PlacementReport(face=face)
        ids: list[str] = []
        # Parts go left to right as a shopper facing the shelf sees it: runs list tiles by ascending x / y, which is
        # left to right from the south and west sides but right to left from the north and east ones.
        seen_order = tiles if face in (Face.S, Face.W) else list(reversed(tiles))
        for part, (x, y) in zip(parts, seen_order, strict=True):
            rid = _new_rack_id(trial)
            rack = Rack(
                id=rid, type=rack_type, shape=[[1]], position=(x, y),
                rotation=_ROTATION_FOR_FACE[face],
                rack_name=f"{label} (photo)", rack_desc=category, design_variant="a",
            )
            rack.slots = face_slots_from_capture(part, [0], face, trial_report)
            trial.racks.append(rack)
            ids.append(rid)
        after = _issue_keys(trial)
        if after - before:
            continue
        blocked = {(b.rack_id, b.face) for b in list_blocked_faces(trial)}
        if any((rid, face) in blocked for rid in ids):
            continue
        report.rack_ids += ids
        report.face = face
        report.placed_items += trial_report.placed_items
        report.placed_facings += trial_report.placed_facings
        report.dropped += trial_report.dropped
        return trial
    return None
