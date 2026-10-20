"""Product facings (and empty gaps) on detected shelf bands.

Three interchangeable detectors share one post-processing path:

- `ClassicDetector`: no model. Each band is rectified into a strip (perspective-normalised rows),
  facings are split at long vertical edges and colour changes, and low-texture segments are gaps.
- `GroundingDinoDetector`: zero-shot open-vocabulary detector (HF `IDEA-Research/grounding-dino-tiny`,
  optional dependency group `capture`), CPU.
- `VLMGroundingDetector`: asks a vision-language model for boxes as JSON (Qwen-VL, Gemini …).

Model detections are de-duplicated (NMS, container boxes) and assigned to a band (boxes spanning two
shelves are dropped). The pipeline then re-examines uncovered stretches of each band with the classic
segmenter (`fill_uncovered`), which both recovers missed facings and reports out-of-stock gaps.
"""

import asyncio
import base64
import gc
import importlib
import importlib.util
import io
import itertools
import logging
import math
import types
from dataclasses import dataclass, replace
from typing import Literal, Protocol

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from .bands import Band, Line, assign_band, long_runs
from .frame import FloatArray, WorkFrame, rgb_array, sobel

logger = logging.getLogger(__name__)

type DetectionKind = Literal["facing", "gap"]

GDINO_MODEL_ID = "IDEA-Research/grounding-dino-tiny"
# One generic class scores higher than a list of package types (the per-class logits split the mass).
GDINO_PROMPT = "product."


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    score: float = 1.0
    source: str = "classic"
    band: int = -1
    kind: DetectionKind = "facing"

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2


class FacingDetector(Protocol):
    """Facings (and gaps) on a work frame. Returns the detections and the shelf bands they refer to:
    a model detector may replace line-based bands its boxes contradict (see `refine_detections`)."""
    name: str

    async def detect(self, frame: WorkFrame, bands: list[Band]) -> tuple[list[Detection], list[Band]]: ...


class ImageLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...


def iou(a: Detection, b: Detection) -> float:
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union > 0 else 0.0


def nms(dets: list[Detection], threshold: float = 0.5) -> list[Detection]:
    kept: list[Detection] = []
    for d in sorted(dets, key=lambda d: -d.score):
        if all(iou(d, k) < threshold for k in kept):
            kept.append(d)
    return kept


# ── band strips ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BandStrip:
    """A band resampled to a fixed number of rows per column (rows follow the slanted shelf lines)."""
    band: Band
    gray: FloatArray            # (n, W)
    rgb: FloatArray             # (n, W, 3)
    gx: FloatArray
    gy: FloatArray
    sat: FloatArray             # (n, W) HSV saturation 0–1

    @property
    def rows(self) -> int:
        return self.gray.shape[0]


def band_strip(frame: WorkFrame, band: Band, rgb: FloatArray) -> BandStrip:
    w, h = frame.size
    xs = np.arange(w)
    tops = band.top.y0 + band.top.slope * (xs - band.top.cx)
    bottoms = band.bottom.y0 + band.bottom.slope * (xs - band.bottom.cx)
    n = max(16, round(band.height))
    t = (np.arange(n, dtype=np.float64) + 0.5) / n
    ys = np.clip(np.rint(tops[None, :] + t[:, None] * (bottoms - tops)[None, :]), 0, h - 1).astype(np.int64)
    gray = frame.gray[ys, xs[None, :]]
    colors = rgb[ys, xs[None, :]]
    gx, gy = sobel(gray)
    mx = colors.max(axis=2)
    mn = colors.min(axis=2)
    sat = np.where(mx > 1.0, (mx - mn) / np.maximum(mx, 1.0), 0.0).astype(np.float32)
    return BandStrip(band=band, gray=gray, rgb=colors, gx=gx, gy=gy, sat=sat)


@dataclass(frozen=True)
class SegmentStats:
    texture: float          # mean gradient magnitude
    saturation: float
    luminance: float
    print_density: float    # share of strong edges (print, outlines); sensor noise stays near 0


