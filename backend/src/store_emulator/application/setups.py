import copy
import json
import logging
import re
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from filelock import FileLock, Timeout
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.rack import RACK_LEVELS, Face, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import RESOURCE_ID_PATTERN
from store_emulator.engine.validation import (
    BlockedFaceDetail, ClearedSlot, Issue, clear_blocked_slots,
    list_blocked_faces, validate,
)
from store_emulator.application.errors import AppError
from store_emulator.application.storage import images as image_storage
from store_emulator.application.storage.io import DATA_DIR, write_json, read_json
from store_emulator.application.storage.generations import find_active_generation, list_generations
from store_emulator.application.storage.setups import (
    read_setup, write_setup, list_setups, new_setup_data,
    delete_setup, find_descendants, metadata_path, personas_path, setup_path,
    read_state, write_state,
)


_SAFE_ID = re.compile(RESOURCE_ID_PATTERN)


def setup_lock_path(project_id: str, setup_id: str) -> Path:
    """Setup-specific lock file path. pid/sid whitelist blocks traversal.

    Lock directory is lazy-created so that tests using ``monkeypatch.chdir``
    still land in the right tmp ``.data/locks``.
    """
    if not _SAFE_ID.fullmatch(project_id) or not _SAFE_ID.fullmatch(setup_id):
        raise ValueError(f"unsafe pid/sid: {project_id}/{setup_id}")
    lock_dir = Path(DATA_DIR) / "locks" / project_id
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"setup_{setup_id}.lock"


def get_setups(project_id: str) -> list[dict[str, Any]]:
    """Setup summaries (store excluded) with readiness attached."""
    setups = list_setups(project_id, include_store=True)
    persona_count = _count_personas(project_id)
    gens = _running_generations(project_id)
    for s in setups:
        s["readiness"] = _compute_readiness(s, persona_count, gens)
        s.pop("store", None)
    return setups


def get_setup(project_id: str, setup_id: str) -> dict[str, Any]:
    """Full setup load with readiness. AppError(404) if missing."""
    try:
        setup = read_setup(project_id, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404)
    persona_count = _count_personas(project_id)
    gens = _running_generations(project_id)
    setup["readiness"] = _compute_readiness(setup, persona_count, gens)
    _resolve_slot_images(project_id, setup)
    return setup


def load_setup_with_validation(project_id: str, setup_id: str) -> dict[str, object]:
    """Setup load + ``list_blocked_faces`` + readiness in a single call (spec rev 4 decision 3).

    Returns a dict compatible with the SetupDetail wire schema. ``blocked_faces``
    is JSON-mode dumped; ``readiness`` is computed the same way as ``get_setup``
    so the GET handler completes in one read. Missing setup raises
    ``AppError(404, "setup_not_found", "not_found", ...)``.
    """
    try:
        setup = read_setup(project_id, setup_id)
    except FileNotFoundError:
        raise AppError(
            404,
            "setup_not_found",
            "not_found",
            f"Setup not found: {setup_id}",
            {},
        )
    blocked: list[BlockedFaceDetail] = []
    store_data = setup.get("store")
    if store_data is not None:
        try:
            store_obj: Store | None = Store.model_validate(store_data)
        except Exception:
            store_obj = None
        if store_obj is not None:
            blocked = list_blocked_faces(store_obj)
    persona_count = _count_personas(project_id)
    gens = _running_generations(project_id)
    result: dict[str, object] = dict(setup)
    result["blocked_faces"] = [bf.model_dump(mode="json") for bf in blocked]
    result["readiness"] = _compute_readiness(
        setup, persona_count, gens
    )
    _resolve_slot_images(project_id, result)
    return result


