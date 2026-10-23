"""Snapshot-checked rack reuse stored as an idempotent child layout."""
from filelock import FileLock, Timeout
from store_emulator.application.errors import AppError
from store_emulator.application.product_sources import check_product_layout, read_product_source
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.images import layout_image_url, load_manifest
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.product_edits import ProductEditsReceipt
from store_emulator.domain.rack_copy import RackCopyOptions, RackCopyPreview, RackCopyRecord, RackCopyRequest, RackCopySave, RackCopySaved
from store_emulator.domain.store import Store
from store_emulator.engine.rack_copy import choices, copy_products


def options(pid: str, sid: str, source_id: str | None) -> RackCopyOptions:
    store, digest = read_product_source(pid, sid)
    try:
        sources, targets = choices(store, source_id)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc
    return RackCopyOptions(source_sha256=digest, currency=store.currency or "USD", source_rack_id=source_id,
                           sources=sources, targets=targets)


def _prepare(pid: str, sid: str, req: RackCopyRequest) -> tuple[Store, RackCopyPreview]:
    store, digest = read_product_source(pid, sid)
    if req.source_sha256 != digest or req.currency != store.currency:
        raise AppError("The layout or currency changed. Reload shelves and preview again", 409)
    try:
        return copy_products(store, req.source_rack_id, req.target_rack_ids)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc


def preview(pid: str, sid: str, req: RackCopyRequest) -> RackCopyPreview:
    report = _prepare(pid, sid, req)[1].model_copy(deep=True)
    # Uploaded images are linked by SKU at read time, not persisted in slots.
    manifest = load_manifest(pid)
    for slot in report.slots:
        for item in slot.items:
            item.image_url = layout_image_url(pid, item.sku, item.image_url, manifest)
    return report


def save(pid: str, sid: str, req: RackCopySave) -> RackCopySaved:
    check_product_layout(pid, sid)
    path = setup_path(pid, f"setup_rackcopy_{req.request_id}")
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = path.parent / ".rack-copy" / f"{req.request_id}.json"
    try:
        with FileLock(path.parent / ".rack-copy.lock", timeout=0):
            if receipt.exists() and ProductEditsReceipt.model_validate_json(receipt.read_bytes()).source_id != sid:
                raise AppError("This request belongs to another source layout", 409)
            if path.exists():
                record = RackCopyRecord.model_validate_json(path.read_bytes())
                if record.rack_copy_request != req:
                    raise AppError("This request already saved different choices. Start a new preview", 409)
                return record.rack_copy_result
            if receipt.exists():
                raise AppError("This draft was removed or its write was interrupted. Check Layouts, then start a new preview", 409)
            store, report = _prepare(pid, sid, req)
            result = RackCopySaved(setup_id=path.stem, placements_added=report.placements_added)
            draft = new_setup_data("Reused shelf products", sid, store.model_dump(mode="json"),
                                   f"Copied existing products from {report.source_name} to {len(report.targets)} empty racks. Original preserved; no stock quantities inferred.")
            source = read_setup(pid, sid)
            if source.get("operations") is not None:
                draft["operations"] = source["operations"]
            building = source.get("building")
            if building is not None:
                draft["building"] = BuildingFloorInfo.model_validate(building).model_dump(mode="json")
            draft["id"] = path.stem
            draft["rack_copy_request"] = req.model_dump(mode="json")
            draft["rack_copy_result"] = result.model_dump(mode="json")
            write_json(receipt, {"source_id": sid})
            write_json(path, draft)
            return result
    except Timeout as exc:
        raise AppError("Another shelf copy is saving. Retry this save shortly", 409) from exc
    except (OSError, ValueError) as exc:
        raise AppError("Could not save the shelf copy. Retry the same request to check whether it completed", 500) from exc