def segment_stats(strip: BandStrip, xa: float, xb: float) -> SegmentStats:
    """Texture / saturation / luminance of the central part of [xa, xb] (avoids neighbours' edges)."""
    w = strip.gray.shape[1]
    span = xb - xa
    a = int(max(0, min(w - 1, xa + 0.15 * span)))
    b = int(max(a + 1, min(w, xb - 0.15 * span)))
    n = strip.rows
    r0, r1 = int(0.15 * n), max(int(0.15 * n) + 1, int(0.85 * n))
    grad = strip.gx[r0:r1, a:b] + strip.gy[r0:r1, a:b]
    return SegmentStats(
        texture=float(grad.mean()) if grad.size else 0.0,
        saturation=float(strip.sat[r0:r1, a:b].mean()) if grad.size else 0.0,
        luminance=float(strip.gray[r0:r1, a:b].mean()) if grad.size else 0.0,
        print_density=float((grad > 60.0).mean()) if grad.size else 0.0,
    )


def _median_stats(stats: list[SegmentStats]) -> SegmentStats:
    return SegmentStats(
        texture=float(np.median([s.texture for s in stats])),
        saturation=float(np.median([s.saturation for s in stats])),
        luminance=float(np.median([s.luminance for s in stats])),
        print_density=float(np.median([s.print_density for s in stats])),
    )


def boundary_score(strip: BandStrip) -> FloatArray:
    """Per-column evidence of a product boundary: long vertical edges plus a colour change."""
    n = strip.rows
    r0, r1 = int(0.1 * n), max(int(0.1 * n) + 2, int(0.9 * n))
    gx, gy = strip.gx[r0:r1], strip.gy[r0:r1]
    tv = max(24.0, float(np.percentile(gx, 75)))
    vertical = (gx > tv) & (gx > 1.2 * gy)
    # Product sides run most of the band height; letters and graphics do not.
    long_vertical = long_runs(vertical.T.copy(), max(4, round(0.25 * (r1 - r0)))).T
    cover = long_vertical.mean(axis=0).astype(np.float32)
    cover = np.maximum(cover, np.maximum(np.roll(cover, 1), np.roll(cover, -1)))
    colors: FloatArray = strip.rgb[r0:r1].mean(axis=0).astype(np.float32)  # (W, 3)
    k = max(3, round(0.06 * n))
    cum = np.concatenate([np.zeros((1, 3), dtype=np.float64), np.cumsum(colors, axis=0, dtype=np.float64)])
    w = int(colors.shape[0])
    xs = np.arange(w, dtype=np.int64)
    lo = np.clip(xs - k, 0, w)
    hi = np.clip(xs + k, 0, w)
    left = (cum[xs] - cum[lo]) / np.maximum(1, xs - lo)[:, None]
    right = (cum[hi] - cum[xs]) / np.maximum(1, hi - xs)[:, None]
    change = np.linalg.norm(left - right, axis=1)
    scale = float(np.percentile(change, 95)) or 1.0
    change_n = np.clip(change / scale, 0.0, 1.5).astype(np.float32)
    return (cover + 0.5 * change_n).astype(np.float32)


def _peaks(score: FloatArray, threshold: float, min_dist: float) -> list[int]:
    w = score.shape[0]
    cand = [x for x in range(1, w - 1) if score[x] >= threshold and score[x] >= score[x - 1] and score[x] >= score[x + 1]]
    kept: list[int] = []
    for x in sorted(cand, key=lambda x: -float(score[x])):
        if all(abs(x - k) >= min_dist for k in kept):
            kept.append(x)
    return sorted(kept)


