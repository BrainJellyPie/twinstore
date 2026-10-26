"""Group identical neighbouring facings and read each product once with a vision-language model.

Facings of one product stand side by side, so neighbours are compared with a colour histogram
(hue × saturation, plus grey levels) and a small grey-level thumbnail; a run of matching
neighbours is one product with that many facings. The model then sees one crop per product —
the package taken from the full-resolution photo plus the price-tag strip under it.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from pydantic import JsonValue, model_validator

from store_emulator.domain.capture import ShelfItemLabel

from .bands import Band
from .detect import Detection, ImageLLM, image_data_url
from .frame import FloatArray, WorkFrame

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Descriptor:
    hist: FloatArray        # L1-normalised colour histogram
    thumb: FloatArray       # zero-mean, unit-norm grey thumbnail (flattened)
    width: float


@dataclass
class FacingGroup:
    band: int
    facings: list[Detection]
    descriptor: Descriptor
    label: ShelfItemLabel | None = None
    error: str = ""
    crops: list[str] = field(default_factory=list[str])

    @property
    def x1(self) -> float:
        return min(f.x1 for f in self.facings)

    @property
    def x2(self) -> float:
        return max(f.x2 for f in self.facings)

    @property
    def representative(self) -> Detection:
        return self.facings[len(self.facings) // 2]


def describe(image: Image.Image, det: Detection) -> Descriptor:
    w, h = det.width, det.height
    box = (round(det.x1 + 0.15 * w), round(det.y1 + 0.15 * h), round(det.x2 - 0.15 * w), round(det.y2 - 0.15 * h))
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        box = (round(det.x1), round(det.y1), max(round(det.x1) + 2, round(det.x2)), max(round(det.y1) + 2, round(det.y2)))
    crop = image.crop(box)
    hsv = np.asarray(crop.convert("HSV"), dtype=np.float32).reshape(-1, 3)
    hue, sat, val = hsv[:, 0] / 256.0, hsv[:, 1] / 255.0, hsv[:, 2] / 255.0
    colored = sat >= 0.25
    hue_bin = np.minimum((hue * 12).astype(np.int64), 11)
    sat_bin = (sat >= 0.6).astype(np.int64)
    color_idx = hue_bin * 2 + sat_bin
    gray_idx = 24 + np.minimum((val * 4).astype(np.int64), 3)
    idx = np.where(colored, color_idx, gray_idx)
    hist = np.bincount(idx, minlength=28).astype(np.float32)
    hist /= max(1.0, float(hist.sum()))
    thumb = np.asarray(crop.convert("L").resize((16, 24), Image.Resampling.BILINEAR), dtype=np.float32).ravel()
    thumb = thumb - thumb.mean()
    norm = float(np.linalg.norm(thumb))
    thumb = thumb / norm if norm > 1e-6 else thumb
    return Descriptor(hist=hist, thumb=thumb, width=det.width)


def similar(a: Descriptor, b: Descriptor, *, hist_min: float = 0.75, corr_min: float = 0.75) -> bool:
    """Same product? Thresholds set on a held-out synthetic split (identical facings: histogram
    intersection ≥ 0.88 and thumbnail correlation ≥ 0.96 for 99% of pairs; different neighbours pass
    both 0.75 cut-offs ~1.5% of the time)."""
    inter = float(np.minimum(a.hist, b.hist).sum())
    corr = float(np.dot(a.thumb, b.thumb))
    ratio = min(a.width, b.width) / max(a.width, b.width, 1e-6)
    return inter >= hist_min and corr >= corr_min and ratio >= 0.6


def group_facings(frame: WorkFrame, facings: list[Detection], gaps: list[Detection]) -> list[FacingGroup]:
    """Runs of identical adjacent facings per band (a gap between two facings breaks the run)."""
    groups: list[FacingGroup] = []
    by_band: dict[int, list[Detection]] = {}
    for d in facings:
        by_band.setdefault(d.band, []).append(d)
    for band, dets in sorted(by_band.items()):
        dets.sort(key=lambda d: d.x1)
        typical = float(np.median([d.width for d in dets]))
        band_gaps = [g for g in gaps if g.band == band]
        current: FacingGroup | None = None
        for d in dets:
            desc = describe(frame.image, d)
            if current is not None:
                prev = current.facings[-1]
                gap_between = any(prev.cx < g.cx < d.cx for g in band_gaps)
                far = d.x1 - prev.x2 > 0.5 * typical
                if not gap_between and not far and similar(current.descriptor, desc):
                    current.facings.append(d)
                    continue
            current = FacingGroup(band=band, facings=[d], descriptor=desc)
            groups.append(current)
    return groups


def label_image(photo: Image.Image, frame: WorkFrame, band: Band, group: FacingGroup, *, max_side: int = 512) -> Image.Image:
    """Package crop (full resolution) above the price-tag strip under it, as one image."""
    rep = group.representative
    pad = 0.04 * rep.width
    pkg = frame.to_image_box(rep.x1 - pad, rep.y1 - pad, rep.x2 + pad, rep.y2)
    product = photo.crop((round(pkg.x1), round(pkg.y1), round(pkg.x2), round(pkg.y2)))
    if not product.width or not product.height:
        raise ValueError("No visible product remains inside the photo.")
    # The tag sits on the shelf edge under the run of facings — centred under a facing or at the
    # run's left end — so the strip under the first facing (a little wider) covers both habits.
    first = group.facings[0]
    left = first.x1 - 0.15 * first.width
    right = first.x2 + 0.15 * first.width
    y_top = min(band.bottom_at(left), band.bottom_at(right))
    tag = frame.to_image_box(left, y_top, right, y_top + 0.36 * band.height)
    strip = photo.crop((round(tag.x1), round(tag.y1), round(tag.x2), round(tag.y2)))
    width = 448
    prod_h = max(1, round(product.height * width / max(1, product.width)))
    prod_h = min(prod_h, 384)
    product = product.resize((max(1, round(product.width * prod_h / max(1, product.height))), prod_h),
                             Image.Resampling.LANCZOS)
    if strip.width and strip.height:
        strip_h = max(1, round(strip.height * width / strip.width))
        strip = strip.resize((width, min(strip_h, 160)), Image.Resampling.LANCZOS)
    else:
        # A visible package may have its price tag beyond the photo's edge.
        strip = Image.new("RGB", (width, 1), (255, 255, 255))
    canvas = Image.new("RGB", (width, product.height + 8 + strip.height), (255, 255, 255))
    canvas.paste(product, ((width - product.width) // 2, 0))
    canvas.paste(strip, (0, product.height + 8))
    s = min(1.0, max_side / max(canvas.size))
    if s < 1.0:
        canvas = canvas.resize((round(canvas.width * s), round(canvas.height * s)), Image.Resampling.LANCZOS)
    return canvas


# No concrete size examples in the prompt: sub-1B models copied them ("500ml") into a third of the
# answers whose package showed no size (prompt ablation).
LABEL_SYSTEM_PROMPT = "You read products on store shelves. Answer with JSON only."
LABEL_PROMPT = (
    "Top: one product package on a store shelf. Bottom: the shelf edge under it with its price tag.\n"
    "Read the product. name: product name as printed, with flavour or variant, without the brand. "
    "brand: brand or \"\". size: the volume, weight or pack count only if it is printed on the package, "
    "otherwise \"\". "
    "category: what kind of product it is in one or two words, for example soft drink, "
    "water, coffee drink, milk, beer, chips, chocolate, candy, instant noodles, sandwich, bread, ice cream, "
    "shampoo, detergent. price_text: the text on the price tag in the bottom strip, exactly as printed, "
    "or \"\". Preserve discount words such as SAVE, OFF and 할인 in price_text. "
    "price: the current selling price as a number, or null if no selling price is shown. "
    "A savings amount, coupon value or amount off is not the selling price; use null for those. "
    "A rate per weight or volume (such as /kg, /L or 리터당) is not the package price; "
    "preserve that rate wording in price_text and use null for price. "
    "confidence: 0-10 for how sure you are of the name.\n"
    "For any unreadable text field, use an empty string, not null. Do not invent missing text.\n"
    "Copy any printed currency symbol or code unchanged, even if it differs from the store currency. "
    "Do not convert the amount.\n"
    "Prices in this store are in {currency}. Keep names in the language printed on the package."
)

_CURRENCY_HINT = {"USD": "US dollars ($)", "KRW": "Korean won (원)", "JPY": "Japanese yen (¥)", "EUR": "euros (€)"}


class _ShelfLabelResponse(ShelfItemLabel):
    @model_validator(mode="before")
    @classmethod
    def read_wrapped_values(cls, value: JsonValue) -> JsonValue:
        # JSON-mode models sometimes put observed values under the schema's
        # properties key. Retain flat fields when present; never guess values
        # from actual field definitions (the inherited validators reject those).
        if isinstance(value, dict) and "properties" in value and not any(key in value for key in cls.model_fields):
            fields = value["properties"]
            if not isinstance(fields, dict) or not any(key in fields for key in cls.model_fields):
                raise ValueError("Return observed product field values, not schema definitions.")
            return fields
        return value


class VLMLabeler:
    """One structured VLM call per product group; failures leave the group unlabeled."""

    def __init__(self, llm: ImageLLM, *, currency: str, concurrency: int = 2, max_side: int = 512) -> None:
        self.llm = llm
        self.currency = currency.upper()
        self.semaphore = asyncio.Semaphore(concurrency)
        self.max_side = max_side
        self.calls = 0

    async def label(self, image: Image.Image) -> ShelfItemLabel:
        url, _ = image_data_url(image, max_side=self.max_side)
        prompt = LABEL_PROMPT.format(currency=_CURRENCY_HINT.get(self.currency, self.currency))
        async with self.semaphore:
            self.calls += 1
            return await self.llm.generate_structured_with_image_async(
                _ShelfLabelResponse, LABEL_SYSTEM_PROMPT, prompt, url, max_retries=1, seed=0,
            )

    async def label_groups(
        self, photo: Image.Image, frame: WorkFrame, bands: list[Band], groups: list[FacingGroup],
        on_done: Callable[[int, int], None] | None = None,
    ) -> None:
        done = 0

        async def one(group: FacingGroup) -> None:
            nonlocal done
            try:
                group.label = await self.label(label_image(photo, frame, bands[group.band], group))
            except Exception as e:  # noqa: BLE001 — one unreadable product must not fail the capture
                group.error = f"{type(e).__name__}: {e}"[:200]
                logger.warning(f"[capture] labeling failed: {group.error}")
            done += 1
            if on_done is not None:
                on_done(done, len(groups))

        await asyncio.gather(*(one(g) for g in groups))