def _resolve_slot_images(project_id: str, setup: dict[str, object]) -> None:
    """Resolve current SKU photos, preserving reviewed immutable layout snapshots.

    Legacy SKU photos are resolved at read time; reviewed layout snapshots keep their own URL.
    """
    store_obj = setup.get("store")
    if not isinstance(store_obj, dict):
        return
    store_dict = cast(dict[str, object], store_obj)
    manifest = image_storage.load_manifest(project_id)
    racks_obj = store_dict.get("racks")
    if not isinstance(racks_obj, list):
        return
    racks_list = cast(list[object], racks_obj)
    for rack in racks_list:
        if not isinstance(rack, dict):
            continue
        rack_dict = cast(dict[str, object], rack)
        slots_obj = rack_dict.get("slots")
        if not isinstance(slots_obj, list):
            continue
        slots_list = cast(list[object], slots_obj)
        for slot in slots_list:
            if not isinstance(slot, dict):
                continue
            slot_dict = cast(dict[str, object], slot)
            items_obj = slot_dict.get("items")
            if not isinstance(items_obj, list):
                continue
            items_list = cast(list[object], items_obj)
            for item in items_list:
                if not isinstance(item, dict):
                    continue
                item_dict = cast(dict[str, object], item)
                sku = item_dict.get("sku")
                if not isinstance(sku, str):
                    continue
                stored_url = item_dict.get("image_url")
                item_dict["image_url"] = image_storage.layout_image_url(
                    project_id, sku, stored_url if isinstance(stored_url, str) else None, manifest,
                )


