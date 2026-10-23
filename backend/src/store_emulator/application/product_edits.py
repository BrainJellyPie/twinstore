"""Read a snapshot and save edited products as a separate, replay-safe child layout."""
from pathlib import Path
from filelock import FileLock, Timeout

from store_emulator.application.errors import AppError
from store_emulator.application.product_sources import check_product_layout, read_product_source
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.product_edits import (
    ProductCatalog, ProductEditsPreview, ProductEditsRecord,
    ProductEditsRequest, ProductEditsSave, ProductEditsSaved, ProductEditsReceipt,
)
from store_emulator.domain.store import Store
from store_emulator.engine.product_edits import apply_product_edits, product_rows



def catalog(pid: str, sid: str) -> ProductCatalog:
    store, digest = read_product_source(pid, sid)
    return ProductCatalog(source_sha256=digest, currency=store.currency or "USD", products=product_rows(store))


def _prepare(pid: str, sid: str, req: ProductEditsRequest) -> tuple[Store, ProductEditsPreview]:
    store, digest = read_product_source(pid, sid)
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
    check_product_layout(pid, sid)
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
            source = read_setup(pid, sid)
            if source.get("operations") is not None:
                draft["operations"] = source["operations"]
            building = source.get("building")
            if building is not None:  # the draft stays on the same building floor
                draft["building"] = BuildingFloorInfo.model_validate(building).model_dump(mode="json")
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
