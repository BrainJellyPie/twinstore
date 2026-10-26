"""Preview and save starter products on empty existing racks as a separate child layout."""
import asyncio
import hashlib
import json
from filelock import FileLock, Timeout
from store_emulator.application.errors import AppError
from store_emulator.application.setups import setup_lock_path, setup_tree_transaction
from store_emulator.application.product_sources import check_product_layout, read_product_source
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.images import layout_image_url, load_manifest
from store_emulator.application.storage.setups import new_setup_data, setup_path, read_setup, unique_setup_name
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.product_edits import ProductEditsReceipt
from store_emulator.domain.starter_fill import (
    StarterAutoRequest, StarterCatalog, StarterCategory, StarterFillRequest, StarterFillSave, StarterPreview, StarterRecord, StarterSaved,
)
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item, category_label
from store_emulator.engine.starter_fill import fill_empty_racks, rack_choices
from store_emulator.engine.starter_selection import select_starter_products
from store_emulator.application.providers import assistive_client
from store_emulator.application.errors import model_failure


def auto_select(pid: str, sid: str, req: StarterAutoRequest, config: SimulationConfig) -> StarterFillRequest:
    check_product_layout(pid, sid)
    store, digest = _source(pid, sid)
    if req.source_sha256 != digest or req.currency != store.currency:
        raise AppError("The layout, currency or starter catalog changed. Reload and try again", 409)
    try:
        racks = rack_choices(store)
        eligible = [rack for rack in racks if not rack.reason and rack.available_slots > 0]
        if not eligible or len(eligible) > 100:
            raise ValueError("Automatic placement needs 1–100 empty accessible shelves. Use manual selection for larger layouts.")
        llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 5000})
        llm = assistive_client(req.model, llm_config)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc
    try:
        assignments = asyncio.run(select_starter_products(llm, store, racks, req.requirements, products_per_slot=req.products_per_slot))
    except Exception as exc:
        raise AppError(model_failure(exc, "Starter products could not be selected"), 502) from exc
    check_product_layout(pid, sid)
    if _source(pid, sid)[1] != digest:
        raise AppError("The layout or starter catalog changed while selecting products. Reload and try again", 409)
    result = StarterFillRequest(source_sha256=digest, currency=req.currency, products_per_slot=req.products_per_slot, assignments=assignments)
    _prepare(pid, sid, result)
    return result


def _source(pid: str, sid: str) -> tuple[Store, str]:
    store, digest = read_product_source(pid, sid)
    if store.currency not in {"USD", "KRW", "JPY"}:
        raise AppError("Starter reference prices support USD, KRW and JPY layouts only; no live FX conversion is provided", 409)
    # A changed bundled catalog must invalidate an old preview just like a changed layout.
    catalog_data = {key: [(p.en, p.ko, p.usd_cents, catalog_slot_item(p, "USD").image_url) for p in values] for key, values in CATALOG.items()}
    digest = hashlib.sha256((digest + json.dumps(catalog_data, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    return store, digest


def catalog(pid: str, sid: str) -> StarterCatalog:
    store, digest = _source(pid, sid)
    try:
        racks = rack_choices(store)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc
    return StarterCatalog(source_sha256=digest, currency=store.currency or "USD", racks=racks,
                          categories=[StarterCategory(key=key, label=category_label(key, "USD"),
                                                      products=[catalog_slot_item(item, store.currency or "USD") for item in values])
                                      for key, values in sorted(CATALOG.items()) if values])


def _prepare(pid: str, sid: str, req: StarterFillRequest) -> tuple[Store, StarterPreview]:
    store, digest = _source(pid, sid)
    if req.source_sha256 != digest or req.currency != store.currency:
        raise AppError("The layout, currency or starter catalog changed. Reload and preview again", 409)
    try:
        return fill_empty_racks(store, req.assignments, req.products_per_slot)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc


def preview(pid: str, sid: str, req: StarterFillRequest) -> StarterPreview:
    report = _prepare(pid, sid, req)[1].model_copy(deep=True)
    manifest = load_manifest(pid)
    for rack in report.racks:
        for item in rack.products:
            item.image_url = layout_image_url(pid, item.sku, item.image_url, manifest)
    return report


def save(pid: str, sid: str, req: StarterFillSave) -> StarterSaved:
    check_product_layout(pid, sid)
    path = setup_path(pid, f"setup_starter_{req.request_id}")
    receipt = path.parent / ".starter-fill" / f"{req.request_id}.json"
    try:
        with FileLock(setup_lock_path(pid, sid).with_name(".starter-fill.lock"), timeout=0):
            if receipt.exists() and ProductEditsReceipt.model_validate_json(receipt.read_bytes()).source_id != sid:
                raise AppError("This request belongs to another source layout", 409)
            if path.exists():
                record = StarterRecord.model_validate_json(path.read_bytes())
                if record.starter_fill_request != req:
                    raise AppError("This request already saved different choices. Start a new preview", 409)
                return record.starter_fill_result
            if receipt.exists():
                raise AppError("This draft was removed or its write was interrupted. Check Layouts, then start a new preview", 409)
            store, report = _prepare(pid, sid, req)
            result = StarterSaved(setup_id=path.stem, placements_added=report.placements_added)
            draft = new_setup_data(unique_setup_name(pid, "Starter products"), sid, store.model_dump(mode="json"),
                                   f"Starter reference assortment: {len(report.racks)} racks, {report.placements_added} placements. Not actual inventory or prices. Original preserved.")
            draft["id"] = path.stem
            draft["starter_fill_request"] = req.model_dump(mode="json")
            draft["starter_fill_result"] = result.model_dump(mode="json")
            with setup_tree_transaction(pid, [sid]), FileLock(setup_lock_path(pid, sid), timeout=10):
                current, digest = _source(pid, sid)
                if req.source_sha256 != digest or req.currency != current.currency:
                    raise AppError("The layout, currency or starter catalog changed. Reload and preview again", 409)
                source = read_setup(pid, sid)
                if source.get("operations") is not None:
                    draft["operations"] = source["operations"]
                building = source.get("building")
                if building is not None:
                    draft["building"] = BuildingFloorInfo.model_validate(building).model_dump(mode="json")
                write_json(receipt, {"source_id": sid})
                write_json(path, draft)
            return result
    except Timeout as exc:
        raise AppError("Another starter draft is saving. Retry this save shortly", 409) from exc
    except (OSError, ValueError) as exc:
        raise AppError("Could not save the starter draft. Retry the same request to check whether it completed", 500) from exc
