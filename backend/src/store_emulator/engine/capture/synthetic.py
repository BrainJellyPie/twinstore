"""Synthetic shelf photos with exact ground truth, for tests and the capture benchmark.

A rack face is re-stocked with runs of identical facings and out-of-stock holes, rendered with the
shopper renderer (`engine.perception.shelf_render.render_face`), cleaned of its set-of-mark badges
(real shelves have none), and optionally degraded like a phone photo: perspective, roll, lighting
gradient, colour cast, blur, sensor noise and JPEG compression. Every facing and gap box is carried
through the same geometric transform, so the ground truth stays exact.
"""

import io
import math
import random
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType, Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.engine.layout_gen.catalog import CATALOG, localized
from store_emulator.engine.perception.shelf_render import face_slots, render_face

type Severity = Literal["clean", "mild", "strong"]
type XYXY = tuple[float, float, float, float]

GAP_SKU = "__gap__"


@dataclass(frozen=True)
class GTFacing:
    box: XYXY
    row: int            # 0 = top shelf in the photo
    level: int          # Parastore level of that shelf
    col: int            # position in the row (gaps count as positions)
    run: int            # index of the run of identical facings in the row
    item: SlotItem


@dataclass(frozen=True)
class GTGap:
    box: XYXY
    row: int
    level: int
    col: int
    item: SlotItem      # the product that is out of stock (its tag is still on the shelf)


@dataclass
class SyntheticShelf:
    image: Image.Image
    facings: list[GTFacing]
    gaps: list[GTGap]
    rack: Rack              # ground-truth rack: the face's slots as a Parastore planogram (gaps removed)
    face: Face
    currency: str
    severity: Severity = "clean"
    meta: dict[str, object] = field(default_factory=dict[str, object])

    @property
    def rows(self) -> int:
        return RACK_LEVELS


@dataclass(frozen=True)
class _Geometry:
    columns: int
    cell_w: int
    pkg_h: int
    tag_h: int
    row_h: int
    top: int
    left: int
    mark_size: int


