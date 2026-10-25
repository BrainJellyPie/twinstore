"""Shelf photo → CaptureResult: deskew, shelf bands, facings and gaps, product groups, labels, planogram."""

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from store_emulator.domain.capture import (
    Box,
    CaptureGap,
    CaptureItem,
    CaptureRackType,
    CaptureResult,
    ShelfBand,
)

from .bands import Band, band_levels, deskewed_frame, detect_bands
from .catalog_match import match_category, normalize_text, price_minor_units, typical_price
from .detect import (
    Detection,
    FacingDetector,
    VLMGroundingDetector,
    classic_detect,
    fill_uncovered,
)
from .frame import WorkFrame
from .planogram import sku_for
from .recognize import FacingGroup, VLMLabeler, group_facings

type StageCallback = Callable[[str, float], None]


@dataclass
class CaptureRun:
    """Result plus the intermediate state (work frame, bands, raw detections, groups) for debugging."""
    result: CaptureResult
    frame: WorkFrame
    bands: list[Band]
    detections: list[Detection]
    groups: list[FacingGroup] = field(default_factory=list[FacingGroup])


def _band_model(frame: WorkFrame, band: Band, level: int) -> ShelfBand:
    w = frame.size[0]
    poly = frame.to_image_points([
        (0.0, band.top_at(0.0)), (float(w), band.top_at(float(w))),
        (float(w), band.bottom_at(float(w))), (0.0, band.bottom_at(0.0)),
    ])
    mid = frame.to_image_points([(w / 2, band.top_at(w / 2)), (w / 2, band.bottom_at(w / 2))])
    return ShelfBand(index=band.index, level=level, top=round(mid[0][1], 1), bottom=round(mid[1][1], 1),
                     polygon=[(round(x, 1), round(y, 1)) for x, y in poly])


def _image_box(frame: WorkFrame, d: Detection) -> Box:
    b = frame.to_image_box(d.x1, d.y1, d.x2, d.y2)
    return Box(x1=round(b.x1, 1), y1=round(b.y1, 1), x2=round(b.x2, 1), y2=round(b.y2, 1))


def build_items(
    frame: WorkFrame, groups: list[FacingGroup], levels: list[int], *, currency: str, rack_type: CaptureRackType,
    salt: str = "",
) -> tuple[list[CaptureItem], str]:
    """Groups (+ labels) → planogram items, and the shelf's dominant catalog category."""
    items: list[CaptureItem] = []
    order_in_band: dict[int, int] = {}
    for g in sorted(groups, key=lambda g: (g.band, g.x1)):
        order = order_in_band.get(g.band, 0)
        order_in_band[g.band] = order + 1
        level = levels[g.band] if 0 <= g.band < len(levels) else 1
        boxes = [_image_box(frame, f) for f in g.facings]
        item = CaptureItem(id=f"i{len(items) + 1:02d}", band=g.band, level=level, order=order,
                           facings=len(g.facings), boxes=boxes)
        label = g.label
        name = (label.name.strip() or label.brand.strip()) if label is not None else ""
        if label is not None and name:
            category = match_category(label.category, f"{label.brand} {name}", rack_type=rack_type)
            typical, _ = typical_price(category, name, currency)
            price = price_minor_units(label, currency, typical)
            sku = sku_for(name, label.brand, label.size)
            if not normalize_text(f"{label.brand} {name}"):
                # Punctuation and a pack size cannot identify a product across photos.
                key = f"{salt}|{g.band}|{order}"
                sku = "cap_u" + hashlib.sha1(key.encode()).hexdigest()[:9]
            item = item.model_copy(update={
                "name": name, "brand": label.brand.strip(), "size": label.size.strip(), "category": category,
                "raw_category": label.category.strip(), "price": price if price is not None else typical,
                "price_estimated": price is None, "price_text": label.price_text.strip(),
                "confidence": label.confidence, "labeled": True,
                "sku": sku,
            })
        items.append(item)
    weights: dict[str, int] = {}
    for it in items:
        if it.labeled and it.category:
            weights[it.category] = weights.get(it.category, 0) + it.facings
    dominant = max(weights, key=lambda c: weights[c]) if weights else ""
    out: list[CaptureItem] = []
    for it in items:
        if it.labeled:
            out.append(it)
            continue
        typical, _ = typical_price(dominant, "", currency) if dominant else (None, "")
        key = f"{salt}|{it.band}|{it.order}"
        out.append(it.model_copy(update={
            "name": f"Product {it.band + 1}.{it.order + 1}", "category": dominant, "price": typical,
            "price_estimated": True, "sku": "cap_u" + hashlib.sha1(key.encode()).hexdigest()[:9],
        }))
    return out, dominant


