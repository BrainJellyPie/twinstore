"""Combine existing captures, preserving source layouts and replaying uncertain saves."""

import hashlib
import json
from pathlib import Path
from filelock import FileLock, Timeout

from store_emulator.application import capture
from store_emulator.application.errors import AppError
from store_emulator.application.currencies import project_currency
from store_emulator.application.setups import setup_lock_path, setup_tree_transaction
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import (
    metadata_path,
    deleted_setup_path,
    new_setup_data,
    read_setup,
    setup_path,
)
from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.capture_batch import (
    CaptureBatchPreview,
    CaptureBatchRecord,
    CaptureBatchRequest,
    CaptureBatchSave,
    CaptureBatchSaved,
)
from store_emulator.domain.store import Store
from store_emulator.engine.capture.planogram import add_capture_racks, match_store_skus
from store_emulator.engine.capture.planogram import PlacementReport
from store_emulator.engine.validation import validate


def _project(pid: str) -> None:
    if len(pid) > 128:
        raise AppError("Invalid project id", 422)
    capture._check_id(pid, "project id")  # pyright: ignore[reportPrivateUsage]
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)


def _prepare(
    pid: str, req: CaptureBatchRequest, default_currency: str
) -> tuple[CaptureBatchPreview, list[CaptureResult]]:
    _project(pid)
    try:
        source = read_setup(pid, req.setup_id)
    except FileNotFoundError as exc:
        raise AppError("Base layout no longer exists", 404) from exc
    if not source.get("store"):
        raise AppError("Choose a layout with a store before combining shelves", 409)
    try:
        store = Store.model_validate(source["store"])
    except ValueError as exc:
        raise AppError(
            "The base layout is invalid; correct it before combining shelves", 409
        ) from exc
    store = store.model_copy(
        update={"currency": store.currency or project_currency(pid, default_currency)}
    )
    results: list[CaptureResult] = []
    for cid in req.capture_ids:
        try:
            view = capture.get_capture(pid, cid)
        except ValueError as exc:
            raise AppError(
                "A selected photo has invalid saved recognition data; review it again",
                409,
            ) from exc
        if (
            view.status.status != "completed"
            or view.result is None
            or not view.result.items
        ):
            raise AppError(
                "Every selected photo must have completed recognition and at least one product",
                409,
            )
        if view.result.currency != store.currency:
            raise AppError("All selected photos must use the base layout currency", 422)
        if any(i.price is not None and i.price < 0 for i in view.result.items):
            raise AppError(
                "A selected photo has a negative price; correct it before combining shelves",
                409,
            )
        results.append(view.result)
    if sum(r.facings for r in results) > 2000 or any(
        i.facings > 24 for r in results for i in r.items
    ):
        raise AppError(
            "Combine at most 2,000 facings, with at most 24 per product", 422
        )
    payload = {
        "setup_id": req.setup_id,
        "store": store.model_dump(mode="json"),
        "captures": [
            (cid, r.model_dump(mode="json"))
            for cid, r in zip(req.capture_ids, results, strict=True)
        ],
    }
    try:
        serialized = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except ValueError as exc:
        raise AppError(
            "A selected photo or layout has non-finite values; correct it before combining shelves",
            409,
        ) from exc
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    try:
        combined, report = add_capture_racks(store, results, exact_sku_match=True)
    except ValueError as exc:
        raise AppError(f"These shelves do not fit: {exc}", 409) from exc
    issues = [i.message for i in validate(combined) if i.severity == "error"]
    if issues:
        raise AppError(f"Combined layout is invalid: {issues[0]}", 409)
    # Crop images must use the same SKU identities that the placement engine matched.
    matched = [
        match_store_skus(combined, r, PlacementReport(), exact=True) for r in results
    ]
    preview = CaptureBatchPreview(
        source_sha256=digest,
        store=combined,
        rack_ids=report.rack_ids,
        placed_items=report.placed_items,
        placed_facings=report.placed_facings,
        requested_facings=sum(r.facings for r in results),
        reduced_facings=max(0, sum(r.facings for r in results) - report.placed_facings),
        dropped=report.dropped,
        notes=report.notes,
        estimated_prices=sum(
            i.price_estimated or i.price is None for r in results for i in r.items
        ),
        unrecognized_items=sum(not i.labeled for r in results for i in r.items),
    )
    return preview, matched


def preview(
    pid: str, req: CaptureBatchRequest, *, default_currency: str = "USD"
) -> CaptureBatchPreview:
    return _prepare(pid, req, default_currency)[0]


def _existing(path: Path, req: CaptureBatchSave) -> CaptureBatchSaved | None:
    if not path.exists():
        return None
    data = CaptureBatchRecord.model_validate_json(path.read_bytes())
    if data.capture_batch_request != req:
        raise AppError(
            "This save request already belongs to a different selection; preview again",
            409,
        )
    return data.capture_batch_result


def save(
    pid: str, req: CaptureBatchSave, *, default_currency: str = "USD"
) -> CaptureBatchSaved:
    _project(pid)
    path = setup_path(pid, f"setup_batch_{req.request_id}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (setup_tree_transaction(pid), FileLock(path.parent / ".capture-batch.lock", timeout=0),
              FileLock(setup_lock_path(pid, path.stem), timeout=10)):
            if deleted_setup_path(pid, path.stem).exists():
                raise AppError("This combined layout was deleted. Start a new preview to save another layout", 409)
            previous = _existing(path, req)
            if previous is not None:
                return previous
            checked, results = _prepare(pid, req, default_currency)
            if checked.source_sha256 != req.source_sha256:
                raise AppError(
                    "A selected photo or the base layout changed; preview again", 409
                )
            if checked.dropped:
                raise AppError(
                    "Some products do not fit. Correct the photos or choose a roomier layout, then preview again",
                    409,
                )
            if checked.reduced_facings and not req.allow_reduced_facings:
                raise AppError(
                    "Facing counts were reduced to fit the grid. Review and accept the reduced counts before saving",
                    409,
                )
            for cid, result in zip(req.capture_ids, results, strict=True):
                capture._save_sku_images(pid, cid, result)  # pyright: ignore[reportPrivateUsage]
            saved = CaptureBatchSaved(
                setup_id=path.stem,
                rack_ids=checked.rack_ids,
                placed_items=checked.placed_items,
                placed_facings=checked.placed_facings,
                notes=checked.notes,
            )
            draft = new_setup_data(
                f"Combined shelves ({len(results)} photos)",
                req.setup_id,
                checked.store.model_dump(mode="json"),
                "Combined reviewed shelf photos; source layouts unchanged.",
            )
            source = read_setup(pid, req.setup_id)
            if source.get("building") is not None:
                draft["building"] = BuildingFloorInfo.model_validate(source["building"]).model_dump(mode="json")
            if source.get("operations") is not None:
                draft["operations"] = source["operations"]
            draft["id"] = path.stem
            draft["capture_batch_request"] = req.model_dump(mode="json")
            draft["capture_batch_result"] = saved.model_dump(mode="json")
            write_json(path, draft)
            return saved
    except Timeout as exc:
        raise AppError(
            "Another shelf combination is saving. Retry this save shortly", 409
        ) from exc
    except (OSError, ValueError) as exc:
        raise AppError(
            "Could not complete the combined draft. Retry the same save to recover safely",
            500,
        ) from exc