def segment_band(
    strip: BandStrip, xa: float, xb: float, *, min_width: float,
) -> list[tuple[float, float]]:
    """Split [xa, xb] of a band into facing-sized segments at boundary peaks."""
    score = boundary_score(strip)
    w = score.shape[0]
    a, b = max(0, int(xa)), min(w, math.ceil(xb))
    if b - a < min_width:
        return []
    local = score.copy()
    local[:a] = 0
    local[b:] = 0
    edges = _peaks(local, 0.35, max(4.0, 0.8 * min_width))
    weak = _peaks(local, 0.3, 3.0)
    cuts = sorted({a, *[e for e in edges if a < e < b], b})
    segments: list[tuple[float, float]] = []
    for s, e in itertools.pairwise(cuts):
        if e - s < 0.5 * min_width:
            continue
        # Pull each end in to the segment's own outline when a second edge sits just inside it
        # (two packages side by side show two outlines with a strip of shelf back between them).
        inner = [x for x in weak if s < x < e]
        span = e - s
        head = [x for x in inner if x - s <= 0.2 * span]
        tail = [x for x in inner if e - x <= 0.2 * span]
        s2 = max(head) if head else s
        e2 = min(tail) if tail else e
        if e2 - s2 >= 0.5 * min_width:
            segments.append((float(s2), float(e2)))
        else:
            segments.append((float(s), float(e)))
    return segments


def weighted_median(widths: list[float]) -> float:
    """Width-weighted median: the segment width that covers the middle of the shelf length, so a
    crowd of narrow slivers cannot drag the "typical facing width" down."""
    ordered = sorted(widths)
    half = sum(ordered) / 2
    acc = 0.0
    for w in ordered:
        acc += w
        if acc >= half:
            return w
    return ordered[-1] if ordered else 0.0


def _box_for(band: Band, xa: float, xb: float) -> tuple[float, float, float, float]:
    top = min(band.top_at(xa), band.top_at(xb))
    bottom = max(band.bottom_at(xa), band.bottom_at(xb))
    return xa, top, xb, bottom


def _is_gap(stats: SegmentStats, ref: SegmentStats) -> bool:
    """Empty shelf: no print and little texture (the back panel shows through). Packages always carry
    print; plain stretches outside the stocked extent (walls, rack ends) are dropped by the caller."""
    return stats.print_density < 0.3 * ref.print_density and stats.texture < 0.5 * ref.texture


def classify_segments(
    strips: dict[int, BandStrip], segments: dict[int, list[tuple[float, float]]], *, source: str,
    ref: SegmentStats | None = None, extent: tuple[float, float] | None = None,
) -> list[Detection]:
    """Segments → facings / gaps. Gaps must lie inside the rack's horizontal extent.

    Slivers (the strip of shelf back between two packages, a rack upright) are dropped first:
    anything narrower than 45% of the typical segment width.
    """
    widths = [e - s for segs in segments.values() for s, e in segs]
    if widths:
        typical_seg = weighted_median(widths)
        segments = {bi: [(s, e) for s, e in segs if e - s >= 0.45 * typical_seg] for bi, segs in segments.items()}
    stats = {bi: [segment_stats(strips[bi], s, e) for s, e in segs] for bi, segs in segments.items()}
    if ref is None:
        all_stats = [st for sts in stats.values() for st in sts]
        if not all_stats:
            return []
        ref = _median_stats(all_stats)
    out: list[Detection] = []
    gaps_raw: list[tuple[int, float, float]] = []
    for bi, segs in segments.items():
        band = strips[bi].band
        for (s, e), st in zip(segs, stats[bi], strict=True):
            if _is_gap(st, ref):
                gaps_raw.append((bi, s, e))
                continue
            x1, y1, x2, y2 = _box_for(band, s, e)
            out.append(Detection(x1, y1, x2, y2, score=0.5, source=source, band=bi))
    facing_widths = [d.width for d in out]
    typical = float(np.median(facing_widths)) if facing_widths else 0.0
    lo, hi = extent if extent is not None else (
        (min(d.x1 for d in out), max(d.x2 for d in out)) if out else (0.0, 0.0))
    for bi, s, e in gaps_raw:
        if e <= lo + 0.25 * typical or s >= hi - 0.25 * typical:
            continue  # outside the stocked part of the rack (wall, aisle, rack end)
        s, e = max(s, lo), min(e, hi)
        k = max(1, round((e - s) / typical)) if typical > 0 else 1
        if typical > 0 and (e - s) < 0.5 * typical:
            continue
        step = (e - s) / k
        band = strips[bi].band
        for j in range(k):
            x1, y1, x2, y2 = _box_for(band, s + j * step, s + (j + 1) * step)
            out.append(Detection(x1, y1, x2, y2, score=0.5, source=source, band=bi, kind="gap"))
    return out


