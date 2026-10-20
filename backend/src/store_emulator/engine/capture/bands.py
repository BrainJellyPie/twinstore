"""Shelf levels from horizontal shelf edges (classical CV, no model).

Shelf edges (the lip with the price-tag strip) are long, straight, near-horizontal lines that span
the whole gondola. Perspective keeps them straight but gives each one its own slope, so instead of
a plain row projection we accumulate horizontal-edge evidence along slanted lines (a 1-D Hough
transform over (height, slope)) and pick the strongest lines. Peaks closer than a few pixels
(shelf lip, tag strip, product bottoms and the next products' tops) form one *rail*; the product
zones between consecutive rails are the shelf bands, kept when they are tall and textured enough to
hold products.
"""

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

from store_emulator.domain.rack import RACK_LEVELS

from .frame import BoolArray, FloatArray, WorkFrame, make_frame, sobel

_SLOPES = np.linspace(-0.15, 0.15, 61)


@dataclass(frozen=True)
class Line:
    """y = y0 + slope · (x − cx), in work-frame pixels."""
    y0: float
    slope: float
    cx: float

    def at(self, x: float) -> float:
        return self.y0 + self.slope * (x - self.cx)


@dataclass(frozen=True)
class Rail:
    top: Line
    bottom: Line
    strength: float


@dataclass(frozen=True)
class Band:
    index: int          # 0 = top band
    top: Line           # product zone: below `top`, above `bottom`
    bottom: Line
    width: int          # work-frame width (x range 0..width)

    @property
    def height(self) -> float:
        return self.bottom.y0 - self.top.y0

    def top_at(self, x: float) -> float:
        return self.top.at(x)

    def bottom_at(self, x: float) -> float:
        return self.bottom.at(x)

    def vertical_overlap(self, x: float, y1: float, y2: float) -> float:
        """Overlap (pixels) of [y1, y2] with the band at column x."""
        return max(0.0, min(y2, self.bottom_at(x)) - max(y1, self.top_at(x)))


def long_runs(mask: BoolArray, min_len: int) -> BoolArray:
    """Keep only horizontal runs of at least `min_len` pixels (drops text strokes and texture)."""
    h, w = mask.shape
    padded = np.zeros((h, w + 2), dtype=np.int8)
    padded[:, 1:-1] = mask
    d = np.diff(padded, axis=1)
    sr, sc = np.nonzero(d == 1)
    er, ec = np.nonzero(d == -1)
    keep = (ec - sc) >= min_len
    marks = np.zeros((h, w + 1), dtype=np.int32)
    np.add.at(marks, (sr[keep], sc[keep]), 1)
    np.add.at(marks, (er[keep], ec[keep]), -1)
    return np.cumsum(marks, axis=1)[:, :w] > 0


def horizontal_edges(gray: FloatArray) -> tuple[BoolArray, FloatArray, FloatArray]:
    """Thin, long, near-horizontal edges: shelf lips, tag strips, package tops and bottoms."""
    gx, gy = sobel(gray)
    t = max(24.0, float(np.percentile(gy, 80)))
    peak_y = np.ones_like(gy, dtype=np.bool_)
    peak_y[1:] &= gy[1:] >= gy[:-1]
    peak_y[:-1] &= gy[:-1] >= gy[1:]
    mask = (gy > t) & (gy > 1.3 * gx) & peak_y
    # ±1 row of slack so a slightly slanted edge still forms long runs.
    dil = mask.copy()
    dil[1:] |= mask[:-1]
    dil[:-1] |= mask[1:]
    w = mask.shape[1]
    return long_runs(dil, max(12, round(0.025 * w))), gx, gy


def line_accumulator(mask: BoolArray) -> tuple[FloatArray, FloatArray]:
    """Coverage of the best slanted line through (cx, y) for every row y, and its slope."""
    h, w = mask.shape
    cx = w / 2
    cum = np.zeros((h, w + 1), dtype=np.float32)
    cum[:, 1:] = np.cumsum(mask, axis=1, dtype=np.float32)
    max_shift = math.ceil(float(np.abs(_SLOPES).max()) * w / 2) + 1
    xs = np.arange(w, dtype=np.float64)
    best = np.zeros(h, dtype=np.float32)
    best_slope = np.zeros(h, dtype=np.float32)
    for k in _SLOPES:
        shifts = np.rint(k * (xs - cx)).astype(np.int64)
        change = np.flatnonzero(np.diff(shifts)) + 1
        starts = np.concatenate(([0], change))
        ends = np.concatenate((change, [w]))
        acc = np.zeros(h + 2 * max_shift, dtype=np.float32)
        for s, e in zip(starts.tolist(), ends.tolist(), strict=True):
            d = int(shifts[s])
            run = cum[:, e] - cum[:, s]
            # The line through (cx, y) crosses these columns at row y + d: acc[y] += run[y + d].
            lo = max_shift - d
            acc[lo:lo + h] += run
        cover = acc[max_shift:max_shift + h] / w
        better = cover > best
        best = np.where(better, cover, best)
        best_slope = np.where(better, np.float32(k), best_slope)
    return best, best_slope


