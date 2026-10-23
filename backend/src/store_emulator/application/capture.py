"""Shelf capture use cases: upload a shelf photo, recognise it in the background, correct it, apply it.

Files per capture (`.data/<pid>/captures/<cid>/`):
- image.jpg        the photo, EXIF orientation applied and metadata (GPS, camera) dropped
- overlay.png      bands, facings, labels and gaps drawn on the photo
- status.json      CaptureStatus (polled by the UI)
- result.json      CaptureResult (the planogram, including user corrections)
- result.auto.json the automatic result before any correction (kept for accuracy tracking)
"""

import asyncio
import hashlib
import io
import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Annotated, cast

from filelock import FileLock, Timeout
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, StringConstraints

from store_emulator.domain.capture import (
    CaptureItem,
    CaptureOptions,
    CaptureResult,
    CaptureStatus,
)
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.providers import ModelRef
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face, RESOURCE_ID_PATTERN
from store_emulator.engine.capture import (
    ClassicDetector,
    FacingDetector,
    GroundingDinoDetector,
    PlacementReport,
    VLMGroundingDetector,
    VLMLabeler,
    add_capture_racks,
    capture_shelf,
    gdino_available,
    render_overlay,
    replace_rack_face,
    sku_for,
)
from store_emulator.engine.capture.catalog_match import match_category, typical_price
from store_emulator.engine.capture.frame import load_photo
from store_emulator.engine.layout_gen.catalog import CATALOG
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.validation import validate
from store_emulator.engine.files import remove_tree

from .async_executor import executor
from .currencies import project_currency
from .errors import AppError, job_failure
from .providers import PRESETS, assistive_vision_model, ensure_local_ready, resolve_model
from .setups import set_active_setup, setup_summary
from .storage import images as image_storage
from .storage.io import DATA_DIR, now_iso, read_json, write_json
from .storage.setups import metadata_path, new_setup_data, read_setup, setup_path

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
STORED_MAX_SIDE = 3000
_SAFE_ID = re.compile(RESOURCE_ID_PATTERN)
_MIN_STATUS_INTERVAL_SEC = 0.5
# Grounding DINO holds ~1 GB while loaded: one capture at a time uses it.
_GDINO_LOCK = threading.Lock()


class CaptureView(BaseModel):
    status: CaptureStatus
    result: CaptureResult | None = None


class CaptureItemEdit(BaseModel):
    """One product of the corrected planogram. Products left out of the list are deleted."""
    id: str | None = Field(default=None, description="existing item id; omit for a product the user adds")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    brand: str = ""
    size: str = ""
    category: str = Field(default="", description="catalog category key or free text (mapped); empty = keep / infer")
    price: int | None = Field(default=None, ge=0, description="minor units (cents, won); null = keep or estimate")
    facings: int = Field(default=1, ge=1, le=24)
    level: int | None = Field(default=None, ge=1, le=4, description="rack level 1 (bottom) – 4 (top)")
    merged_from: list[str] = Field(default_factory=list[str], description="ids of items merged into this one")


class CaptureUpdate(BaseModel):
    items: list[CaptureItemEdit]


class ApplyResult(BaseModel):
    setup_id: str
    setup: dict[str, object]
    rack_ids: list[str]
    face: str
    placed_items: int
    placed_facings: int
    dropped: list[str]
    notes: list[str]


