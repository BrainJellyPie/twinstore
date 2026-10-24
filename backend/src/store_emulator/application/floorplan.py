"""Floor plan import: a plan image (hand sketch, CAD export, PDF page) becomes a new draft layout.

The plan is read by a vision-language model when one is configured (fixture kinds and category words
written on the plan), falling back to the model-free reader (ink geometry) when the model is off or
fails. The image is kept next to the layout in `.data/<pid>/floorplans/<setup id>.png`.
"""

import asyncio
import base64
import io
import logging
import math
import re
from collections.abc import Sized
from contextlib import closing
from pathlib import Path
from threading import Lock
from typing import Any, cast

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.floorplan import FloorPlanReading, PlanReader
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import RESOURCE_ID_PATTERN
from store_emulator.engine.floorplan import classic_read, plan_to_store, vlm_read
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.validation import validate

from .capture import capture_llm_config
from .errors import AppError
from .setups import set_active_setup, setup_summary, setup_tree_transaction
from .storage.io import DATA_DIR, read_json, write_json
from .storage.setups import metadata_path, new_setup_data, setup_path

logger = logging.getLogger(__name__)

MAX_PLAN_BYTES = 25 * 1024 * 1024
MAX_PLAN_SIDE = 2400
MAX_IMAGE_PIXELS = 25_000_000
_PDF_LOCK = Lock()  # PDFium native operations must not overlap across request threads.
_SAFE_ID = re.compile(RESOURCE_ID_PATTERN)


class FloorPlanImport(BaseModel):
    setup_id: str
    setup: dict[str, object]
    reading: FloorPlanReading
    grid_size: tuple[int, int]
    racks: int
    notes: list[str]
    warnings: list[str]
    source_page: int = 1
    source_pages: int = 1
    source_rotation: int = 0


class FloorPlanPreview(BaseModel):
    page_number: int
    page_count: int
    rotation: int
    width: int
    height: int
    image: str


def _load_plan_page(data: bytes, filename: str, *, page_number: int, rotation: int) -> tuple[Image.Image, int]:
    """Decode one selected page, with bounded rendering and detached native buffers."""
    if len(data) > MAX_PLAN_BYTES:
        raise AppError("plan too large (max 25 MB)", 413)
    if page_number < 1 or rotation not in (0, 90, 180, 270):
        raise AppError("choose a page starting at 1 and a rotation of 0, 90, 180 or 270 degrees", 422)
    page_count = 1
    if data[:5] == b"%PDF-" or filename.lower().endswith(".pdf"):
        try:
            import pypdfium2  # type: ignore[import-not-found]  # untyped native PDF binding
        except ImportError:
            raise AppError("reading PDF plans needs `uv pip install pypdfium2`; or upload the page as PNG/JPEG", 400) from None
        try:
            with _PDF_LOCK, closing(pypdfium2.PdfDocument(data)) as pdf:  # type: ignore[reportUnknownMemberType]  # native binding
                page_count = len(cast(Sized, pdf))
                if page_count == 0:
                    raise AppError("the PDF has no pages", 400)
                if page_number > page_count:
                    raise AppError(f"this PDF has {page_count} pages; choose a page in that range", 422)
                with closing(pdf[page_number - 1]) as page:  # type: ignore[reportUnknownVariableType]
                    width, height = cast(tuple[float, float], page.get_size())  # type: ignore[reportUnknownMemberType]
                    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
                        raise AppError("the PDF page has invalid dimensions", 400)
                    scale = min(2.0, MAX_PLAN_SIDE / max(width, height))
                    with closing(page.render(scale=scale)) as bitmap:  # type: ignore[reportUnknownMemberType]
                        # Copy the pixels before the bitmap's native buffer is released.
                        img = cast(Image.Image, bitmap.to_pil()).convert("RGB")  # type: ignore[reportUnknownMemberType]
        except (RuntimeError, ValueError, IndexError) as e:
            raise AppError("the PDF could not be read; use a valid, unlocked PDF or upload PNG/JPEG", 400) from e
    else:
        if page_number != 1:
            raise AppError("an image has one page; choose page 1", 422)
        try:
            with Image.open(io.BytesIO(data)) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise AppError("plan image exceeds 25 megapixels; resize it before importing", 413)
                img = ImageOps.exif_transpose(source).convert("RGB")
        except Image.DecompressionBombError as e:
            raise AppError("plan image exceeds the supported pixel limit", 413) from e
        except (UnidentifiedImageError, OSError) as e:
            raise AppError("not an image the server can read (use PNG, JPEG, WebP or PDF)", 400) from e
        img.thumbnail((MAX_PLAN_SIDE, MAX_PLAN_SIDE))
    if rotation:
        img = img.rotate(-rotation, expand=True)
    return img, page_count