def find_rails(frame: WorkFrame) -> tuple[list[Rail], FloatArray]:
    mask, _, _ = horizontal_edges(frame.gray)
    profile, slopes = line_accumulator(mask)
    h, w = mask.shape
    cx = w / 2
    peak = float(profile.max()) if profile.size else 0.0
    thr = max(0.2, 0.4 * peak)
    ys = [
        y for y in range(1, h - 1)
        if profile[y] >= thr and profile[y] >= profile[y - 1] and profile[y] > profile[y + 1]
    ]
    merge = max(6.0, 0.03 * h)
    rails: list[Rail] = []
    cluster: list[int] = []

    def close(group: list[int]) -> None:
        strongest = max(group, key=lambda y: float(profile[y]))
        slope = float(slopes[strongest])
        rails.append(Rail(
            top=Line(float(group[0]), slope, cx), bottom=Line(float(group[-1]), slope, cx),
            strength=float(profile[strongest]),
        ))

    for y in ys:
        if cluster and y - cluster[-1] > merge:
            close(cluster)
            cluster = []
        cluster.append(y)
    if cluster:
        close(cluster)
    return rails, profile


def _region_texture(frame: WorkFrame, grad: FloatArray, top: Line, bottom: Line) -> float:
    """Density of strong edges (outlines, print) in a zone; sensor noise and plain walls stay low."""
    h, w = grad.shape
    x0, x1 = int(0.1 * w), int(0.9 * w)
    xs = np.arange(x0, x1, max(1, (x1 - x0) // 64))
    total, count = 0.0, 0
    for x in xs.tolist():
        y0 = max(0, round(top.at(x)) + 2)
        y1 = min(h, round(bottom.at(x)) - 2)
        if y1 > y0:
            total += float((grad[y0:y1, x] > 60.0).sum())
            count += y1 - y0
    return total / count if count else 0.0


def _regions(rails: list[Rail], h: int, cx: float) -> list[tuple[Line, Line, bool]]:
    """Zones above the first rail, between rails and below the last rail (flag: touches the border)."""
    edges = [Line(0.0, 0.0, cx), *(line for r in rails for line in (r.top, r.bottom)), Line(float(h - 1), 0.0, cx)]
    out: list[tuple[Line, Line, bool]] = []
    for i in range(0, len(edges), 2):
        out.append((edges[i], edges[i + 1], i == 0 or i + 2 >= len(edges)))
    return out


def _reference_height(heights: list[float]) -> float:
    """Typical band height: median of the taller half (split bands and signs only lower the rest)."""
    ordered = sorted(heights)
    return float(np.median(ordered[len(ordered) // 2:])) if len(ordered) >= 3 else ordered[len(ordered) // 2]


def merge_weak_rails(rails: list[Rail], h: int, cx: float) -> list[Rail]:
    """Drop weak rails that cut one shelf into two short zones (a line of text, a label edge)."""
    rails = list(rails)
    while len(rails) >= 2:
        regions = _regions(rails, h, cx)
        heights = [b.y0 - t.y0 for t, b, _ in regions if b.y0 - t.y0 >= 0.06 * h]
        if not heights:
            break
        ref = _reference_height(heights)
        median_strength = float(np.median([r.strength for r in rails]))
        weakest: int | None = None
        for i, r in enumerate(rails):
            above = regions[i][1].y0 - regions[i][0].y0
            below = regions[i + 1][1].y0 - regions[i + 1][0].y0
            if (r.strength < 0.7 * median_strength and above < 0.75 * ref and below < 0.75 * ref
                    and above + below + (r.bottom.y0 - r.top.y0) <= 1.5 * ref
                    and (weakest is None or r.strength < rails[weakest].strength)):
                weakest = i
        if weakest is None:
            break
        del rails[weakest]
    return rails


def detect_bands(frame: WorkFrame) -> list[Band]:
    """Shelf bands top → bottom. Falls back to one band covering the image when no shelf edge is found."""
    w, h = frame.size
    cx = w / 2
    rails, _ = find_rails(frame)
    rails = merge_weak_rails(rails, h, cx)
    gx, gy = sobel(frame.gray)
    grad = gx + gy
    image_tex = float((grad > 60.0).mean()) or 1.0
    candidates = [(t, b, border, b.y0 - t.y0) for t, b, border in _regions(rails, h, cx) if b.y0 - t.y0 >= 0.06 * h]
    if not candidates:
        return [Band(0, Line(0.02 * h, 0.0, cx), Line(0.98 * h, 0.0, cx), w)]
    # The typical band height comes from textured zones only: tall signs, drawers or floor would
    # otherwise inflate it and push real shelves below the height cut.
    all_tex = [_region_texture(frame, grad, t, b) / image_tex for t, b, _, _ in candidates]
    median_tex = float(np.median(all_tex))
    textured = [c[3] for c, tx in zip(candidates, all_tex, strict=True) if tx >= 0.5 * median_tex]
    ref = _reference_height(textured or [c[3] for c in candidates])
    tall = [c for c in candidates if c[3] >= 0.6 * ref]
    textures = [tx for c, tx in zip(candidates, all_tex, strict=True) if c[3] >= 0.6 * ref]
    tex_ref = float(np.median(textures)) if textures else 0.0
    bands: list[Band] = []
    for (top, bottom, border, height), tex in zip(tall, textures, strict=True):
        if tex < 0.45 * tex_ref:
            continue
        if border and height < 0.7 * ref:
            continue
        bands.append(Band(len(bands), top, bottom, w))
    if not bands:
        return [Band(0, Line(0.02 * h, 0.0, cx), Line(0.98 * h, 0.0, cx), w)]
    return bands


def dominant_tilt(gray: FloatArray, max_deg: float = 20.0) -> float:
    """Coarse roll from the orientation histogram of strong near-horizontal edges (±max_deg)."""
    p = np.pad(gray, 1, mode="edge")
    sx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    sy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    mag = np.hypot(sx, sy)
    strong = mag > max(40.0, float(np.percentile(mag, 90)))
    # Gradient of an edge with slope s points at 90° + atan(s) (mod 180).
    dev = (np.degrees(np.arctan2(sy[strong], sx[strong])) % 180.0) - 90.0
    weights = mag[strong]
    sel = np.abs(dev) <= max_deg
    if int(sel.sum()) < 50:
        return 0.0
    hist, edges = np.histogram(dev[sel], bins=int(2 * max_deg / 0.5), range=(-max_deg, max_deg), weights=weights[sel])
    smooth = np.convolve(hist, np.ones(3) / 3, mode="same")
    i = int(np.argmax(smooth))
    return float((edges[i] + edges[i + 1]) / 2)


def estimate_tilt(frame: WorkFrame) -> float:
    """Residual roll in degrees (PIL rotate angle that makes shelf edges horizontal); 0 if unsure."""
    rails, _ = find_rails(frame)
    strong = [r for r in rails if r.strength >= 0.3]
    if len(strong) < 2:
        return 0.0
    slopes = sorted(r.top.slope for r in strong)
    median = slopes[len(slopes) // 2]
    # A line with slope s (y down) is rotated level by a counter-clockwise rotation of atan(s).
    return math.degrees(math.atan(median))


def band_levels(n_bands: int) -> list[int]:
    """Parastore level for each band (top → bottom).

    Each band goes to the level whose quarter of the unit height contains the band's centre, so a
    4-shelf photo maps 1:1, 5–6 shelves merge neighbours, and a single shelf lands at eye level (3).
    """
    levels: list[int] = []
    for i in range(n_bands):
        j = n_bands - 1 - i  # 0 = bottom band
        level = 1 + math.floor((j + 0.5) * RACK_LEVELS / n_bands)
        levels.append(min(RACK_LEVELS, max(1, level)))
    return levels


def assign_band(bands: list[Band], x1: float, y1: float, x2: float, y2: float) -> int | None:
    """Band holding the box, or None when it sits on no band or spans several (a whole-shelf box)."""
    if not bands:
        return None
    cx = (x1 + x2) / 2
    height = max(1.0, y2 - y1)
    overlaps = [b.vertical_overlap(cx, y1, y2) for b in bands]
    best = max(range(len(bands)), key=lambda i: overlaps[i])
    if overlaps[best] < 0.5 * height:
        return None
    spanned = sum(1 for i, o in enumerate(overlaps) if o >= 0.35 * max(1.0, bands[i].height))
    if spanned >= 2:
        return None
    return best


def deskewed_frame(photo: Image.Image) -> WorkFrame:
    """Work frame with the camera roll removed: coarse orientation histogram, then rail slopes."""
    f0 = make_frame(photo)
    coarse = dominant_tilt(f0.gray)
    f1 = make_frame(photo, angle=coarse) if abs(coarse) >= 0.25 else f0
    fine = estimate_tilt(f1)
    if abs(fine) < 0.2:
        return f1
    return make_frame(photo, angle=f1.angle + fine)
