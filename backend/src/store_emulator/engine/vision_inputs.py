"""Inputs read off photos.

Storefront appeal: a vision-language model rates how inviting a shop looks from the street (sign,
entrance, window, upkeep); the overall score sets the venue's pull in the neighborhood demand model
(Huff attractiveness, 1.0 = typical, 5/10 → 1.0, each point ±8 %). Without a model, image statistics
give a rough estimate: brightness for upkeep, colourfulness for the window, edge density in the top
band for the sign.

Receipts: the model transcribes a receipt photo (store, time, product lines, totals); lines are later
matched to the store's products so receipts can score a run like a POS export.
"""

import csv
import io
import re
from typing import Protocol, Self

import numpy as np
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from store_emulator.domain.vision_inputs import (
    MAX_RECEIPT_AMOUNT,
    ReceiptLine,
    ReceiptReading,
    StorefrontAppeal,
)
from store_emulator.engine.capture.catalog_match import normalize_text
from store_emulator.engine.capture.detect import image_data_url


class VisionLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
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

    @field_validator("signage", "entrance", "window", "upkeep", "overall", mode="before")
    @classmethod
    def _numeric_ratings(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Storefront ratings must be numbers from 0 to 10, not true or false.")
        return value

    @field_validator("reasons", mode="before")
    @classmethod
    def _optional_reason(cls, value: object) -> object:
        return "" if value is None else value


STOREFRONT_PROMPT = """You judge shop fronts the way passers-by do. Rate this storefront photo from 0 to 10 on:
signage (a visible, legible shop sign), entrance (open, inviting, step-free), window (products or a lit interior
visible from outside), upkeep (bright, clean, well kept), and overall: how likely a passer-by is to walk in.
5 is an ordinary shop front. Use numeric ratings, never true or false.
Give a short reason; use an empty string instead of null when no explanation is given."""


async def vlm_appeal(llm: VisionLLM, img: Image.Image, *, model: str = "vlm") -> StorefrontAppeal:
    url, _ = image_data_url(ImageOps.exif_transpose(img).convert("RGB"), max_side=1024, fmt="JPEG")
    r = await llm.generate_structured_with_image_async(_StorefrontRating, STOREFRONT_PROMPT, "Rate this storefront.", url, max_retries=1, seed=0)
    return StorefrontAppeal(
        method="vlm", model=model, signage=r.signage, entrance=r.entrance, window=r.window, upkeep=r.upkeep,
        overall=r.overall, attractiveness=attractiveness_for(r.overall), reasons=r.reasons.strip(),
    )


def _receipt_observations(schema: dict[str, JsonValue]) -> None:
    fields = schema.get("properties")
    assert isinstance(fields, dict)
    required: list[JsonValue] = list(fields)
    schema["required"] = required
    for field in fields.values():
        if isinstance(field, dict):
            field.pop("default", None)


class _ReceiptLineVLM(BaseModel):
    # Require explicit observations on the wire while keeping old partial
    # transcriptions readable. Null amounts still represent unreadable prices.
    model_config = ConfigDict(json_schema_extra=_receipt_observations)

    name: str = Field(max_length=80, description="The purchased product's printed name, e.g. the ITEM column; empty only if unreadable")
    quantity: float = Field(default=1.0, allow_inf_nan=False, description="The purchased count or weight, e.g. QTY; not an amount of money")
    unit_price: float | None = Field(default=None, allow_inf_nan=False, description="Printed price of one unit, e.g. UNIT; null if absent")
    line_total: float | None = Field(default=None, allow_inf_nan=False, description="Printed amount for this product row, e.g. AMOUNT; null if absent")

    @field_validator("quantity", "unit_price", "line_total", mode="before")
    @classmethod
    def _numeric_line(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Receipt quantities and amounts must be numbers, not true or false.")
        return value


class _ReceiptVLM(BaseModel):
    model_config = ConfigDict(json_schema_extra=_receipt_observations)

    store: str = Field(default="", max_length=80)
    date: str = Field(default="", description="YYYY-MM-DD as printed, or empty")
    time: str = Field(default="", description="HH:MM as printed, or empty")
    currency: str = Field(default="", description="ISO 4217 code if you can tell, e.g. USD, KRW")
    product_row_count: int | None = Field(default=None, ge=0, description="Count of actual purchased or returned product rows, excluding subtotal, tax, payment and change rows; zero when no products")
    lines: list[_ReceiptLineVLM] = Field(default_factory=list[_ReceiptLineVLM], description="Every purchased product row, excluding subtotal, tax and payment rows")
    total_row: str = Field(default="", max_length=160, description="The complete printed row supplying the final total, preserving its label; empty if absent")
    total: float | None = Field(default=None, allow_inf_nan=False)

    @field_validator("product_row_count", mode="before")
    @classmethod
    def _numeric_product_count(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("The product row count must be an integer, not true or false.")
        return value

    @model_validator(mode="after")
    def _complete_product_rows(self) -> Self:
        if self.product_row_count is not None and self.product_row_count != len(self.lines):
            raise ValueError(f"The receipt declares {self.product_row_count} product rows but returns {len(self.lines)}. "
                             "Include each printed product once; exclude footer rows and empty padding.")
        return self

    @field_validator("total", mode="before")
    @classmethod
    def _numeric_total(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Receipt total must be a number or null when unreadable, not true or false.")
        return value

    @field_validator("store", "date", "time", "currency", "total_row", mode="before")
    @classmethod
    def _unknown_metadata(cls, value: object) -> object:
        return "" if value is None else value


RECEIPT_PROMPT = """You transcribe shop receipts. List every purchased product line with its name as printed, quantity,
unit price and line total (numbers as printed, no currency symbols). Skip subtotals, tax, payment and change lines.
Give the store name, date (YYYY-MM-DD), time (HH:MM), currency code and the receipt total when printed.
Return JSON with store, date, time, currency, lines and total. Each object in lines must copy the product text
into name, the purchased count/weight (QTY) into quantity, the single-unit price (UNIT) into unit_price,
and that product row's amount (AMOUNT) into line_total. Read the printed date and time into date and time.
Do not leave readable product names, dates or times empty. For total, copy the final TOTAL including tax,
not SUBTOTAL, CASH or CHANGE. Do not recalculate it from the product lines; use null if no total is printed.
Date and time are independent observations: a date without a printed clock time requires time="".
Never infer an hour from a date. A SUBTOTAL row alone is not a TOTAL row: without a separate final TOTAL,
set total=null. A printed TOTAL of 0 or 0.00 is total=0, including cancelled transactions with lines=[].
Keep every purchased line even when its name is unreadable: use an empty name and retain its readable quantity and amounts
so the product can be chosen during review. Never omit a purchased line just because its name is unreadable.
For unreadable store, date, time or currency text use an empty string, not null. Do not invent missing text.
Use finite numbers only, never true or false. For unreadable or missing amounts use null, never NaN or Infinity.
Copy only the printed amount; do not repeat digits. Amounts must fit within 9007199254740991 minor units
(cents for USD, whole won for KRW, whole yen for JPY).
Before total, fill total_row by copying its complete printed row, including the label and amount exactly as written.
Do not rename a SUBTOTAL row to TOTAL. When no final total row is printed, set total_row="" and total=null.
Include returned or refunded product rows for review. Preserve every printed minus sign in quantity and amounts; a returned quantity -1 must remain -1 and a row amount -2.50 must remain -2.50. Never turn a negative number into its positive absolute value.
Column mapping: QTY / 수량 -> quantity; UNIT / 단가 -> unit_price; AMOUNT / 금액 -> line_total. These numbers are separate observations. Never calculate line_total from quantity or another amount. Copy the amount printed in its own column even when the arithmetic appears inconsistent.
Before lines, set product_row_count to the number of actual purchased or returned product rows. Include exactly that many lines, once per printed product row, and then close the array. Do not count or emit subtotal, tax, total, cash or change rows as products. An unreadable product name is not a blank placeholder or a footer row. Never pad lines with empty or zero-filled objects."""

_ZERO_DECIMAL = {"KRW", "JPY", "VND", "IDR", "CLP", "ISK", "HUF", "TWD"}
_SUBTOTAL_ROW = re.compile(r"^(?:sub\s*total|sous\s*total|소계(?:\s*금액)?|小[計计])(?=\s|\d|$)")


def _minor(v: float | None, currency: str) -> int | None:
    if v is None:
        return None
    scaled = v if currency.upper() in _ZERO_DECIMAL else v * 100
    if not -MAX_RECEIPT_AMOUNT <= scaled <= MAX_RECEIPT_AMOUNT:
        raise ValueError(f"Receipt amount is outside the supported range in {currency} minor units; "
                         "copy the printed amount or use null when it cannot be read.")
    return round(scaled)


async def vlm_receipt(llm: VisionLLM, img: Image.Image, *, receipt_id: str, default_currency: str = "USD") -> ReceiptReading:
    url, _ = image_data_url(ImageOps.exif_transpose(img).convert("RGB"), max_side=1600, fmt="JPEG")

    # The default currency belongs to this request, not a shared model class.
    class ReceiptResponse(_ReceiptVLM):
        @model_validator(mode="after")
        def representable_amounts(self) -> Self:
            currency = (self.currency.strip() or default_currency.strip()).upper()
            _minor(self.total, currency)
            for line in self.lines:
                _minor(line.unit_price, currency)
                _minor(line.line_total, currency)
            return self

    user = f"Transcribe this receipt. If no currency is readable, leave it empty; the store uses {default_currency.strip().upper()}."
    # Every line has quantities and prices; the shared storefront-rating cap
    # truncates ordinary long receipts before the complete list can be read.
    r = await llm.generate_structured_with_image_async(
        ReceiptResponse, RECEIPT_PROMPT, user, url, max_retries=2, seed=0, max_tokens=6144)
    currency = (r.currency.strip() or default_currency.strip()).upper()
    lines = [ReceiptLine(name=line.name.strip(), quantity=line.quantity, unit_price=_minor(line.unit_price, currency),
                         line_total=_minor(line.line_total, currency))
             for line in r.lines]
    stamp = f"{r.date} {r.time}".strip() if r.date else ""
    subtotal = _SUBTOTAL_ROW.match(normalize_text(r.total_row)) is not None
    return ReceiptReading(receipt_id=receipt_id, store=r.store.strip(), timestamp=stamp, currency=currency, lines=lines,
                          total=None if subtotal else _minor(r.total, currency),
                          notes=[r.total_row.strip()] if subtotal else [])


def match_lines(reading: ReceiptReading, products: dict[str, str]) -> ReceiptReading:
    """Match complete normalized names to a unique SKU; other names require review before assigning sales."""
    names: dict[str, set[str]] = {}
    for sku, name in products.items():
        key = normalize_text(name)
        if key:
            names.setdefault(key, set()).add(sku)
    out: list[ReceiptLine] = []
    for line in reading.lines:
        key = normalize_text(line.name)
        candidates = names.get(key, set())
        sku = next(iter(candidates)) if len(candidates) == 1 else ""
        out.append(line.model_copy(update={"sku": sku, "matched": bool(sku)}))
    return reading.model_copy(update={"lines": out})


def receipts_csv(readings: list[ReceiptReading]) -> str:
    """POS-export CSV of matched lines (columns the fidelity report understands)."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["receipt_id", "sku", "quantity", "unit_price", "line_total", "timestamp"])
    for r in readings:
        for line in r.lines:
            if not line.matched:
                continue
            # POS scoring consumes unit_price. Preserve actual paid amounts after discounts,
            # and receipts that show a line total without a unit price.
            unit = (line.line_total / line.quantity if line.line_total is not None and line.quantity > 0
                    else line.unit_price)
            total = "" if line.line_total is None else str(line.line_total)
            writer.writerow([r.receipt_id, line.sku, line.quantity, unit, total, r.timestamp])
    return output.getvalue()