class ClassicDetector:
    """Model-free fallback: splits each band at strong vertical edges and colour changes."""

    name = "classic"

    async def detect(self, frame: WorkFrame, bands: list[Band]) -> tuple[list[Detection], list[Band]]:
        return classic_detect(frame, bands), bands


def classic_detect(frame: WorkFrame, bands: list[Band]) -> list[Detection]:
    if not bands:
        return []
    rgb = rgb_array(frame.image)
    strips = {b.index: band_strip(frame, b, rgb) for b in bands}
    w = frame.size[0]
    segments: dict[int, list[tuple[float, float]]] = {}
    for b in bands:
        min_width = max(8.0, 0.22 * b.height)
        segments[b.index] = segment_band(strips[b.index], 0, w, min_width=min_width)
    dets = classify_segments(strips, segments, source="classic")
    return split_wide(dets, strips)


def split_wide(dets: list[Detection], strips: dict[int, BandStrip]) -> list[Detection]:
    """Split facings much wider than typical when their colour profile repeats (identical facings
    pressed together without a visible boundary)."""
    facings = [d for d in dets if d.kind == "facing"]
    if len(facings) < 3:
        return dets
    typical = float(np.median([d.width for d in facings]))
    out: list[Detection] = []
    for d in dets:
        k = round(d.width / typical) if typical > 0 else 1
        if d.kind != "facing" or d.width < 1.6 * typical or k < 2:
            out.append(d)
            continue
        strip = strips[d.band]
        n = strip.rows
        prof = strip.gray[int(0.2 * n):int(0.8 * n), int(d.x1):int(d.x2)].mean(axis=0)
        prof = prof - prof.mean()
        lag = round(d.width / k)
        if lag < 4 or prof.size <= lag + 4:
            out.append(d)
            continue
        a, b = prof[:-lag], prof[lag:]
        denom = float(np.sqrt((a * a).sum() * (b * b).sum())) or 1.0
        if float((a * b).sum()) / denom < 0.5:
            out.append(d)
            continue
        step = d.width / k
        out.extend(replace(d, x1=d.x1 + j * step, x2=d.x1 + (j + 1) * step) for j in range(k))
    return out


# ── model detections → band-assigned facings ─────────────────────────────────────

def bands_from_boxes(frame: WorkFrame, boxes: list[Detection]) -> list[Band]:
    """Shelf bands from product boxes: rows of boxes at the same height (products stand on shelves)."""
    w = frame.size[0]
    cx = w / 2
    typical_h = float(np.median([d.height for d in boxes]))
    rows: list[list[Detection]] = []
    for d in sorted(boxes, key=lambda d: (d.y1 + d.y2) / 2):
        cy = (d.y1 + d.y2) / 2
        if rows and cy - float(np.mean([(o.y1 + o.y2) / 2 for o in rows[-1]])) < 0.5 * typical_h:
            rows[-1].append(d)
        else:
            rows.append([d])
    spans = [(float(np.percentile([d.y1 for d in r], 15)), float(np.percentile([d.y2 for d in r], 85)))
             for r in rows if len(r) >= 2]
    for i in range(len(spans) - 1):
        if spans[i][1] > spans[i + 1][0]:
            mid = (spans[i][1] + spans[i + 1][0]) / 2
            spans[i] = (spans[i][0], mid)
            spans[i + 1] = (mid, spans[i + 1][1])
    return [Band(i, Line(t, 0.0, cx), Line(b, 0.0, cx), w) for i, (t, b) in enumerate(spans) if b - t > 4]