def load_plan_image(data: bytes, filename: str) -> Image.Image:
    """Backward-compatible first-page reader."""
    return _load_plan_page(data, filename, page_number=1, rotation=0)[0]


def preview_floor_plan(pid: str, data: bytes, filename: str, *, page_number: int, rotation: int) -> FloorPlanPreview:
    if not _SAFE_ID.fullmatch(pid) or not metadata_path(pid).exists():
        raise AppError(f"project not found: {pid}", 404)
    img, page_count = _load_plan_page(data, filename, page_number=page_number, rotation=rotation)
    img.thumbnail((1000, 1000))
    output = io.BytesIO()
    img.save(output, format="PNG")
    return FloorPlanPreview(page_number=page_number, page_count=page_count, rotation=rotation, width=img.width,
                            height=img.height, image="data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii"))


def read_plan(img: Image.Image, reader: PlanReader, model: str, config: SimulationConfig) -> FloorPlanReading:
    if reader == "classic":
        return classic_read(img)
    llm_config = capture_llm_config(config, model) if model.strip().lower() != "none" else None
    if llm_config is None:
        if reader == "vlm":
            raise AppError("the vlm reader needs a vision model", 400)
        return classic_read(img)
    try:
        # A whole plan includes coordinates, kinds and labels for many fixtures.
        return asyncio.run(vlm_read(LiteLLMClient(llm_config.model_copy(update={"max_tokens": 6144})), img, model=llm_config.model))
    except Exception as e:
        if reader == "vlm":
            raise AppError(f"the vision model could not read the plan: {type(e).__name__}: {e}"[:300], 502) from e
        logger.info(f"[floorplan] vlm reader failed ({type(e).__name__}); using the classic reader")
        reading = classic_read(img)
        return reading.model_copy(update={"notes": [f"vision model unavailable ({type(e).__name__}); read by geometry", *reading.notes]})


def import_floor_plan(
    pid: str, data: bytes, filename: str, *, reader: PlanReader, model: str, name: str | None, config: SimulationConfig,
    page_number: int = 1, rotation: int = 0,
) -> FloorPlanImport:
    if not _SAFE_ID.fullmatch(pid) or not metadata_path(pid).exists():
        raise AppError(f"project not found: {pid}", 404)
    img, page_count = _load_plan_page(data, filename, page_number=page_number, rotation=rotation)
    try:
        reading = read_plan(img, reader, model, config)
    except ValueError as e:
        raise AppError(str(e), 422) from e
    reading.notes.append(f"Imported page {page_number} of {page_count}; rotation {rotation} degrees clockwise.")
    try:
        meta = cast(dict[str, Any], read_json(metadata_path(pid)))
    except FileNotFoundError as exc:
        img.close()
        raise AppError(f"project not found: {pid}", 404) from exc
    schedule = [DaySchedule.model_validate(d) for d in cast(list[dict[str, Any]], meta.get("weekly_schedule") or [])]
    layout_name = name or f"floor plan ({Path(filename).stem[:40] or 'plan'})"
    store, notes = plan_to_store(reading, currency=str(meta.get("currency") or config.currency), name=str(meta.get("name") or layout_name),
                                 store_type=str(meta.get("store_type") or "convenience"), schedule=schedule)
    issues = validate(store)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise AppError(f"the plan did not give a valid layout: {errors[0].message}", 422)
    setup = new_setup_data(layout_name, None, store.model_dump(mode="json"),
                           f"floor plan import ({reading.reader}), page {page_number}/{page_count}, rotation {rotation}: {'; '.join(notes)}"[:1000])
    with closing(img), io.BytesIO() as encoded:
        img.thumbnail((2000, 2000))
        img.save(encoded, format="PNG")
        image_bytes = encoded.getvalue()
    path = setup_path(pid, setup["id"])
    image_path = Path(DATA_DIR) / pid / "floorplans" / f"{setup['id']}.png"
    with setup_tree_transaction(pid):
        if path.exists() or image_path.exists():
            raise AppError("This imported layout identifier already exists. Retry to create a new layout.", 409)
        result = FloorPlanImport(
            setup_id=setup["id"], setup=setup_summary(pid, setup), reading=reading, grid_size=store.grid_size,
            racks=sum(1 for r in store.racks if r.slots), notes=[*reading.notes, *notes],
            warnings=[i.message for i in issues if i.severity == "warning"],
            source_page=page_number, source_pages=page_count, source_rotation=rotation,
        )
        try:
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(image_bytes)
            write_json(path, setup)
            set_active_setup(pid, setup["id"])
        except Exception:
            for created in (path, image_path):
                try:
                    created.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove failed floor plan import file %s", created, exc_info=True)
            raise
    return result
