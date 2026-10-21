"""Inputs read off photos.

Storefront appeal: a vision-language model rates how inviting a shop looks from the street (sign,
entrance, window, upkeep); the overall score sets the venue's pull in the neighborhood demand model
(Huff attractiveness, 1.0 = typical, 5/10 → 1.0, each point ±8 %). Without a model, image statistics
give a rough estimate: brightness for upkeep, colourfulness for the window, edge density in the top
band for the sign.

Receipts: the model transcribes a receipt photo (store, time, product lines, totals); lines are later
matched to the store's products so receipts can score a run like a POS export.
"""

import difflib
from typing import Protocol

import numpy as np
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from store_emulator.domain.vision_inputs import (
    ReceiptLine,
    ReceiptReading,
    StorefrontAppeal,
)
from store_emulator.engine.capture.catalog_match import normalize_text
from store_emulator.engine.capture.detect import image_data_url


class VisionLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...


def attractiveness_for(overall: float) -> float:
    return round(min(1.5, max(0.5, 0.6 + 0.08 * overall)), 3)


def _clip10(v: float) -> float:
    return round(min(10.0, max(0.0, v)), 1)


def classic_appeal(img: Image.Image) -> StorefrontAppeal:
    rgb = np.asarray(ImageOps.exif_transpose(img).convert("RGB").resize((320, 240)), dtype=np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg, yb = r - g, 0.5 * (r + g) - b
    colorful = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    top = lum[: lum.shape[0] // 3]
    edges = float((np.abs(np.diff(top, axis=1)) > 28).mean())
    upkeep = _clip10((float(lum.mean()) - 55) / 12)
    window = _clip10(colorful / 7)
    signage = _clip10(edges * 60)
    entrance = _clip10((upkeep + window) / 2)
    overall = round((signage + entrance + window + upkeep) / 4, 1)
    return StorefrontAppeal(
        method="image_stats", signage=signage, entrance=entrance, window=window, upkeep=upkeep, overall=overall,
        attractiveness=attractiveness_for(overall),
        reasons="estimated from image statistics (brightness, colourfulness, sign-band edges); connect a vision model for a judgment",
    )


class _StorefrontRating(BaseModel):
    signage: int = Field(ge=0, le=10, description="is there a visible, legible shop sign from the street")
    entrance: int = Field(ge=0, le=10, description="open, inviting, easy to walk into")
    window: int = Field(ge=0, le=10, description="products or a lit interior visible from outside")
    upkeep: int = Field(ge=0, le=10, description="bright, clean, well kept")
    overall: int = Field(ge=0, le=10, description="how likely a passer-by is to walk in")
    reasons: str = Field(default="", max_length=240)


STOREFRONT_PROMPT = """You judge shop fronts the way passers-by do. Rate this storefront photo from 0 to 10 on:
signage (a visible, legible shop sign), entrance (open, inviting, step-free), window (products or a lit interior
visible from outside), upkeep (bright, clean, well kept), and overall: how likely a passer-by is to walk in.
5 is an ordinary shop front. Give a short reason."""


async def vlm_appeal(llm: VisionLLM, img: Image.Image, *, model: str = "vlm") -> StorefrontAppeal:
    url, _ = image_data_url(ImageOps.exif_transpose(img).convert("RGB"), max_side=1024, fmt="JPEG")
    r = await llm.generate_structured_with_image_async(_StorefrontRating, STOREFRONT_PROMPT, "Rate this storefront.", url, max_retries=1, seed=0)
    return StorefrontAppeal(
        method="vlm", model=model, signage=r.signage, entrance=r.entrance, window=r.window, upkeep=r.upkeep,
        overall=r.overall, attractiveness=attractiveness_for(r.overall), reasons=r.reasons.strip(),
    )


class _ReceiptLineVLM(BaseModel):
    name: str = Field(max_length=80)
    quantity: float = 1.0
    unit_price: float | None = None
    line_total: float | None = None


class _ReceiptVLM(BaseModel):
    store: str = Field(default="", max_length=80)
    date: str = Field(default="", description="YYYY-MM-DD as printed, or empty")
    time: str = Field(default="", description="HH:MM as printed, or empty")
    currency: str = Field(default="", description="ISO 4217 code if you can tell, e.g. USD, KRW")
    lines: list[_ReceiptLineVLM] = []
    total: float | None = None


RECEIPT_PROMPT = """You transcribe shop receipts. List every purchased product line with its name as printed, quantity,
unit price and line total (numbers as printed, no currency symbols). Skip subtotals, tax, payment and change lines.
Give the store name, date (YYYY-MM-DD), time (HH:MM), currency code and the receipt total when printed."""

_ZERO_DECIMAL = {"KRW", "JPY", "VND", "IDR", "CLP", "ISK", "HUF", "TWD"}


def _minor(v: float | None, currency: str) -> int | None:
    if v is None:
        return None
    return round(v) if currency.upper() in _ZERO_DECIMAL else round(v * 100)


async def vlm_receipt(llm: VisionLLM, img: Image.Image, *, receipt_id: str, default_currency: str = "USD") -> ReceiptReading:
    url, _ = image_data_url(ImageOps.exif_transpose(img).convert("RGB"), max_side=1600, fmt="JPEG")
    r = await llm.generate_structured_with_image_async(_ReceiptVLM, RECEIPT_PROMPT, "Transcribe this receipt.", url, max_retries=1, seed=0)
    currency = (r.currency or default_currency).upper()
    lines = [ReceiptLine(name=line.name.strip(), quantity=line.quantity or 1.0, unit_price=_minor(line.unit_price, currency),
                         line_total=_minor(line.line_total, currency))
             for line in r.lines if line.name.strip()]
    stamp = f"{r.date} {r.time}".strip() if r.date else ""
    return ReceiptReading(receipt_id=receipt_id, store=r.store.strip(), timestamp=stamp, currency=currency, lines=lines,
                          total=_minor(r.total, currency))


def match_lines(reading: ReceiptReading, products: dict[str, str], *, cutoff: float = 0.72) -> ReceiptReading:
    """Lines carry the store's SKU when their name matches one of its products (`products`: name → sku)."""
    names = {normalize_text(n): sku for n, sku in products.items()}
    keys = list(names)
    out: list[ReceiptLine] = []
    for line in reading.lines:
        key = normalize_text(line.name)
        sku = names.get(key)
        if sku is None:
            close = difflib.get_close_matches(key, keys, n=1, cutoff=cutoff)
            sku = names[close[0]] if close else None
        out.append(line.model_copy(update={"sku": sku or "", "matched": sku is not None}))
    return reading.model_copy(update={"lines": out})


def receipts_csv(readings: list[ReceiptReading]) -> str:
    """POS-export CSV of matched lines (columns the fidelity report understands)."""
    rows = ["receipt_id,sku,quantity,unit_price,line_total,timestamp"]
    for r in readings:
        for line in r.lines:
            if not line.matched:
                continue
            unit = "" if line.unit_price is None else str(line.unit_price)
            total = "" if line.line_total is None else str(line.line_total)
            rows.append(f"{r.receipt_id},{line.sku},{line.quantity:g},{unit},{total},{r.timestamp}")
    return "\n".join(rows) + "\n"
