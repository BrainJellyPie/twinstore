"""Read a snapshot and save edited products as a separate, replay-safe child layout."""
import hashlib
import json
import re
from pathlib import Path
from filelock import FileLock, Timeout

from store_emulator.application.currencies import project_currency
from store_emulator.application.errors import AppError
from store_emulator.application.storage.generations import find_active_generation
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, new_setup_data, read_setup, setup_path
from store_emulator.domain.product_edits import (
    MAX_PRICE, ProductCatalog, ProductEditsPreview, ProductEditsRecord,
    ProductEditsRequest, ProductEditsSave, ProductEditsSaved, ProductEditsReceipt,
)
from store_emulator.domain.store import Store
from store_emulator.engine.product_edits import apply_product_edits, product_rows


def _project(pid: str, sid: str) -> None:
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) for value in (pid, sid)):
        raise AppError("Invalid project or layout identifier", 422)
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)


def _source(pid: str, sid: str) -> tuple[Store, str]:
    _project(pid, sid)
    try:
        source = read_setup(pid, sid)
    except FileNotFoundError as exc:
        raise AppError("Source layout no longer exists", 404) from exc
    except (ValueError, AttributeError) as exc:
        raise AppError("Stored layout data is unreadable. Restore a valid copy before editing", 409) from exc
    if find_active_generation(pid, sid, "layout"):
        raise AppError("Layout generation is in progress; reload when it finishes", 409)
    if not source.get("store"):
        raise AppError("Create and stock a layout before editing products", 409)
    try:
        store = Store.model_validate(source["store"])
        store.currency = store.currency or project_currency(pid, "USD")
        payload = json.dumps(store.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, allow_nan=False)
    except ValueError as exc:
        raise AppError("The stored layout is invalid; repair it before editing products", 409) from exc
    items = [item for rack in store.racks for slot in rack.slots for item in slot.items]
    if len(items) > 50_000 or len({item.sku for item in items}) > 5_000:
        raise AppError("Edit layouts with at most 5,000 SKUs and 50,000 placements", 413)
    if any(item.price > MAX_PRICE for item in items):
        raise AppError("A stored price exceeds the safe integer limit; correct it first", 409)
    return store, hashlib.sha256(payload.encode()).hexdigest()


def catalog(pid: str, sid: str) -> ProductCatalog:
    store, digest = _source(pid, sid)
    return ProductCatalog(source_sha256=digest, currency=store.currency or "USD", products=product_rows(store))


def _prepare(pid: str, sid: str, req: ProductEditsRequest) -> tuple[Store, ProductEditsPreview]:
    store, digest = _source(pid, sid)
    if req.source_sha256 != digest or req.currency != store.currency:
        raise AppError("The source layout or currency changed. Reload products and review your edits again", 409)
    try:
        return apply_product_edits(store, req.edits)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc


def preview(pid: str, sid: str, req: ProductEditsRequest) -> ProductEditsPreview:
    return _prepare(pid, sid, req)[1]


def _existing(path: Path, req: ProductEditsSave) -> ProductEditsSaved | None:
    if not path.exists():
        return None
    record = ProductEditsRecord.model_validate_json(path.read_bytes())
    if record.product_edits_request != req:
        raise AppError("This request already saved different edits. Start a new preview", 409)
    return record.product_edits_result


def save(pid: str, sid: str, req: ProductEditsSave) -> ProductEditsSaved:
    _project(pid, sid)
    path = setup_path(pid, f"setup_products_{req.request_id}")
    path.parent.mkdir(parents=True, exist_ok=True)
    # The source ID is also part of replay identity, including when the source was later removed.
    receipt = path.parent / ".product-edits" / f"{req.request_id}.json"
    try:
        with FileLock(path.parent / ".product-edits.lock", timeout=0):
            if receipt.exists():
                accepted_source = ProductEditsReceipt.model_validate_json(receipt.read_bytes()).source_id
                if accepted_source != sid:
                    raise AppError("This request belongs to another source layout", 409)
            previous = _existing(path, req)
            if previous is not None:
                return previous
            if receipt.exists():
                raise AppError("This draft was removed or its write was interrupted. Check Layouts, then start a new preview", 409)
            store, report = _prepare(pid, sid, req)
            if not report.changes:
                raise AppError("No product values changed; there is no draft to save", 422)
            result = ProductEditsSaved(setup_id=path.stem, changed_placements=report.changed_placements)
            draft = new_setup_data(
                "Edited products", sid, store.model_dump(mode="json"),
                f"Explicit edits to {len(report.changes)} SKUs / {report.changed_placements} placements. Source layout preserved.",
            )
            draft["id"] = path.stem
            draft["product_edits_request"] = req.model_dump(mode="json")
            draft["product_edits_result"] = result.model_dump(mode="json")
            write_json(receipt, {"source_id": sid})
            write_json(path, draft)
            return result
    except Timeout as exc:
        raise AppError("Another product draft is saving. Retry this save shortly", 409) from exc
    except (OSError, ValueError) as exc:
        raise AppError("Could not save the product draft. Retry the same request to check whether it completed", 500) from exc