def _geometry(columns: int, width: int) -> _Geometry:
    """Layout constants of `render_face` (kept in sync by tests/engine/test_capture.py)."""
    margin, frame, header = 14, 10, 46
    inner_w = width - 2 * margin - 2 * frame
    cell_w = inner_w // columns
    pkg_h = max(100, min(170, int(cell_w * 0.78)))
    tag_h = max(26, cell_w // 6)
    return _Geometry(
        columns=columns, cell_w=cell_w, pkg_h=pkg_h, tag_h=tag_h, row_h=18 + pkg_h + tag_h + 10,
        top=margin + header + frame + 18, left=margin + frame, mark_size=max(14, min(20, cell_w // 8)),
    )


def _package_box(g: _Geometry, row: int, col: int) -> tuple[int, int, int, int]:
    y0 = g.top + row * g.row_h
    board_y = y0 + 6 + g.pkg_h
    return g.left + col * g.cell_w + 6, y0 + 6, g.left + (col + 1) * g.cell_w - 6, board_y - 2


def restock(
    base: Rack, face: Face, *, currency: str, rng: random.Random, blocks: int = 1, columns: int = 4,
    gap_rate: float = 0.12, facing_weights: tuple[float, ...] = (0.5, 0.35, 0.15),
) -> tuple[Rack, list[list[bool]]]:
    """A `blocks`-wide copy of `base` whose face carries runs of identical facings and some gaps.

    Returns the rendered rack (gaps still stocked, so their tags render) and, per row top → bottom,
    which positions are gaps.
    """
    category = base.rack_desc if base.rack_desc in CATALOG else "chips"
    names_seen: dict[str, SlotItem] = {}
    pool: list[SlotItem] = []
    for slot in base.slots:
        if slot.face == face:
            for item in slot.items:
                if item.name not in names_seen:
                    names_seen[item.name] = item
                    pool.append(item)
    for entry in CATALOG[category]:
        name, price = localized(entry, currency)
        if name not in names_seen:
            item = SlotItem(sku=f"syn_{len(names_seen):03d}", name=name, price=price)
            names_seen[name] = item
            pool.append(item)
    rng.shuffle(pool)
    per_row = columns
    rows_items: list[list[SlotItem]] = []
    rows_gaps: list[list[bool]] = []
    cursor = 0
    for _ in range(RACK_LEVELS):
        entries: list[SlotItem] = []
        while len(entries) < per_row:
            item = pool[cursor % len(pool)]
            cursor += 1
            n = rng.choices(range(1, len(facing_weights) + 1), weights=facing_weights, k=1)[0]
            entries.extend([item] * min(n, per_row - len(entries)))
        gaps = [rng.random() < gap_rate for _ in entries]
        if all(gaps):
            gaps[0] = False
        rows_items.append(entries)
        rows_gaps.append(gaps)
    per_block = per_row // blocks
    slots: list[Slot] = []
    for r, entries in enumerate(rows_items):
        level = RACK_LEVELS - r
        for b in range(blocks):
            chunk = entries[b * per_block:(b + 1) * per_block]
            slots.append(Slot(block=b, face=face, level=level, items=chunk))
    rack = base.model_copy(update={"shape": [[1] * blocks], "slots": slots, "rotation": 0})
    return rack, rows_gaps


def _sample(img: Image.Image, x: float, y: float) -> tuple[int, int, int]:
    px = img.getpixel((int(x), int(y)))
    if isinstance(px, tuple) and len(px) >= 3:
        return int(px[0]), int(px[1]), int(px[2])
    return (128, 128, 128)


def render_scene(
    rack: Rack, face: Face, gaps: list[list[bool]], *, currency: str, width: int = 768,
) -> SyntheticShelf:
    rows = face_slots(rack, face)
    columns = max(1, max((len(r) for r in rows), default=1))
    # Capture benchmarks model four physical shelves, without wrapping the chart's rows.
    width = max(width, columns * 120 + 48)
    # Their colour oracle and exact box outlines require synthetic packages rather than photos.
    view = render_face(rack, face, currency=currency, width=width, number_on_tag=False,
                       image_loader=lambda item: None)
    img = Image.open(io.BytesIO(view.png)).convert("RGB")
    g = _geometry(columns, width)
    draw = ImageDraw.Draw(img)
    fridge = rack.type == RackType.FRIDGE
    facings: list[GTFacing] = []
    gt_gaps: list[GTGap] = []
    for r, row in enumerate(rows):
        level = RACK_LEVELS - r
        run = -1
        prev = ""
        for c, (_, item) in enumerate(row):
            x0, y0, x1, y1 = _package_box(g, r, c)
            is_gap = r < len(gaps) and c < len(gaps[r]) and gaps[r][c]
            # Erase the numbered badge: redraw the package corner under it.
            rad = max(13, g.mark_size - 2)
            bcx, bcy = x0 + rad - 2, y0 - 6 + rad + 2
            patch_box = (bcx - rad - 2, bcy - rad - 2, bcx + rad + 3, bcy + rad + 3)
            pkg_color = _sample(img, x1 - 10, y1 - 10)
            bg_color = _sample(img, x0 - 4, (y0 + y1) / 2)
            patch = Image.new("RGB", (patch_box[2] - patch_box[0], patch_box[3] - patch_box[1]), bg_color)
            ImageDraw.Draw(patch).rounded_rectangle(
                (x0 - patch_box[0], y0 - patch_box[1], x1 - patch_box[0], y1 - patch_box[1]),
                radius=10, fill=pkg_color, outline=(40, 40, 40), width=2,
            )
            img.paste(patch, (patch_box[0], patch_box[1]))
            if is_gap:
                back = (88, 96, 108) if fridge else (128, 116, 100)
                draw.rectangle((x0 - 5, y0 - 5, x1 + 5, y1 + 1), fill=back)
                shade = tuple(max(0, v - 28) for v in back)
                draw.rectangle((x0 - 5, y0 - 5, x1 + 5, y0 + 8), fill=(shade[0], shade[1], shade[2]))
                gt_gaps.append(GTGap(box=(x0, y0, x1, y1), row=r, level=level, col=c, item=item))
                prev = ""
                continue
            if item.name != prev:
                run += 1
            prev = item.name
            facings.append(GTFacing(box=(x0, y0, x1, y1), row=r, level=level, col=c, run=run, item=item))
    stocked = [
        s.model_copy(update={"items": [it for k, it in enumerate(s.items) if not _is_gap_entry(rack, face, s, k, gaps)]})
        for s in rack.slots
    ]
    gt_rack = rack.model_copy(update={"slots": [s for s in stocked if s.items]})
    return SyntheticShelf(image=img, facings=facings, gaps=gt_gaps, rack=gt_rack, face=face, currency=currency)


def _is_gap_entry(rack: Rack, face: Face, slot: Slot, k: int, gaps: list[list[bool]]) -> bool:
    if slot.face != face:
        return False
    row = RACK_LEVELS - slot.level
    blocks_before = sum(
        len(s.items) for s in rack.slots
        if s.face == face and s.level == slot.level and s.block < slot.block
    )
    col = blocks_before + k
    return row < len(gaps) and col < len(gaps[row]) and gaps[row][col]


# ── phone-photo degradation ─────────────────────────────────────────────────────

_SEVERITY: dict[Severity, dict[str, tuple[float, float]]] = {
    "clean": {},
    "mild": {"corner": (0.0, 0.03), "roll": (0.0, 2.0), "light": (0.0, 0.25), "cast": (0.0, 0.06),
             "blur": (0.0, 0.8), "noise": (1.5, 4.0), "jpeg": (70, 90)},
    "strong": {"corner": (0.03, 0.07), "roll": (2.0, 5.0), "light": (0.25, 0.5), "cast": (0.05, 0.12),
               "blur": (0.6, 1.6), "noise": (4.0, 9.0), "jpeg": (40, 65)},
}


def _homography(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> np.ndarray:
    """3×3 matrix H with dst ~ H · src (four point pairs)."""
    a: list[list[float]] = []
    b: list[float] = []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.extend([u, v])
    h = np.linalg.solve(np.array(a, dtype=np.float64), np.array(b, dtype=np.float64))
    return np.append(h, 1.0).reshape(3, 3)


def _apply_h(h: np.ndarray, x: float, y: float) -> tuple[float, float]:
    p = h @ np.array([x, y, 1.0])
    return float(p[0] / p[2]), float(p[1] / p[2])


def _warp_box(h: np.ndarray, box: XYXY, size: tuple[int, int]) -> XYXY:
    x1, y1, x2, y2 = box
    pts = [_apply_h(h, x, y) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w, hgt = size
    return max(0.0, min(xs)), max(0.0, min(ys)), min(float(w), max(xs)), min(float(hgt), max(ys))


def _background(size: tuple[int, int], rng: random.Random) -> Image.Image:
    w, h = size
    base = np.array([rng.uniform(150, 215)] * 3, dtype=np.float32) + np.array(
        [rng.uniform(-12, 12) for _ in range(3)], dtype=np.float32)
    ys = np.linspace(-0.5, 0.5, h, dtype=np.float32)[:, None, None]
    field_ = base[None, None, :] * (1.0 + rng.uniform(-0.25, 0.25) * ys)
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, 6, (h, w, 3)).astype(np.float32)
    arr = np.clip(np.broadcast_to(field_, (h, w, 3)) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def degrade(scene: SyntheticShelf, severity: Severity, rng: random.Random) -> SyntheticShelf:
    """Phone-photo version of a rendered scene, with boxes transformed exactly."""
    img = scene.image
    w, h = img.size
    pad_x, pad_y = int(w * rng.uniform(0.04, 0.1)), int(h * rng.uniform(0.04, 0.1))
    canvas_size = (w + 2 * pad_x, h + 2 * pad_y)
    canvas = _background(canvas_size, rng)
    canvas.paste(img, (pad_x, pad_y))
    shift = np.array([[1, 0, pad_x], [0, 1, pad_y], [0, 0, 1]], dtype=np.float64)
    p = _SEVERITY[severity]
    cw, ch = canvas_size
    corners = [(0.0, 0.0), (float(cw), 0.0), (float(cw), float(ch)), (0.0, float(ch))]
    hmat = shift
    if p:
        lo, hi = p["corner"]
        moved = [(x + rng.choice((-1, 1)) * rng.uniform(lo, hi) * cw, y + rng.choice((-1, 1)) * rng.uniform(lo, hi) * ch)
                 for x, y in corners]
        roll = math.radians(rng.choice((-1, 1)) * rng.uniform(*p["roll"]))
        cx, cy = cw / 2, ch / 2
        rolled = [(cx + (x - cx) * math.cos(roll) - (y - cy) * math.sin(roll),
                   cy + (x - cx) * math.sin(roll) + (y - cy) * math.cos(roll)) for x, y in moved]
        persp = _homography(corners, rolled)
        hmat = persp @ shift
        inv = np.linalg.inv(persp)
        coeffs = (inv / inv[2, 2]).flatten()[:8].tolist()
        canvas = canvas.transform(canvas_size, Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC,
                                  fillcolor=(170, 170, 170))
        arr = np.asarray(canvas, dtype=np.float32)
        yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
        a, b = (rng.uniform(*p["light"]) * rng.choice((-1, 1)) for _ in range(2))
        gain = 1.0 + a * (xx / cw - 0.5) + b * (yy / ch - 0.5)
        r2 = ((xx - cw / 2) / (cw / 2)) ** 2 + ((yy - ch / 2) / (ch / 2)) ** 2
        gain *= 1.0 - rng.uniform(0.0, 0.2) * r2 / 2
        cast = np.array([1.0 + rng.uniform(-1, 1) * rng.uniform(*p["cast"]) for _ in range(3)], dtype=np.float32)
        arr = arr * gain[:, :, None] * cast[None, None, :]
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
        radius = rng.uniform(*p["blur"])
        if radius > 0.05:
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius))
        sigma = rng.uniform(*p["noise"])
        noisy = np.asarray(canvas, dtype=np.float32) + np.random.default_rng(rng.randrange(1 << 30)).normal(0, sigma, (ch, cw, 3))
        canvas = Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8), "RGB")
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=int(rng.uniform(*p["jpeg"])))
        canvas = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    facings = [GTFacing(_warp_box(hmat, f.box, canvas_size), f.row, f.level, f.col, f.run, f.item) for f in scene.facings]
    gaps = [GTGap(_warp_box(hmat, g.box, canvas_size), g.row, g.level, g.col, g.item) for g in scene.gaps]
    return SyntheticShelf(image=canvas, facings=facings, gaps=gaps, rack=scene.rack, face=scene.face,
                          currency=scene.currency, severity=severity, meta=dict(scene.meta))


def make_scene(
    base: Rack, face: Face, *, currency: str, seed: int, severity: Severity = "clean", blocks: int = 1,
    columns: int = 4, gap_rate: float = 0.12, width: int = 768,
) -> SyntheticShelf:
    rng = random.Random(seed)
    rack, gaps = restock(base, face, currency=currency, rng=rng, blocks=blocks, columns=columns, gap_rate=gap_rate)
    scene = render_scene(rack, face, gaps, currency=currency, width=width)
    scene.meta = {"seed": seed, "rack_id": base.id, "rack_name": base.rack_name, "category": base.rack_desc,
                  "blocks": blocks, "columns": columns, "rack_type": base.type.value}
    return degrade(scene, severity, rng) if severity != "clean" else scene