def compute_rack_fingerprint(store: Store | None) -> str:
    """Deterministic rack-only fingerprint (spec rev 4 decision 6).

    Excludes ``items``; only whitelisted fields are serialized. ``None`` becomes
    the ``"<NONE>"`` sentinel. racks / slots / locked_faces are all sorted so
    ordering differences are absorbed.
    """
    if store is None:
        return "<NONE>"
    racks_data: list[dict[str, object]] = []
    for rack in sorted(store.racks, key=lambda r: r.id):
        slots_meta: list[dict[str, object]] = sorted(
            [
                {"block": s.block, "face": s.face.value, "level": s.level}
                for s in rack.slots
            ],
            key=lambda d: (cast(int, d["block"]), cast(str, d["face"]), cast(int, d["level"])),
        )
        locked: list[dict[str, object]] = sorted(
            [{"block": lf.block, "face": lf.face.value} for lf in rack.locked_faces],
            key=lambda d: (cast(int, d["block"]), cast(str, d["face"])),
        )
        racks_data.append({
            "id": rack.id,
            "type": rack.type.value,
            "shape": rack.shape,
            "position": list(rack.position),
            "rotation": rack.rotation,
            "rack_name": rack.rack_name,
            "rack_desc": rack.rack_desc,
            "rack_decoration_desc": rack.rack_decoration_desc,
            "design_variant": rack.design_variant,
            "levels": rack.levels,
            "dwell_min": rack.dwell_min,
            "dwell_max": rack.dwell_max,
            "locked_faces": locked,
            "slots": slots_meta,
        })
    payload: dict[str, object] = {
        "grid_size": list(store.grid_size),
        "racks": racks_data,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def assert_setup_mutation_allowed(
    disk_setup: dict[str, object],
    incoming_setup: dict[str, object],
) -> None:
    """spec rev 4 decisions 3 + 6: runId / rack fingerprint / items checks.

    1. ``runId`` set → reject every change (no-op included).
       ``AppError(409, "setup_locked", "simulation_history_exists", ..., {"runId": ...})``.
    2. Rack fingerprint differs and disk items > 0 → ``AppError(409, "racks_locked", ...)``.
    3. Items-only or store-meta-only change → pass.
    """
    if disk_setup.get("runId"):
        raise AppError(
            409,
            "setup_locked",
            "simulation_history_exists",
            "setup cannot be modified because it has simulation history.",
            {"runId": disk_setup["runId"]},
        )
    disk_store_data = disk_setup.get("store")
    incoming_store_data = incoming_setup.get("store")
    if incoming_store_data is None:
        return  # name/memo-only change — no rack comparison needed
    if disk_setup.get("status") == "running" and incoming_store_data != disk_store_data:
        # The run that ends will lock the layout it simulated; an edit saved meanwhile would be locked unsimulated
        # (or lost to the run's own write).
        raise AppError(
            409,
            "setup_running",
            "simulation_running",
            "This layout is being simulated; save the change when the run ends.",
            {},
        )
    disk_store = (
        Store.model_validate(disk_store_data) if disk_store_data else None
    )
    incoming_store = Store.model_validate(incoming_store_data)
    if compute_rack_fingerprint(disk_store) == compute_rack_fingerprint(incoming_store):
        return  # no rack changes
    if disk_store is not None:
        item_count = sum(
            len(slot.items) for rack in disk_store.racks for slot in rack.slots
        )
        if item_count > 0:
            raise AppError(
                409,
                "racks_locked",
                "items_exist",
                "store layout cannot be modified while items are registered.",
                {"item_count": item_count},
            )


def save_setup_with_lock(
    project_id: str,
    setup_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    """Grid editor PUT save flow with filelock critical section (spec rev 4 §4.1).

    payload: SetupUpdatePayload (name / store / memo, optional).
    Returns a SaveSetupResponse-compatible dict:
    ``{"setup": ..., "cleared": [...], "blocked_faces": [...], "issues": [...]}``.

    Lock timeout=10s. The entire pipeline — disk read → policy check → validate
    → clear_blocked_slots → write — runs inside a single critical section so
    concurrent PUTs cannot produce partial writes.
    """
    try:
        with FileLock(str(setup_lock_path(project_id, setup_id)), timeout=10):
            try:
                disk_setup = read_setup(project_id, setup_id)
            except FileNotFoundError:
                raise AppError(
                    404, "setup_not_found", "not_found",
                    f"Setup not found: {setup_id}", {},
                )
            store_data = payload.get("store")
            try:
                assert_setup_mutation_allowed(disk_setup, payload)
                store_obj = Store.model_validate(store_data) if store_data is not None else None
            except ValidationError as e:
                msg = str(e).split("\n")[0][:200]
                raise AppError(
                    422, "invalid_store", "validation_error",
                    f"invalid store data: {msg}", {},
                ) from e
            cleared: list[ClearedSlot] = []
            issues: list[Issue] = []
            if store_obj is not None:
                issues = validate(store_obj)
                errors = [i for i in issues if i.severity == "error"]
                if errors:
                    raise AppError(
                        422, "validation_failed", "validation_error",
                        "store layout has errors.",
                        {"issues": [i.model_dump(mode="json") for i in issues]},
                    )
                cleared = clear_blocked_slots(store_obj)
                disk_setup["store"] = store_obj.model_dump(mode="json")
            name_val = payload.get("name")
            if isinstance(name_val, str):
                disk_setup["name"] = name_val
            memo_val = payload.get("memo")
            if isinstance(memo_val, str):
                disk_setup["memo"] = memo_val
            write_setup(project_id, setup_id, disk_setup)
            blocked = list_blocked_faces(store_obj) if store_obj is not None else []
            warnings = [i for i in issues if i.severity == "warning"]
            return {
                "setup": disk_setup,
                "cleared": [c.model_dump(mode="json") for c in cleared],
                "blocked_faces": [bf.model_dump(mode="json") for bf in blocked],
                "issues": [w.model_dump(mode="json") for w in warnings],
            }
    except Timeout:
        raise AppError(
            503, "setup_lock_timeout", "lock_timeout",
            "another request is modifying this setup. Please retry shortly.",
            {"timeout_seconds": 10},
        )


def _count_personas(project_id: str) -> int:
    p_file = personas_path(project_id)
    if not p_file.exists():
        return 0
    try:
        data: object = read_json(p_file)
    except ValueError as e:   # damaged: the layouts still open and say the customers are missing
        logger.warning(f"[setups] {project_id}: {e}")
        return 0
    return len(cast(list[object], data)) if isinstance(data, list) else 0


def _running_generations(project_id: str) -> list[dict[str, Any]]:
    return [g for g in list_generations(project_id) if g.get("status") in ("pending", "running")]


def setup_summary(project_id: str, setup: dict[str, Any]) -> dict[str, Any]:
    """Summary with store excluded and readiness attached. Shared by new-setup responses."""
    summary = {k: v for k, v in setup.items() if k != "store"}
    persona_count = _count_personas(project_id)
    gens = _running_generations(project_id)
    summary["readiness"] = _compute_readiness(setup, persona_count, gens)
    return summary


def _compute_readiness(
    setup: dict[str, Any],
    persona_count: int,
    gens: list[dict[str, Any]],
) -> dict[str, Any]:
    """Whether simulation can start, with reason codes. ``ready=True`` allows start.

    reasons code:
    - layout_pending: layout generation in progress
    - personas_pending: persona generation in progress
    - no_layout: store missing (layout not generated)
    - no_personas: zero personas
    - no_items: zero items across slots
    - no_entrance: zero entrance racks
    - no_exit: zero exit racks
    - no_counter: zero counter racks
    """
    reasons: list[str] = []
    for g in gens:
        if g.get("kind") == "layout" and g.get("setup_id") == setup.get("id"):
            reasons.append("layout_pending")
        elif g.get("kind") == "persona":
            reasons.append("personas_pending")

    store = setup.get("store")
    if not store:
        if "layout_pending" not in reasons:
            reasons.append("no_layout")
    else:
        try:
            store_obj = Store.model_validate(store)
        except Exception as exc:
            # Invalid store data — don't break readiness, surface as no_items.
            # The write paths (save_setup, replace_slots) raise 400 on the same
            # error, so a malformed store that only manifests here is logged.
            logger.warning(
                "readiness: store validation failed setup_id=%s err=%s",
                setup.get("id"), str(exc).split("\n", 1)[0][:200],
            )
            store_obj = None
        if store_obj is None:
            reasons.append("no_items")
        else:
            total_items = sum(
                len(s.items) for r in store_obj.racks for s in r.slots
            )
            if total_items == 0:
                reasons.append("no_items")
            if not store_obj.entrances:
                reasons.append("no_entrance")
            if not store_obj.exits:
                reasons.append("no_exit")
            if not store_obj.counters:
                reasons.append("no_counter")

    if persona_count == 0 and "personas_pending" not in reasons:
        reasons.append("no_personas")

    return {"ready": len(reasons) == 0, "reasons": reasons}


def set_active_setup(project_id: str, setup_id: str | None) -> None:
    state = read_state(project_id)
    state["activeSetupId"] = setup_id
    write_state(project_id, state)


def save_setup(
    project_id: str,
    setup_id: str,
    store: dict[str, Any] | None,
    name: str | None = None,
    memo: str | None = None,
) -> list[ClearedSlot]:
    """Save setup.

    - store change: only when status=draft and no active layout generation.
      Items on unreachable faces are auto-removed.
    - name/memo: allowed regardless of status.

    Returns ClearedSlot list of slots auto-removed.
    """
    try:
        setup = read_setup(project_id, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404)

    cleared: list[ClearedSlot] = []
    if store is not None:
        if setup["status"] != "draft":
            raise AppError(
                f"setup status is {setup['status']}. Branch a new setup before modifying.", 409,
            )
        # A running layout regeneration will overwrite store; protect user edits.
        if find_active_generation(project_id, setup_id, "layout"):
            raise AppError("layout generation is in progress. Retry once it completes.", 409)
        try:
            store_obj = Store.model_validate(store)
        except Exception as e:
            raise AppError(f"invalid store data: {str(e).split(chr(10))[0][:200]}", 400)
        # No entrance → reachability is undefined. clear_blocked_slots returns
        # an empty result silently, so reject here to keep util/save consistent.
        if not store_obj.entrances:
            raise AppError("cannot save store without an entrance.", 400)
        cleared = clear_blocked_slots(store_obj)
        if cleared:
            store = store_obj.model_dump(mode="json")
        setup["store"] = store
    if name is not None:
        setup["name"] = name
    if memo is not None:
        setup["memo"] = memo
    write_setup(project_id, setup_id, setup)
    return cleared



@dataclass(frozen=True, slots=True)
class ReplaceSlotsResult:
    count: int
    cleared: list[ClearedSlot]


def replace_slots(
    project_id: str,
    setup_id: str,
    slot_specs: list[dict[str, Any]],
) -> ReplaceSlotsResult:
    """Recompute all slots on a draft setup. Validates coords / locked / level.

    Each slot_specs row: rack_id, block, face, level, sku, name, price, promo.
    On success, replaces setup.store.racks[].slots.

    Multiple rows on the same coord (rack_id, block, face, level) are
    accumulated as SlotItems; each SKU keeps its own name/price/promo. There
    is no cross-row uniqueness check.

    A row with empty sku ("") produces no SlotItem, and a coord with zero
    non-empty items produces no Slot at all (sparse representation — empty
    coords are simply missing from the list).

    Returns ``ReplaceSlotsResult(count, cleared)``:
    - count: registered SKU placements (summed across slot.items)
    - cleared: ClearedSlot list for unreachable slots auto-removed post-upload

    Errors:
    - 404: setup missing
    - 409: not draft / layout generation in progress
    - 400: store missing / coord / level / face format errors
    """
    try:
        setup = read_setup(project_id, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404)
    if setup["status"] != "draft":
        raise AppError(f"setup status is {setup['status']}. Branch a new setup before modifying.", 409)

    if find_active_generation(project_id, setup_id, "layout"):
        raise AppError("layout generation is in progress. Retry once it completes.", 409)

    store_data = setup.get("store")
    if not store_data:
        raise AppError("no store layout.", 400)
    try:
        store = Store.model_validate(store_data)
    except Exception as e:
        raise AppError(f"invalid store data: {str(e).split(chr(10))[0][:200]}", 400)

    racks_by_id = {r.id: r for r in store.racks}
    locked_by_rack: dict[str, set[tuple[int, Face]]] = {
        r.id: {(bf.block, bf.face) for bf in r.locked_faces}
        for r in store.racks
    }
    valid_face_by_rack: dict[str, dict[int, set[Face]]] = {}
    for r in store.racks:
        valid_face_by_rack[r.id] = {
            idx: set(r.valid_faces(idx)) for idx in range(len(r.block_cells))
        }

    @dataclass(slots=True)
    class _SlotAccum:
        rack_id: str
        block: int
        face: Face
        level: int
        items: list[SlotItem] = field(default_factory=list[SlotItem])

    slot_by_coord: dict[tuple[str, int, Face, int], _SlotAccum] = {}

    for row_idx, spec in enumerate(slot_specs, start=1):
        rack_id = str(spec.get("rack_id", "")).strip()
        if not rack_id:
            continue
        if rack_id not in racks_by_id:
            raise AppError(f"row {row_idx}: rack_id '{rack_id}' not found", 400)
        try:
            block = int(spec["block"])
            face_str = str(spec["face"]).strip().upper()
            level = int(spec["level"])
        except (KeyError, ValueError, TypeError):
            raise AppError(f"row {row_idx}: block/face/level format error", 400)
        if face_str not in Face.__members__:
            raise AppError(f"row {row_idx}: invalid face '{face_str}'", 400)
        if level < 1 or level > RACK_LEVELS:
            raise AppError(
                f"row {row_idx}: level {level} out of range 1~{RACK_LEVELS}", 400,
            )
        face = Face(face_str)
        valid_faces = valid_face_by_rack[rack_id].get(block, set())
        if not valid_faces:
            raise AppError(f"row {row_idx}: rack '{rack_id}' block {block} not found", 400)
        if face not in valid_faces:
            raise AppError(f"row {row_idx}: rack '{rack_id}' block {block} face {face_str} is not exposed", 400)
        if (block, face) in locked_by_rack[rack_id]:
            raise AppError(f"row {row_idx}: rack '{rack_id}' block {block} face {face_str} is locked", 400)

        sku = str(spec.get("sku", "")).strip()
        name = str(spec.get("name", "")).strip()
        price_raw = spec.get("price", 0)
        try:
            price = int(price_raw) if price_raw not in (None, "") else 0
        except (ValueError, TypeError):
            raise AppError(f"row {row_idx}: price is not a number", 400)
        promo = str(spec.get("promo", "") or "").strip()

        coord = (rack_id, block, face, level)
        existing = slot_by_coord.get(coord)
        if existing is None:
            existing = _SlotAccum(
                rack_id=rack_id, block=block, face=face, level=level,
            )
            slot_by_coord[coord] = existing

        # Empty sku ("") creates no SlotItem; coords with zero non-empty
        # items skip Slot creation entirely (sparse representation).
        if sku:
            if len(existing.items) >= 4:
                raise AppError(f"row {row_idx}: rack '{rack_id}' block {block} face {face_str} level {level} holds at most 4 products", 400)
            existing.items.append(SlotItem(
                sku=sku, name=name, price=price, promo=promo,
            ))

    new_slots_by_rack: dict[str, list[Slot]] = {r.id: [] for r in store.racks}
    for accum in slot_by_coord.values():
        if not accum.items:
            continue
        new_slots_by_rack[accum.rack_id].append(Slot(
            block=accum.block, face=accum.face, level=accum.level,
            items=accum.items,
        ))

    for r in store.racks:
        r.slots = new_slots_by_rack.get(r.id, [])
    cleared = clear_blocked_slots(store)  # unreachable slots are auto-removed
    setup["store"] = store.model_dump(mode="json")
    write_setup(project_id, setup_id, setup)
    total = sum(len(slot.items) for r in store.racks for slot in r.slots)
    return ReplaceSlotsResult(count=total, cleared=cleared)


def create_setup_from_source(
    project_id: str,
    source_setup_id: str | None,
    mode: str,
    name: str | None = None,
    memo: str = "",
) -> dict[str, Any]:
    """Copy source setup's store into a new draft.

    mode:
    - "racks_and_items": deep copy including slots
    - "racks": deep copy then clear all racks[].slots = []
    - "empty": create setup with store=None. source_setup_id optional —
      when provided, used as parentId (inherits block meta); otherwise parentId=None.
    """
    if not metadata_path(project_id).is_file():
        raise AppError(f"project not found: {project_id}", 404)
    if mode not in ("racks_and_items", "racks", "empty"):
        raise AppError(f"unknown mode: {mode}", 400)

    if mode == "empty":
        # If source is provided, it's used only as parentId (store stays empty).
        parent_id: str | None = None
        src_name: str | None = None
        if source_setup_id:
            try:
                source = read_setup(project_id, source_setup_id)
            except FileNotFoundError:
                raise AppError(f"source setup not found: {source_setup_id}", 404)
            parent_id = source_setup_id
            src_name = source.get("name")
        if name:
            final_name = name
        elif src_name:
            final_name = f"{src_name} (copy)"
        else:
            final_name = "Untitled layout"
        new_setup = new_setup_data(final_name, parent_id, None, memo)
        write_json(setup_path(project_id, new_setup["id"]), new_setup)
        set_active_setup(project_id, new_setup["id"])
        return setup_summary(project_id, new_setup)

    if not source_setup_id:
        raise AppError("source_setup_id is required.", 400)
    try:
        source = read_setup(project_id, source_setup_id)
    except FileNotFoundError:
        raise AppError(f"source setup not found: {source_setup_id}", 404)

    src_name = source.get("name") or "layout"
    final_name = name or f"{src_name} (copy)"
    store_copy: dict[str, Any] | None = cast(
        Any, copy.deepcopy(source.get("store")),
    )
    if mode == "racks" and isinstance(store_copy, dict):
        racks_field = cast(list[Any], store_copy.get("racks") or [])
        for rack_any in racks_field:
            if isinstance(rack_any, dict):
                cast(dict[str, Any], rack_any)["slots"] = []

    new_setup = new_setup_data(final_name, source_setup_id, store_copy, memo)
    for key in ("building", "generation", "operations"):   # a copy is run like its source until changed
        if source.get(key) is not None:
            new_setup[key] = copy.deepcopy(source[key])
    write_json(setup_path(project_id, new_setup["id"]), new_setup)
    set_active_setup(project_id, new_setup["id"])
    return setup_summary(project_id, new_setup)


def delete_setup_with_descendants(project_id: str, setup_id: str) -> list[str]:
    """Delete setup + descendant branches. Enforces business rules. Returns deleted IDs."""
    try:
        setup = read_setup(project_id, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404)

    if not setup.get("parentId"):
        raise AppError("the initial setup cannot be deleted.", 409)
    if setup["status"] == "running":
        raise AppError("cannot delete a setup that is currently running.", 409)

    deleted_ids = [*find_descendants(project_id, setup_id), setup_id]
    deadline = time.monotonic() + 10
    try:
        with ExitStack() as locks:
            # Acquire the entire tree before changing any files. Stable ordering
            # also prevents overlapping ancestor/descendant deletions deadlocking.
            for del_id in sorted(deleted_ids):
                locks.enter_context(FileLock(
                    str(setup_lock_path(project_id, del_id)),
                    timeout=max(0, deadline - time.monotonic()),
                ))
            for del_id in deleted_ids:
                try:
                    current = read_setup(project_id, del_id)
                except FileNotFoundError:
                    if del_id == setup_id:
                        raise AppError(f"setup not found: {setup_id}", 404)
                    continue
                # A simulation may have started while deletion waited for a save.
                if current["status"] == "running":
                    raise AppError(
                        f"setup '{current.get('name', del_id)}' is currently running and cannot be deleted.", 409,
                    )
            for del_id in deleted_ids:
                delete_setup(project_id, del_id)

            # If the active setup was deleted, switch to the first remaining one.
            state = read_state(project_id)
            if state.get("activeSetupId") in deleted_ids:
                remaining = list_setups(project_id)
                state["activeSetupId"] = remaining[0]["id"] if remaining else None
                write_state(project_id, state)
            return deleted_ids
    except Timeout:
        raise AppError(503, "setup_lock_timeout", "lock_timeout",
                       "another request is modifying this setup. Please retry shortly.", {"timeout_seconds": 10})


def layout_operations(project_id: str, setup_id: str) -> OperationsConfig | None:
    """How this layout's store is run (stock, refills, tills, crowding), when it has been saved; None otherwise.
    Runs, A/B tests and the optimizer on the layout use it unless told otherwise."""
    try:
        data = read_setup(project_id, setup_id)
    except FileNotFoundError:
        raise AppError(404, "setup_not_found", "not_found", f"Setup not found: {setup_id}", {})
    saved = data.get("operations")
    if not isinstance(saved, dict):
        return None
    try:
        return OperationsConfig.model_validate(saved)
    except ValidationError as e:   # damaged on disk: the layout runs as if none were saved, and says why in the log
        logger.warning(f"[setups] {project_id}/{setup_id}: unreadable operations settings ignored: {e}")
        return None


def save_layout_operations(project_id: str, setup_id: str, config: OperationsConfig | None) -> OperationsConfig | None:
    """Save (or with None, clear) how the layout's store is run. Allowed on a finalized layout too: it changes how
    the store is run, not the layout its runs recorded."""
    try:
        with FileLock(str(setup_lock_path(project_id, setup_id)), timeout=10):
            try:
                data = read_setup(project_id, setup_id)
            except FileNotFoundError:
                raise AppError(404, "setup_not_found", "not_found", f"Setup not found: {setup_id}", {})
            if config is None:
                data.pop("operations", None)
            else:
                data["operations"] = config.model_dump(mode="json")
            write_setup(project_id, setup_id, data)
            return config
    except Timeout:
        raise AppError(503, "setup_lock_timeout", "lock_timeout",
                       "another request is modifying this setup. Please retry shortly.", {"timeout_seconds": 10})


def run_operations(
    project_id: str, setup_id: str, operations: OperationsConfig | None, shared_store: bool | None,
) -> OperationsConfig | None:
    """The operations a run, test or search on the layout uses: none when asked for none, the request's own when it
    brings them, else the layout's saved ones (or none)."""
    if shared_store is False:
        return None
    if operations is not None:
        return operations
    saved = layout_operations(project_id, setup_id)
    return saved if saved is not None or not shared_store else OperationsConfig()
