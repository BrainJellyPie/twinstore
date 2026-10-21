"""Photo inputs: storefront appeal sets a venue's pull in the neighborhood; receipts score a run.

Storefront ratings use the app's vision model (or the given model), falling back to image
statistics when no model answers. Receipts need a vision model; their lines are matched to the
products of a layout and returned with a POS-export CSV the fidelity report accepts.
"""

import asyncio
import io
import logging
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.store import Store
from store_emulator.domain.town import Town
from store_emulator.domain.vision_inputs import ReceiptReading, StorefrontAppeal
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.vision_inputs import (
    classic_appeal,
    match_lines,
    receipts_csv,
    vlm_appeal,
    vlm_receipt,
)

from .capture import capture_llm_config
from .errors import AppError
from .storage.io import DATA_DIR
from .storage.runs import load_run_store
from .storage.setups import metadata_path, read_setup
from .town import require_town, save_town

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 25 * 1024 * 1024
_SAFE_ID = re.compile(r"[a-z0-9_]+")


class StorefrontResult(BaseModel):
    venue_id: str
    appeal: StorefrontAppeal
    previous_attractiveness: float
    town: Town


class ReceiptsResult(BaseModel):
    receipts: list[ReceiptReading]
    matched_lines: int
    unmatched_lines: int
    csv: str


def _photo(data: bytes) -> Image.Image:
    if len(data) > MAX_PHOTO_BYTES:
        raise AppError("photo too large (max 25 MB)", 413)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise AppError("not an image the server can read (use PNG, JPEG or WebP)", 400) from e
    return img.convert("RGB")


def _client(config: SimulationConfig, model: str) -> LiteLLMClient | None:
    llm_config = capture_llm_config(config, model) if model.strip().lower() != "none" else None
    return LiteLLMClient(llm_config.model_copy(update={"max_tokens": 1500})) if llm_config is not None else None


def rate_storefront(pid: str, venue_id: str, data: bytes, *, model: str, config: SimulationConfig) -> StorefrontResult:
    town = require_town(pid)
    venue = town.get_venue(venue_id)
    if venue is None:
        raise AppError(f"venue not found: {venue_id}", 404)
    img = _photo(data)
    llm = _client(config, model)
    appeal: StorefrontAppeal
    if llm is None:
        appeal = classic_appeal(img)
    else:
        try:
            appeal = asyncio.run(vlm_appeal(llm, img, model=llm.model))
        except Exception as e:  # noqa: BLE001 — any model failure falls back to image statistics
            logger.info(f"[vision_inputs] storefront model failed ({type(e).__name__}); using image statistics")
            appeal = classic_appeal(img)
            appeal = appeal.model_copy(update={"reasons": f"vision model unavailable ({type(e).__name__}); {appeal.reasons}"})
    previous = venue.attractiveness
    venues = [v.model_copy(update={"attractiveness": appeal.attractiveness}) if v.id == venue_id else v for v in town.venues]
    saved = save_town(pid, town.model_copy(update={"venues": venues}))
    return StorefrontResult(venue_id=venue_id, appeal=appeal, previous_attractiveness=previous, town=saved)


def _products(pid: str, setup_id: str | None, run_id: str | None) -> dict[str, str]:
    """Product name → SKU of a run's store (preferred: the store the run simulated) or of a layout."""
    store: Store | None = None
    if run_id:
        if not _SAFE_ID.fullmatch(run_id):
            raise AppError(f"invalid run id: {run_id}", 400)
        base = Path(DATA_DIR) / pid / "runs" / run_id
        if not (base / "input").exists():
            raise AppError(f"run not found: {run_id}", 404)
        store = load_run_store(base)
    elif setup_id:
        try:
            data = read_setup(pid, setup_id).get("store")
        except FileNotFoundError:
            raise AppError(f"setup not found: {setup_id}", 404) from None
        store = Store.model_validate(data) if data else None
    if store is None:
        return {}
    return {item.name: item.sku for _, slot in store.all_slots for item in slot.items}


def read_receipts(
    pid: str, photos: list[bytes], *, setup_id: str | None, model: str, config: SimulationConfig, run_id: str | None = None,
) -> ReceiptsResult:
    if not _SAFE_ID.fullmatch(pid) or not metadata_path(pid).exists():
        raise AppError(f"project not found: {pid}", 404)
    if not photos:
        raise AppError("no receipt photo given", 400)
    llm = _client(config, model)
    if llm is None:
        raise AppError("reading receipts needs a vision model", 400)
    products = _products(pid, setup_id, run_id)
    readings: list[ReceiptReading] = []
    for k, data in enumerate(photos):
        img = _photo(data)
        try:
            reading = asyncio.run(vlm_receipt(llm, img, receipt_id=f"r{k + 1:03d}", default_currency=config.currency))
        except Exception as e:  # noqa: BLE001 — one unreadable receipt must not fail the batch
            readings.append(ReceiptReading(receipt_id=f"r{k + 1:03d}", notes=[f"could not read: {type(e).__name__}: {e}"[:200]]))
            continue
        readings.append(match_lines(reading, products) if products else reading)
    matched = sum(1 for r in readings for line in r.lines if line.matched)
    total = sum(len(r.lines) for r in readings)
    return ReceiptsResult(receipts=readings, matched_lines=matched, unmatched_lines=total - matched, csv=receipts_csv(readings))