def refine_detections(
    frame: WorkFrame, bands: list[Band], raw: list[Detection], *, fill: bool = True,
) -> tuple[list[Detection], list[Band]]:
    """NMS, drop container / tag-sized / multi-shelf boxes, assign bands, fill uncovered stretches.

    When the line-based bands explain fewer than 60% of at least six model boxes (stacked packs,
    unusual shelving, signs taken for shelves), the bands are rebuilt from the boxes themselves.
    """
    w, h = frame.size
    dets = [d for d in raw if d.width > 2 and d.height > 2 and d.width * d.height <= 0.35 * w * h and d.width <= 0.5 * w]
    dets = nms(dets, 0.5)
    kept: list[Detection] = []
    for d in dets:
        inside = sum(
            1 for o in dets if o is not d
            and min(d.x2, o.x2) - max(d.x1, o.x1) > 0.8 * o.width
            and min(d.y2, o.y2) - max(d.y1, o.y1) > 0.8 * o.height
        )
        if inside < 2:
            kept.append(d)
    if len(kept) >= 6:
        explained = sum(1 for d in kept if assign_band(bands, d.x1, d.y1, d.x2, d.y2) is not None)
        if explained < 0.6 * len(kept):
            rebuilt = bands_from_boxes(frame, kept)
            if rebuilt:
                logger.info(f"[capture] shelf lines explain {explained}/{len(kept)} boxes; bands rebuilt from boxes")
                bands = rebuilt
    out: list[Detection] = []
    for d in kept:
        bi = assign_band(bands, d.x1, d.y1, d.x2, d.y2)
        if bi is None:
            continue
        band = bands[bi]
        if d.height < 0.35 * band.height or d.width < 0.08 * band.height:
            continue
        out.append(replace(d, band=bi))
    # Inside one band, overlapping boxes are the same facing seen twice: keep the stronger.
    final: list[Detection] = []
    for d in sorted(out, key=lambda d: -d.score):
        clash = any(
            o.band == d.band and min(d.x2, o.x2) - max(d.x1, o.x1) > 0.5 * min(d.width, o.width)
            for o in final
        )
        if not clash:
            final.append(d)
    if fill and final:
        final += fill_uncovered(frame, bands, final)
    return sorted(final, key=lambda d: (d.band, d.x1)), bands


def fill_uncovered(frame: WorkFrame, bands: list[Band], facings: list[Detection]) -> list[Detection]:
    """Stretches of a band that no detection covers: missed facings (textured) or gaps (empty)."""
    rgb = rgb_array(frame.image)
    strips = {b.index: band_strip(frame, b, rgb) for b in bands}
    typical = float(np.median([d.width for d in facings]))
    extent = (min(d.x1 for d in facings), max(d.x2 for d in facings))
    ref_stats = [segment_stats(strips[d.band], d.x1, d.x2) for d in facings]
    ref = _median_stats(ref_stats)
    segments: dict[int, list[tuple[float, float]]] = {}
    for b in bands:
        covered = sorted((d.x1, d.x2) for d in facings if d.band == b.index)
        cursor = extent[0]
        holes: list[tuple[float, float]] = []
        for x1, x2 in covered:
            if x1 - cursor >= 0.6 * typical:
                holes.append((cursor, x1))
            cursor = max(cursor, x2)
        if extent[1] - cursor >= 0.6 * typical:
            holes.append((cursor, extent[1]))
        segs: list[tuple[float, float]] = []
        for xa, xb in holes:
            parts = segment_band(strips[b.index], xa, xb, min_width=0.5 * typical)
            segs.extend(parts or [(xa, xb)])
        if segs:
            segments[b.index] = segs
    if not segments:
        return []
    return classify_segments(strips, segments, source="fill", ref=ref, extent=extent)


