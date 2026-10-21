"""Floor plan import: a plan image (hand sketch, CAD export, PDF page) becomes a new draft layout.

The plan is read by a vision-language model when one is configured (fixture kinds and category words
written on the plan), falling back to the model-free reader (ink geometry) when the model is off or
fails. The image is kept next to the layout in `.data/<pid>/floorplans/<setup id>.png`.
"""

import asyncio
import io
import logging
import re
from contextlib import closing
from pathlib import Path
from typing import Any, cast

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.floorplan import FloorPlanReading, PlanReader
from store_emulator.domain.store import DaySchedule
from store_emulator.engine.floorplan import classic_read, plan_to_store, vlm_read
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.validation import validate

from .capture import capture_llm_config
from .errors import AppError
from .setups import set_active_setup, setup_summary
from .storage.io import DATA_DIR, read_json, write_json
from .storage.setups import metadata_path, new_setup_data, setup_path

logger = logging.getLogger(__name__)

MAX_PLAN_BYTES = 25 * 1024 * 1024
_SAFE_ID = re.compile(r"[a-z0-9_]+")


class FloorPlanImport(BaseModel):
    setup_id: str
    setup: dict[str, object]
    reading: FloorPlanReading
    grid_size: tuple[int, int]
    racks: int
    notes: list[str]
    warnings: list[str]


def load_plan_image(data: bytes, filename: str) -> Image.Image:
    """The plan as an image; a PDF's first page is rendered when pypdfium2 is installed."""
    if len(data) > MAX_PLAN_BYTES:
        raise AppError("plan too large (max 25 MB)", 413)
    if data[:5] == b"%PDF-" or filename.lower().endswith(".pdf"):
        try:
            import pypdfium2  # type: ignore[import-not-found]  # optional: renders PDF pages
        except ImportError:
            raise AppError("reading PDF plans needs `uv pip install pypdfium2`; or upload the page as PNG/JPEG", 400) from None
        try:
            with closing(pypdfium2.PdfDocument(data)) as pdf:  # type: ignore[reportUnknownMemberType]  # optional native binding
                if len(pdf) == 0:  # type: ignore[reportUnknownArgumentType]  # optional native binding
                    raise AppError("the PDF has no pages", 400)
                with closing(pdf[0]) as page:  # type: ignore[reportUnknownVariableType]
                    with closing(page.render(scale=2)) as bitmap:  # type: ignore[reportUnknownMemberType]
                        # Copy the pixels before the bitmap's native buffer is released.
                        return cast(Image.Image, bitmap.to_pil()).convert("RGB")  # type: ignore[reportUnknownMemberType]
        except (RuntimeError, ValueError, IndexError) as e:
            raise AppError("the PDF could not be read; use a valid, unlocked PDF or upload PNG/JPEG", 400) from e
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise AppError("not an image the server can read (use PNG, JPEG, WebP or PDF)", 400) from e
    return img.convert("RGB")


def read_plan(img: Image.Image, reader: PlanReader, model: str, config: SimulationConfig) -> FloorPlanReading:
    if reader == "classic":
        return classic_read(img)
    llm_config = capture_llm_config(config, model) if model.strip().lower() != "none" else None
    if llm_config is None:
        if reader == "vlm":
            raise AppError("the vlm reader needs a vision model", 400)
        return classic_read(img)
    try:
        return asyncio.run(vlm_read(LiteLLMClient(llm_config.model_copy(update={"max_tokens": 1500})), img, model=llm_config.model))
    except Exception as e:
        if reader == "vlm":
            raise AppError(f"the vision model could not read the plan: {type(e).__name__}: {e}"[:300], 502) from e
        logger.info(f"[floorplan] vlm reader failed ({type(e).__name__}); using the classic reader")
        reading = classic_read(img)
        return reading.model_copy(update={"notes": [f"vision model unavailable ({type(e).__name__}); read by geometry", *reading.notes]})


def import_floor_plan(
    pid: str, data: bytes, filename: str, *, reader: PlanReader, model: str, name: str | None, config: SimulationConfig,
) -> FloorPlanImport:
    if not _SAFE_ID.fullmatch(pid) or not metadata_path(pid).exists():
        raise AppError(f"project not found: {pid}", 404)
    img = load_plan_image(data, filename)
    try:
        reading = read_plan(img, reader, model, config)
    except ValueError as e:
        raise AppError(str(e), 422) from e
    meta = cast(dict[str, Any], read_json(metadata_path(pid)))
    schedule = [DaySchedule.model_validate(d) for d in cast(list[dict[str, Any]], meta.get("weekly_schedule") or [])]
    layout_name = name or f"floor plan ({Path(filename).stem[:40] or 'plan'})"
    store, notes = plan_to_store(reading, currency=config.currency, name=str(meta.get("name") or layout_name),
                                 store_type=str(meta.get("store_type") or "convenience"), schedule=schedule)
    issues = validate(store)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise AppError(f"the plan did not give a valid layout: {errors[0].message}", 422)
    setup = new_setup_data(layout_name, None, store.model_dump(mode="json"), f"floor plan import ({reading.reader}): {'; '.join(notes)}"[:1000])
    write_json(setup_path(pid, setup["id"]), setup)
    set_active_setup(pid, setup["id"])
    folder = Path(DATA_DIR) / pid / "floorplans"
    folder.mkdir(parents=True, exist_ok=True)
    img.thumbnail((2000, 2000))
    img.save(folder / f"{setup['id']}.png")
    return FloorPlanImport(
        setup_id=setup["id"], setup=setup_summary(pid, setup), reading=reading, grid_size=store.grid_size,
        racks=sum(1 for r in store.racks if r.slots), notes=[*reading.notes, *notes],
        warnings=[i.message for i in issues if i.severity == "warning"],
    )