def _check_id(value: str, what: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise AppError(f"invalid {what}: {value}", 400)


def _base_dir(pid: str) -> Path:
    _check_id(pid, "project id")
    return Path(DATA_DIR) / pid / "captures"


def _dir(pid: str, cid: str) -> Path:
    _check_id(cid, "capture id")
    return _base_dir(pid) / cid


def _write_status(pid: str, status: CaptureStatus) -> None:
    write_json(_dir(pid, status.capture_id) / "status.json", status.model_dump(mode="json"))


def _read_status(pid: str, cid: str) -> CaptureStatus:
    path = _dir(pid, cid) / "status.json"
    if not path.exists():
        raise AppError(f"capture not found: {cid}", 404)
    return CaptureStatus.model_validate(read_json(path))


def _read_result(pid: str, cid: str) -> CaptureResult | None:
    path = _dir(pid, cid) / "result.json"
    return CaptureResult.model_validate(read_json(path)) if path.exists() else None


def _with_counts(status: CaptureStatus, result: CaptureResult) -> CaptureStatus:
    return status.model_copy(update={
        "items": len(result.items), "facings": result.facings, "gaps": len(result.gaps), "levels": len(result.bands),
    })


# ── model and detector selection ────────────────────────────────────────────────

def capture_llm_config(config: SimulationConfig, model: str) -> LLMConfig | None:
    """LLM config for reading products: the given model reference, or the app's vision model.

    "none" disables recognition (facings and gaps only). Sampling is greedy and cached so a capture
    re-run on the same photo costs nothing.
    """
    if model.strip().lower() == "none":
        return None
    base = LLMConfig(
        temperature=0.0, max_tokens=320, seed=0, timeout_sec=300.0,
        cache_dir=str(Path(DATA_DIR) / "llm_cache" / "capture"),
    )
    if model.strip():
        try:
            return resolve_model(model.strip(), base=base)
        except ValueError as e:
            raise AppError(str(e), 400) from e
    vlm = config.engines.vlm_glance.llm
    # The app's vision model, or a cloud provider's when that is the local model and it is not running while a key is
    # set up (as for reading a pack). Through resolve_model: the default local endpoint follows TwinStore's own
    # server (port, request limit).
    alternative = assistive_vision_model("", vlm)
    if alternative:
        try:
            return resolve_model(alternative, base=base)
        except ValueError as e:
            raise AppError(str(e), 400) from e
    resolved = resolve_model(vlm.model, base=base.model_copy(update={
        "api_base": vlm.api_base, "structured_output": vlm.structured_output, "api_key": vlm.api_key,
    }))
    if resolved.api_base:
        try:   # a local server that does not answer would "read" every product as Product 1.1, 1.2, …
            ensure_local_ready(resolved.api_base)
        except ValueError as e:
            raise AppError(str(e), 503) from e
    return resolved


def model_has_vision(model: str) -> bool:
    """Vision flag of a model reference (unknown models are assumed to see, as in the model picker)."""
    parsed = ModelRef.parse(model) if model else None
    if parsed is None:
        return True
    meta = next((m for m in PRESETS[parsed.provider].models if m.id == parsed.model), None)
    return meta.vision if meta else True


def choose_detector(options: CaptureOptions, llm: LiteLLMClient | None) -> FacingDetector:
    kind = options.detector
    if kind == "auto":
        if gdino_available():
            kind = "gdino"
        elif llm is not None and model_has_vision(options.model):
            kind = "vlm"
        else:
            kind = "classic"
    if kind == "gdino":
        if not gdino_available():
            raise AppError("the gdino detector needs the optional dependencies: uv sync --extra capture", 400)
        return GroundingDinoDetector()
    if kind == "vlm":
        if llm is None:
            raise AppError("the vlm detector needs a vision model (model must not be 'none')", 400)
        return VLMGroundingDetector(llm, model=llm.model)
    return ClassicDetector()


# ── create / run ─────────────────────────────────────────────────────────────────

def prepare_photo(data: bytes, filename: str) -> Image.Image:
    """Decoded, upright, metadata-free photo, at most STORED_MAX_SIDE px (capture coordinates refer to it)."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError(f"image too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)", 413)
    try:
        photo = load_photo(data)
    except Image.DecompressionBombError as e:
        raise AppError("Image dimensions are too large; reduce the resolution and try again.", 413) from e
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise AppError(f"not a readable image (JPEG, PNG or WebP): {filename}", 422) from e
    if min(photo.size) < 120:
        raise AppError("image too small: at least 120 px on the short side", 422)
    s = min(1.0, STORED_MAX_SIDE / max(photo.size))
    if s < 1.0:
        photo = photo.resize((round(photo.width * s), round(photo.height * s)), Image.Resampling.LANCZOS)
    return photo


def create_capture(
    pid: str, data: bytes, filename: str, options: CaptureOptions, config: SimulationConfig,
    *, request_id: str | None = None,
) -> CaptureStatus:
    """Store a photo and start recognition; stable request IDs replay the accepted job."""
    _check_id(pid, "project id")
    if not metadata_path(pid).exists():
        raise AppError(f"project not found: {pid}", 404)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("image too large (max 25 MB)", 413)
    options = options.model_copy(update={"currency": (options.currency or project_currency(pid, config.currency)).upper()})
    if request_id is None:
        return _start_capture(pid, f"cap_{uuid.uuid4().hex[:8]}", data, filename, options, config, "")
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise AppError("Invalid upload request id", 422)
    digest = hashlib.sha256(json.dumps({
        "image": hashlib.sha256(data).hexdigest(), "filename": filename,
        "options": options.model_dump(mode="json"),
    }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    cid = f"cap_upload_{request_id}"
    base = _base_dir(pid)
    base.mkdir(parents=True, exist_ok=True)
    try:
        # Wait for another photo being accepted (decoding a 25 MB photo takes seconds) rather than refusing at once: a
        # second tab's queue paused on that refusal until retried by hand.
        with FileLock(base / ".upload.lock", timeout=60):
            if (_dir(pid, cid) / "status.json").exists():
                accepted = _read_status(pid, cid)
                if accepted.upload_sha256 != digest:
                    raise AppError("This upload request belongs to a different photo or settings", 409)
                return accepted
            if (base / ".uploads" / f"{cid}.json").exists():
                raise AppError("This photo was removed or its upload was interrupted. Clear the local entry and choose it again for a new attempt", 409)
            return _start_capture(pid, cid, data, filename, options, config, digest)
    except Timeout as exc:
        raise AppError("Another photo is being accepted. Retry this upload shortly", 409) from exc


def _start_capture(
    pid: str, cid: str, data: bytes, filename: str, options: CaptureOptions,
    config: SimulationConfig, digest: str,
) -> CaptureStatus:
    photo = prepare_photo(data, filename)
    llm_config = capture_llm_config(config, options.model)
    if options.detector == "gdino" and not gdino_available():
        raise AppError("the gdino detector needs the optional dependencies: uv sync --extra capture", 400)
    if options.detector == "vlm" and llm_config is None:
        raise AppError("the vlm detector needs a vision model (model must not be 'none')", 400)
    if digest:
        # Keep a receipt outside the removable photo directory; replay must not resurrect deletion.
        write_json(_base_dir(pid) / ".uploads" / f"{cid}.json", {"upload_sha256": digest})
    folder = _dir(pid, cid)
    folder.mkdir(parents=True, exist_ok=True)
    photo.save(folder / "image.jpg", format="JPEG", quality=92)
    status = CaptureStatus(
        capture_id=cid, status="pending", stage="queued", options=options, image_name=filename[:200],
        image_size=photo.size, created_at=now_iso(), upload_sha256=digest,
    )
    _write_status(pid, status)
    try:
        executor.submit(_run_job, pid, status, llm_config)
    except RuntimeError as exc:
        _write_status(pid, status.model_copy(update={"status": "failed", "error": "Could not start recognition. Retry as a new attempt.", "finished_at": now_iso()}))
        raise AppError("Could not start recognition. Retry this upload to inspect its status", 503) from exc
    return status


def run_capture_sync(
    photo: Image.Image, options: CaptureOptions, llm_config: LLMConfig | None, *, salt: str = "",
    on_stage: "StageWriter | None" = None,
) -> CaptureResult:
    """Run the whole pipeline in the calling thread (CLI and background jobs)."""
    llm = LiteLLMClient(llm_config) if llm_config is not None else None
    detector = choose_detector(options, llm)
    labeler = VLMLabeler(llm, currency=options.currency) if llm is not None else None

    async def go() -> CaptureResult:
        run = await capture_shelf(
            photo, detector=detector, labeler=labeler, currency=options.currency, rack_type=options.rack_type,
            model=options.model or (llm_config.model if llm_config else ""), salt=salt,
            on_stage=on_stage.update if on_stage is not None else None,
        )
        return run.result

    try:
        if isinstance(detector, GroundingDinoDetector):
            with _GDINO_LOCK:
                return asyncio.run(go())
        return asyncio.run(go())
    finally:
        if isinstance(detector, GroundingDinoDetector):
            detector.close()


class StageWriter:
    """Throttled status.json updates from the pipeline's stage callback."""

    def __init__(self, pid: str, status: CaptureStatus) -> None:
        self.pid = pid
        self.status = status
        self._last = 0.0

    def update(self, stage: str, progress: float) -> None:
        now = time.monotonic()
        changed = stage != self.status.stage
        self.status = self.status.model_copy(update={"stage": stage, "progress": round(progress, 3)})
        if changed or now - self._last >= _MIN_STATUS_INTERVAL_SEC:
            self._last = now
            _write_status(self.pid, self.status)


def _run_job(pid: str, status: CaptureStatus, llm_config: LLMConfig | None) -> None:
    status = status.model_copy(update={"status": "running", "stage": "detecting"})
    _write_status(pid, status)
    writer = StageWriter(pid, status)
    folder = _dir(pid, status.capture_id)
    try:
        photo = Image.open(folder / "image.jpg").convert("RGB")
        result = run_capture_sync(photo, status.options, llm_config, salt=status.capture_id, on_stage=writer)
        payload = json.loads(result.model_dump_json())
        write_json(folder / "result.auto.json", payload)
        write_json(folder / "result.json", payload)
        (folder / "overlay.png").write_bytes(render_overlay(photo, result))
        final = _with_counts(writer.status, result).model_copy(update={
            "status": "completed", "stage": "done", "progress": 1.0, "finished_at": now_iso(),
        })
    except Exception as e:  # surface any failure to the UI instead of a stuck job
        logger.exception(f"[capture] {status.capture_id} failed")
        final = writer.status.model_copy(update={
            "status": "failed", "error": job_failure(e, "Reading the shelf photo failed"), "finished_at": now_iso(),
        })
    _write_status(pid, final)


def save_capture(
    pid: str, photo: Image.Image, filename: str, options: CaptureOptions, result: CaptureResult,
) -> CaptureStatus:
    """Store a capture computed elsewhere (the CLI) exactly like an uploaded one, so the app can apply it."""
    _check_id(pid, "project id")
    if not metadata_path(pid).exists():
        raise AppError(f"project not found: {pid}", 404)
    cid = f"cap_{uuid.uuid4().hex[:8]}"
    folder = _dir(pid, cid)
    folder.mkdir(parents=True, exist_ok=True)
    photo.save(folder / "image.jpg", format="JPEG", quality=92)
    payload = json.loads(result.model_dump_json())
    write_json(folder / "result.auto.json", payload)
    write_json(folder / "result.json", payload)
    (folder / "overlay.png").write_bytes(render_overlay(photo, result))
    now = now_iso()
    status = _with_counts(CaptureStatus(
        capture_id=cid, status="completed", stage="done", progress=1.0, options=options, image_name=filename[:200],
        image_size=photo.size, created_at=now, finished_at=now,
    ), result)
    _write_status(pid, status)
    return status


# ── read / list / delete ─────────────────────────────────────────────────────────

def get_capture(pid: str, cid: str) -> CaptureView:
    return CaptureView(status=_read_status(pid, cid), result=_read_result(pid, cid))


def list_captures(pid: str) -> list[CaptureStatus]:
    base = _base_dir(pid)
    if not base.is_dir():
        return []
    out: list[CaptureStatus] = []
    for p in base.iterdir():
        if (p / "status.json").exists():
            try:
                out.append(CaptureStatus.model_validate(read_json(p / "status.json")))
            except ValueError as e:   # one damaged capture must not hide the others
                logger.warning(f"[capture] skipping {pid}/{p.name}: {e}")
    return sorted(out, key=lambda s: s.created_at, reverse=True)


def delete_capture(pid: str, cid: str) -> None:
    status = _read_status(pid, cid)
    if status.status in ("pending", "running"):
        raise AppError("capture is still being processed", 409)
    if _lab_job_running(_dir(pid, cid)):
        # The job would write its results back under the deleted capture.
        raise AppError("a Shelf Lab job on this capture is still running; delete it when the job has finished", 409)
    remove_tree(_dir(pid, cid))


def _lab_job_running(folder: Path) -> bool:
    for status_file in (folder / "lab" / "jobs").glob("*/status.json"):
        try:
            state = cast(dict[str, object], read_json(status_file)).get("status")
        except (OSError, ValueError):
            continue
        if state in ("pending", "running"):
            return True
    return False


def capture_image_path(pid: str, cid: str, *, overlay: bool) -> Path:
    _read_status(pid, cid)
    path = _dir(pid, cid) / ("overlay.png" if overlay else "image.jpg")
    if not path.exists():
        raise AppError("overlay not ready yet" if overlay else "image missing", 404)
    return path


# ── corrections ──────────────────────────────────────────────────────────────────

def _resolve_category(edit: CaptureItemEdit, base: CaptureItem | None, rack_type: str) -> str:
    if edit.category in CATALOG:
        return edit.category
    if edit.category.strip():
        return match_category(edit.category, f"{edit.brand} {edit.name}", rack_type=rack_type)
    if base is not None and base.category and base.name == edit.name:
        return base.category
    return match_category("", f"{edit.brand} {edit.name}", rack_type=rack_type)


def apply_edits(result: CaptureResult, edits: list[CaptureItemEdit]) -> CaptureResult:
    """Corrected planogram: names/prices/facings edited, items deleted (left out), merged or added."""
    by_id = {it.id: it for it in result.items}
    ids = [e.id for e in edits if e.id]
    if len(ids) != len(set(ids)):
        raise AppError("duplicate item id in corrections", 400)
    unknown = [i for e in edits for i in [*([e.id] if e.id else []), *e.merged_from] if i not in by_id]
    if unknown:
        raise AppError(f"unknown item id(s): {', '.join(sorted(set(unknown)))}", 400)
    merged = [m for e in edits for m in e.merged_from]
    if len(merged) != len(set(merged)):
        raise AppError("a source item can only be merged once", 400)
    if set(merged) & set(ids):
        raise AppError("an item cannot be both kept and merged into another", 400)
    items: list[CaptureItem] = []
    order_in_level: dict[int, int] = {}
    next_new = 1 + max((int(i[1:]) for i in by_id if i[1:].isdigit()), default=0)
    for e in edits:
        base = by_id.get(e.id) if e.id else None
        level = e.level or (base.level if base else 1)
        category = _resolve_category(e, base, result.rack_type)
        renamed = base is None or base.name != e.name.strip() or base.size != e.size.strip()
        if e.price is not None:
            price, estimated = e.price, False
        elif base is not None and not renamed and base.price is not None:
            price, estimated = base.price, base.price_estimated
        else:
            price, estimated = typical_price(category, e.name, result.currency)[0], True
        boxes = list(base.boxes) if base else []
        for mid in e.merged_from:
            boxes += by_id[mid].boxes
        item_id = e.id or f"i{next_new:02d}"
        if not e.id:
            next_new += 1
        order = order_in_level.get(level, 0)
        order_in_level[level] = order + 1
        items.append(CaptureItem(
            id=item_id, band=base.band if base else -1, level=level, order=order, facings=e.facings,
            boxes=sorted(boxes, key=lambda b: b.x1), sku=sku_for(e.name.strip(), e.brand.strip(), e.size.strip()),
            name=e.name.strip(), brand=e.brand.strip(), size=e.size.strip(), category=category,
            raw_category=base.raw_category if base else "", price=price, price_estimated=estimated,
            price_text=base.price_text if base and not renamed else "",
            confidence=10 if base is None or renamed else base.confidence, labeled=True,
        ))
    weights: dict[str, int] = {}
    for it in items:
        if it.category:
            weights[it.category] = weights.get(it.category, 0) + it.facings
    dominant = max(weights, key=lambda c: weights[c]) if weights else result.dominant_category
    return result.model_copy(update={"items": items, "dominant_category": dominant, "edited": True})


def update_capture(pid: str, cid: str, update: CaptureUpdate) -> CaptureView:
    status = _read_status(pid, cid)
    result = _read_result(pid, cid)
    if status.status != "completed" or result is None:
        raise AppError("capture is not finished yet", 409)
    corrected = apply_edits(result, update.items)
    folder = _dir(pid, cid)
    write_json(folder / "result.json", json.loads(corrected.model_dump_json()))
    photo = Image.open(folder / "image.jpg").convert("RGB")
    (folder / "overlay.png").write_bytes(render_overlay(photo, corrected))
    status = _with_counts(status, corrected)
    _write_status(pid, status)
    return CaptureView(status=status, result=corrected)


# ── apply to a layout ────────────────────────────────────────────────────────────

def _save_sku_images(pid: str, cid: str, result: CaptureResult) -> None:
    """Use each product's photo crop as its SKU image when the SKU has none yet."""
    manifest = image_storage.load_manifest(pid)
    photo: Image.Image | None = None
    for item in result.items:
        if item.sku in manifest or not item.boxes:
            continue
        if photo is None:
            photo = Image.open(_dir(pid, cid) / "image.jpg").convert("RGB")
        b = item.boxes[len(item.boxes) // 2]
        crop = photo.crop((round(b.x1), round(b.y1), round(b.x2), round(b.y2)))
        crop.thumbnail((384, 384), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=88)
        try:
            image_storage.save_image(pid, item.sku, buf.getvalue(), f"{item.sku}.jpg")
        except (image_storage.ImageStorageError, ValueError) as e:
            logger.warning(f"[capture] could not save SKU image {item.sku}: {e}")


def apply_captures(
    pid: str, capture_ids: list[str], setup_id: str, *, rack_id: str | None = None, face: str | None = None,
    new_rack: bool = False, name: str | None = None, default_currency: str = "USD",
) -> ApplyResult:
    """Save a new draft layout (child of `setup_id`) with the captured shelves; the source stays untouched.

    With `rack_id` (and one capture) that rack's face is replaced; otherwise every capture becomes new
    rack(s) on free floor next to an aisle.
    """
    if not capture_ids:
        raise AppError("no capture given", 400)
    results: list[CaptureResult] = []
    for cid in capture_ids:
        status = _read_status(pid, cid)
        result = _read_result(pid, cid)
        if status.status != "completed" or result is None:
            raise AppError(f"capture {cid} is not finished yet", 409)
        if not result.items:
            raise AppError(f"capture {cid} has no products", 409)
        results.append(result)
    try:
        source = read_setup(pid, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404) from None
    if not source.get("store"):
        raise AppError("this layout has no store yet", 400)
    store = Store.model_validate(source["store"])
    currency = store.currency or project_currency(pid, default_currency)
    if any(result.currency != currency for result in results):
        raise AppError(f"Every capture must use the layout's price currency ({currency}); prices are not converted automatically.", 422)
    store = store.model_copy(update={"currency": currency})
    try:
        if rack_id and not new_rack:
            if len(results) != 1:
                raise AppError("replacing a rack face takes exactly one capture", 400)
            target_face = Face(face) if face else None
            new_store, report = replace_rack_face(store, results[0], rack_id, target_face)
        else:
            new_store, report = add_capture_racks(store, results)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    errors = [i for i in validate(new_store) if i.severity == "error"]
    if errors:
        raise AppError(f"the resulting layout is invalid: {errors[0].message}", 409)
    for cid, result in zip(capture_ids, results, strict=True):
        _save_sku_images(pid, cid, result)
    label = "shelf photo" if len(results) == 1 else f"{len(results)} shelf photos"
    final_name = name or f"{source.get('name') or 'layout'} ({label})"
    memo = _memo(capture_ids, results, report)
    new_setup = new_setup_data(final_name, setup_id, new_store.model_dump(mode="json"), memo[:1000])
    if source.get("building") is not None:
        new_setup["building"] = BuildingFloorInfo.model_validate(source["building"]).model_dump(mode="json")
    if source.get("operations") is not None:
        new_setup["operations"] = source["operations"]
    write_json(setup_path(pid, new_setup["id"]), new_setup)
    set_active_setup(pid, new_setup["id"])
    for cid in capture_ids:
        status = _read_status(pid, cid)
        _write_status(pid, status.model_copy(update={"applied_setup_ids": [*status.applied_setup_ids, new_setup["id"]]}))
    return ApplyResult(
        setup_id=new_setup["id"], setup=setup_summary(pid, new_setup), rack_ids=report.rack_ids,
        face=report.face.value, placed_items=report.placed_items, placed_facings=report.placed_facings,
        dropped=report.dropped, notes=report.notes,
    )


def _memo(capture_ids: list[str], results: list[CaptureResult], report: PlacementReport) -> str:
    products = sum(len(r.items) for r in results)
    where = f"rack {', '.join(report.rack_ids)} face {report.face.value}"
    dropped = f"; {len(report.dropped)} product(s) did not fit" if report.dropped else ""
    return f"shelf capture {', '.join(capture_ids)}: {products} products → {where}{dropped}"


def recover_interrupted_captures() -> int:
    """A restarted single-worker server has no surviving capture executor jobs."""
    recovered = 0
    for path in Path(DATA_DIR).glob("*/captures/*/status.json"):
        try:
            status = CaptureStatus.model_validate_json(path.read_bytes())
            if status.status not in ("pending", "running"):
                continue
            status = status.model_copy(update={
                "status": "failed", "error": "Recognition was interrupted by a server restart. Upload again for a new attempt.",
                "finished_at": now_iso(),
            })
            write_json(path, status.model_dump(mode="json"))
            recovered += 1
        except (OSError, ValueError):
            logger.warning("Could not recover capture status %s", path, exc_info=True)
    return recovered