# ── Grounding DINO (optional dependency) ─────────────────────────────────────────

def gdino_available() -> bool:
    return importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None


class GroundingDinoDetector:
    """Zero-shot detector; the model is loaded lazily and released by `close()`."""

    name = "gdino"

    def __init__(self, model_id: str = GDINO_MODEL_ID, *, prompt: str = GDINO_PROMPT,
                 box_threshold: float = 0.1, text_threshold: float = 0.1, threads: int = 2,
                 shortest_edge: int = 512, longest_edge: int = 853) -> None:
        self.model_id = model_id
        self.prompt = prompt
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        self.threads = threads
        # Input resolution: the model default (800 / 1333) costs ~2.5× more CPU for little gain on shelves.
        self.size = {"shortest_edge": shortest_edge, "longest_edge": longest_edge}
        # transformers objects are untyped; a namespace keeps them out of the typed surface.
        self._hf = types.SimpleNamespace(processor=None, model=None)

    def _load(self) -> types.SimpleNamespace:
        if self._hf.model is None:
            torch = importlib.import_module("torch")
            transformers = importlib.import_module("transformers")
            torch.set_num_threads(self.threads)
            self._hf.processor = transformers.AutoProcessor.from_pretrained(self.model_id)
            self._hf.model = transformers.AutoModelForZeroShotObjectDetection.from_pretrained(self.model_id)
            self._hf.model.eval()
        return self._hf

    def detect_image(self, image: Image.Image) -> list[Detection]:
        torch = importlib.import_module("torch")
        hf = self._load()
        inputs = hf.processor(images=image, text=self.prompt, return_tensors="pt", size=self.size)
        with torch.inference_mode():
            outputs = hf.model(**inputs)
        results = hf.processor.post_process_grounded_object_detection(
            outputs, inputs["input_ids"], threshold=self.box_threshold, text_threshold=self.text_threshold,
            target_sizes=[(image.size[1], image.size[0])],
        )
        boxes = [[float(v) for v in b] for b in results[0]["boxes"].tolist()]
        scores = [float(s) for s in results[0]["scores"].tolist()]
        return [Detection(b[0], b[1], b[2], b[3], score=s, source="gdino") for b, s in zip(boxes, scores, strict=True)]

    async def detect(self, frame: WorkFrame, bands: list[Band]) -> tuple[list[Detection], list[Band]]:
        raw = await asyncio.to_thread(self.detect_image, frame.image)
        return refine_detections(frame, bands, raw, fill=False)

    def close(self) -> None:
        self._hf = types.SimpleNamespace(processor=None, model=None)
        gc.collect()


# ── VLM grounding ────────────────────────────────────────────────────────────────

class _GroundedBox(BaseModel):
    box_2d: list[float] = Field(min_length=4, max_length=4)
    label: str = Field(default="", max_length=40)


class _Grounding(BaseModel):
    products: list[_GroundedBox] = Field(default_factory=list[_GroundedBox], max_length=80)


VLM_GROUNDING_SYSTEM_PROMPT = "You detect products on store shelf photos. Answer with JSON only."
VLM_GROUNDING_PROMPT = (
    "Find every product facing on the shelves in this photo: one box per visible package "
    "(bottle, can, box, bag, cup). Do not box shelves, price tags or signs. "
    "Return products: [{{\"box_2d\": [x1, y1, x2, y2], \"label\": short name}}]. "
    "Coordinates: {convention}."
)

type BoxConvention = Literal["auto", "pixels", "norm1000", "norm1", "gemini"]


