"""Snapshot library images into a separate, retry-safe layout without model calls."""
import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4
from filelock import FileLock, Timeout
from PIL import Image, UnidentifiedImageError
from store_emulator.application.errors import AppError
from store_emulator.application.setups import setup_lock_path, setup_tree_transaction
from store_emulator.application.product_sources import check_product_layout, read_product_source
from store_emulator.application.shelf_lab import PackageAsset, package_asset, package_directory, package_edit
from store_emulator.application.storage.io import DATA_DIR, write_json
from store_emulator.application.storage.images import layout_image_url, load_manifest
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.library_photos import PhotoAsset, PhotoOptions, PhotoPreview, PhotoRecord, PhotoRequest, PhotoSave, PhotoSaved
from store_emulator.domain.product_edits import ProductEditsReceipt
from store_emulator.domain.store import Store
from store_emulator.engine.library_photos import assign, products

MAX_ASSETS = 500
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_BATCH_BYTES = 64 * 1024 * 1024


def _source(pid: str, sid: str) -> tuple[Store, str]:
    store, digest = read_product_source(pid, sid)
    manifest = load_manifest(pid, strict=True)
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                item.image_url = layout_image_url(pid, item.sku, item.image_url, manifest)
    payload = digest + json.dumps(manifest, sort_keys=True)
    return store, hashlib.sha256(payload.encode()).hexdigest()


def _photo(pid: str, aid: str) -> tuple[PackageAsset, bytes, str]:
    with package_edit(pid, aid) as path:
        if path.stat().st_size > MAX_PHOTO_BYTES:
            raise AppError("A library photo exceeds 8 MB; use a smaller image", 413)
        data = path.read_bytes()
        try:
            with Image.open(io.BytesIO(data)) as im:
                if im.format != "PNG":
                    raise ValueError("Expected a library PNG")
                im.verify()
            asset = package_asset(path)
        except (ValueError, OSError, AttributeError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise AppError("A library photo is unreadable; replace it in Products", 409) from exc
        version = hashlib.sha256(data + asset.model_dump_json().encode()).hexdigest()
        return asset, data, version


def options(pid: str, sid: str) -> PhotoOptions:
    store, digest = _source(pid, sid)
    paths = sorted(package_directory(pid).glob("pkg_*.png"))
    if len(paths) > MAX_ASSETS:
        raise AppError("Use a library of at most 500 photos for this workflow", 413)
    assets: list[PhotoAsset] = []
    for path in paths:
        asset, _, version = _photo(pid, path.stem)
        assets.append(PhotoAsset(asset_id=asset.asset_id, name=asset.name, sku=asset.sku, version=version,
                                 image_url=f"/api/projects/{pid}/lab/packages/{asset.asset_id}"))
    return PhotoOptions(source_sha256=digest, products=products(store), assets=assets)


def photo_file(pid: str, digest: str) -> Path:
    check_product_layout(pid, "photo")
    path = Path(DATA_DIR) / pid / "product_photos" / f"{digest}.png"
    if not path.is_file():
        raise AppError("Saved product photo not found", 404)
    return path


def _snapshot(pid: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    path = Path(DATA_DIR) / pid / "product_photos" / f"{digest}.png"
    with setup_tree_transaction(pid):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.stat().st_size != len(data) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            tmp = path.with_suffix(f".tmp-{uuid4().hex}")
            try:
                tmp.write_bytes(data)
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
    return f"/api/projects/{pid}/product-photo-files/{digest}"


def _prepare(pid: str, sid: str, req: PhotoRequest) -> tuple[Store, PhotoPreview]:
    store, digest = _source(pid, sid)
    if req.source_sha256 != digest:
        raise AppError("The layout or its images changed. Reload and preview again", 409)
    loaded: dict[str, tuple[str, bytes]] = {}
    total = 0
    for choice in req.assignments:
        asset, data, version = _photo(pid, choice.asset_id)
        if version != choice.version:
            raise AppError("A library photo or its link changed. Reload and preview again", 409)
        total += len(data)
        if total > MAX_BATCH_BYTES:
            raise AppError("Selected photos exceed 64 MB; choose a smaller batch", 413)
        loaded[choice.sku] = (asset.name, data)
    # Validate the entire batch before writing any snapshot files.
    try:
        assign(store, {sku: (name, "pending") for sku, (name, _) in loaded.items()}, req.replace_existing)
        return assign(store, {sku: (name, _snapshot(pid, data)) for sku, (name, data) in loaded.items()}, req.replace_existing)
    except ValueError as exc:
        raise AppError(str(exc), 422) from exc


def preview(pid: str, sid: str, req: PhotoRequest) -> PhotoPreview:
    return _prepare(pid, sid, req)[1]


def save(pid: str, sid: str, req: PhotoSave) -> PhotoSaved:
    check_product_layout(pid, sid)
    path = setup_path(pid, f"setup_photos_{req.request_id}")
    receipt = path.parent / ".library-photos" / f"{req.request_id}.json"
    try:
        with FileLock(setup_lock_path(pid, sid).with_name(".library-photos.lock"), timeout=0):
            if receipt.exists() and ProductEditsReceipt.model_validate_json(receipt.read_bytes()).source_id != sid:
                raise AppError("This request belongs to another source layout", 409)
            if path.exists():
                record = PhotoRecord.model_validate_json(path.read_bytes())
                if record.library_photos_request != req:
                    raise AppError("This request already saved different choices. Start a new preview", 409)
                return record.library_photos_result
            if receipt.exists():
                raise AppError("This draft was removed or its write was interrupted. Check Layouts, then start a new preview", 409)
            store, report = _prepare(pid, sid, req)
            result = PhotoSaved(setup_id=path.stem, changed_placements=report.changed_placements)
            draft = new_setup_data("Library product photos", sid, store.model_dump(mode="json"),
                                   "Reviewed existing photos applied to products. Original preserved; no model calls or stock/price inference.")
            source = read_setup(pid, sid)
            if source.get("operations") is not None:
                draft["operations"] = source["operations"]
            building = source.get("building")
            if building is not None:
                draft["building"] = BuildingFloorInfo.model_validate(building).model_dump(mode="json")
            draft.update(id=path.stem, library_photos_request=req.model_dump(mode="json"), library_photos_result=result.model_dump(mode="json"))
            with setup_tree_transaction(pid, [sid]):
                write_json(receipt, {"source_id": sid})
                write_json(path, draft)
            return result
    except Timeout as exc:
        raise AppError("Another photo layout is saving. Retry shortly", 409) from exc
    except (OSError, ValueError) as exc:
        raise AppError("Could not save photos. Retry the same request to check whether it completed", 500) from exc