class CaptureModelFailed(RuntimeError):
    """Every product the model was asked to read failed with an error."""


async def capture_shelf(
    photo: Image.Image, *, detector: FacingDetector, labeler: VLMLabeler | None = None,
    currency: str = "USD", rack_type: CaptureRackType = "shelf", model: str = "", salt: str = "",
    on_stage: StageCallback | None = None,
) -> CaptureRun:
    def stage(name: str, progress: float) -> None:
        if on_stage is not None:
            on_stage(name, progress)

    timings: dict[str, float] = {}
    notes: list[str] = []
    t0 = time.perf_counter()
    stage("detecting", 0.05)
    frame = deskewed_frame(photo)
    bands = detect_bands(frame)
    timings["bands_sec"] = round(time.perf_counter() - t0, 3)
    t1 = time.perf_counter()
    detections, bands = await detector.detect(frame, bands)
    used = detector.name
    facing_bands = {d.band for d in detections if d.kind == "facing"}
    if detector.name != "classic":
        missing = [b for b in bands if b.index not in facing_bands]
        if missing and len(missing) == len(bands):
            notes.append(f"{detector.name} found no products; used the classic detector")
            used = "classic"
            detections = classic_detect(frame, bands)
        else:
            if missing:
                notes.append(f"{len(missing)} shelf level(s) had no {detector.name} detections; filled by the classic detector")
                detections = detections + classic_detect(frame, missing)
            # Stretches no box covers: missed facings or out-of-stock gaps.
            detections = detections + fill_uncovered(frame, bands, [d for d in detections if d.kind == "facing"])
    timings["detect_sec"] = round(time.perf_counter() - t1, 3)
    facings = [d for d in detections if d.kind == "facing"]
    gaps = [d for d in detections if d.kind == "gap"]
    sources: dict[str, int] = {}
    for d in facings:
        sources[d.source] = sources.get(d.source, 0) + 1
    stage("grouping", 0.3)
    groups = group_facings(frame, facings, gaps)
    levels = band_levels(len(bands))
    t2 = time.perf_counter()
    if labeler is not None and groups:
        def on_done(done: int, total: int) -> None:
            stage("reading", 0.35 + 0.55 * done / max(1, total))

        stage("reading", 0.35)
        await labeler.label_groups(photo, frame, bands, groups, on_done)
        failed = sum(1 for g in groups if g.label is None)
        errors = [g.error for g in groups if g.error]
        if failed == len(groups) and len(errors) == len(groups):
            # Not one product read, every call an error (a model that is not there, a key turned down): a planogram
            # of "Product 1.1, 1.2, …" at typical prices would look like a result.
            raise CaptureModelFailed(errors[0])
        if failed:
            notes.append(f"{failed} of {len(groups)} products could not be read by the model")
    timings["recognize_sec"] = round(time.perf_counter() - t2, 3)
    stage("planogram", 0.95)
    items, dominant = build_items(frame, groups, levels, currency=currency, rack_type=rack_type, salt=salt)
    typical_w = float(np.median([f.width for f in facings])) if facings else 1.0
    capture_gaps = [
        CaptureGap(band=g.band, level=levels[g.band] if 0 <= g.band < len(levels) else 1,
                   box=_image_box(frame, g), facings=round(g.width / max(1.0, typical_w), 2))
        for g in gaps
    ]
    if len(bands) > 4:
        notes.append(f"{len(bands)} shelves detected; merged into the rack's 4 levels by height")
    timings["total_sec"] = round(time.perf_counter() - t0, 3)
    result = CaptureResult(
        image_size=photo.size, tilt_deg=round(frame.angle, 2), detector=used, model=model if labeler else "",
        currency=currency.upper(), rack_type=rack_type,
        bands=[_band_model(frame, b, levels[b.index]) for b in bands],
        items=items, gaps=capture_gaps, dominant_category=dominant, notes=notes, timings=timings,
        detection_sources=sources,
        vlm_calls=(labeler.calls if labeler is not None else 0)
        + (detector.calls if isinstance(detector, VLMGroundingDetector) else 0),
    )
    return CaptureRun(result=result, frame=frame, bands=bands, detections=detections, groups=groups)