def normalize_boxes(
    raw: list[list[float]], size: tuple[int, int], *, convention: BoxConvention = "auto", model: str = "",
) -> list[tuple[float, float, float, float]]:
    """VLM box lists → pixel xyxy in an image of `size`.

    Gemini answers [ymin, xmin, ymax, xmax] on 0–1000; Qwen2.5-VL answers absolute pixels of the
    image it saw; Qwen3-VL and most others use 0–1000. With `auto`, Gemini is recognised by name,
    values ≤ 1 are taken as fractions, and values that fit 0–1000 but overflow the image (or
    come from a model known to normalise) as 0–1000.
    """
    w, h = size
    if not raw:
        return []
    conv = convention
    if conv == "auto":
        lowered = model.lower()
        peak = max(max(abs(v) for v in b) for b in raw)
        if "gemini" in lowered:
            conv = "gemini"
        elif peak <= 1.0:
            conv = "norm1"
        elif peak <= 1000 and ("qwen3" in lowered or "qwen-3" in lowered or any(
                b[0] > w or b[2] > w or b[1] > h or b[3] > h for b in raw)):
            conv = "norm1000"
        else:
            conv = "pixels"
    out: list[tuple[float, float, float, float]] = []
    for b in raw:
        if conv == "gemini":
            y1, x1, y2, x2 = b[0] / 1000 * h, b[1] / 1000 * w, b[2] / 1000 * h, b[3] / 1000 * w
        elif conv == "norm1000":
            x1, y1, x2, y2 = b[0] / 1000 * w, b[1] / 1000 * h, b[2] / 1000 * w, b[3] / 1000 * h
        elif conv == "norm1":
            x1, y1, x2, y2 = b[0] * w, b[1] * h, b[2] * w, b[3] * h
        else:
            x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
        x1, x2 = sorted((max(0.0, min(w, x1)), max(0.0, min(w, x2))))
        y1, y2 = sorted((max(0.0, min(h, y1)), max(0.0, min(h, y2))))
        if x2 - x1 >= 2 and y2 - y1 >= 2:
            out.append((x1, y1, x2, y2))
    return out


def image_data_url(image: Image.Image, *, max_side: int, fmt: str = "PNG") -> tuple[str, tuple[int, int]]:
    w, h = image.size
    s = min(1.0, max_side / max(w, h))
    img = image if s == 1.0 else image.resize((max(1, round(w * s)), max(1, round(h * s))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format=fmt, **({"quality": 90} if fmt == "JPEG" else {}))
    mime = "image/png" if fmt == "PNG" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii"), img.size


class VLMGroundingDetector:
    """Boxes from a vision-language model's JSON answer (one call per photo)."""

    name = "vlm"

    def __init__(self, llm: ImageLLM, *, model: str = "", convention: BoxConvention = "auto",
                 max_side: int = 768) -> None:
        self.llm = llm
        self.model = model
        self.convention: BoxConvention = convention
        self.max_side = max_side
        self.calls = 0

    async def detect(self, frame: WorkFrame, bands: list[Band]) -> tuple[list[Detection], list[Band]]:
        url, size = image_data_url(frame.image, max_side=self.max_side)
        hint = {
            "gemini": "[ymin, xmin, ymax, xmax] normalised to 0-1000",
            "norm1000": "x1, y1, x2, y2 normalised to 0-1000",
            "norm1": "x1, y1, x2, y2 as fractions 0-1",
        }.get(self.convention, f"pixels of this {size[0]}x{size[1]} image")
        self.calls += 1
        try:
            answer = await self.llm.generate_structured_with_image_async(
                _Grounding, VLM_GROUNDING_SYSTEM_PROMPT, VLM_GROUNDING_PROMPT.format(convention=hint), url,
                max_retries=1, seed=0,
            )
        except Exception as e:  # noqa: BLE001 — a failed grounding call falls back to the classic detector
            logger.warning(f"[capture] VLM grounding failed: {type(e).__name__}: {e}")
            return [], bands
        boxes = normalize_boxes([b.box_2d for b in answer.products], size, convention=self.convention, model=self.model)
        fx = frame.size[0] / size[0]
        fy = frame.size[1] / size[1]
        raw = [Detection(x1 * fx, y1 * fy, x2 * fx, y2 * fy, score=0.5, source="vlm") for x1, y1, x2, y2 in boxes]
        return refine_detections(frame, bands, raw, fill=False)
