"""Reading a floor plan image into fixtures.

`classic_read` needs no model: dark ink is separated from paper (Otsu), the largest ink component is
taken as the outer walls, filled rectangles (ink components) and outlined rectangles (paper regions
enclosed by ink) inside them become fixtures, and the widest break in the outer wall becomes the
entrance. Fixture kinds follow from where they stand: against the back wall → fridge, against another
wall → wall shelf, free-standing and elongated → two-sided gondola, small and next to the entrance →
counter.

`vlm_read` asks a vision-language model for the outline, the size if a scale is drawn, and every
fixture with its kind and any category words written on it.
"""

from collections import deque
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, Self

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, model_validator

from store_emulator.domain.floorplan import FixtureKind, FloorPlanReading, PlanFixture
from store_emulator.engine.capture.detect import image_data_url

type BoolArray = npt.NDArray[np.bool_]

WORK_SIDE = 400
DEFAULT_LONG_SIDE_M = 12.0   # a typical small store, used when the plan carries no scale


@dataclass(frozen=True)
class Component:
    x1: int
    y1: int
    x2: int          # exclusive
    y2: int
    area: int
    touches_border: bool

    @property
    def box_area(self) -> int:
        return max(1, (self.x2 - self.x1) * (self.y2 - self.y1))

    @property
    def fill(self) -> float:
        return self.area / self.box_area


def otsu(gray: npt.NDArray[np.float32]) -> float:
    hist, edges = np.histogram(gray, bins=64, range=(0.0, 255.0))
    total = gray.size
    centers = (edges[:-1] + edges[1:]) / 2
    best, best_t = -1.0, 128.0
    w0 = 0.0
    s0 = 0.0
    s_all = float((hist * centers).sum())
    for i in range(len(hist) - 1):
        w0 += float(hist[i])
        s0 += float(hist[i] * centers[i])
        w1 = total - w0
        if w0 == 0 or w1 == 0:
            continue
        m0, m1 = s0 / w0, (s_all - s0) / w1
        between = w0 * w1 * (m0 - m1) ** 2
        if between > best:
            best, best_t = between, float(edges[i + 1])
    return best_t


def ink_mask(img: Image.Image, side: int = WORK_SIDE) -> BoolArray:
    """Dark strokes as True at a working resolution (light-on-dark plans are inverted first)."""
    gray_img = ImageOps.exif_transpose(img).convert("L")
    gray_img.thumbnail((side, side), Image.Resampling.LANCZOS)
    gray = np.asarray(gray_img, dtype=np.float32)
    if float(np.median(gray)) < 110:
        gray = 255 - gray
    return gray < min(otsu(gray), 200.0)


def components(mask: BoolArray) -> list[Component]:
    """4-connected components of True pixels."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out: list[Component] = []
    for sy in range(h):
        row = mask[sy]
        for sx in range(w):
            if not row[sx] or seen[sy, sx]:
                continue
            q: deque[tuple[int, int]] = deque([(sx, sy)])
            seen[sy, sx] = True
            x1, y1, x2, y2, area, border = sx, sy, sx, sy, 0, False
            while q:
                x, y = q.popleft()
                area += 1
                x1, y1, x2, y2 = min(x1, x), min(y1, y), max(x2, x), max(y2, y)
                if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                    border = True
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((nx, ny))
            out.append(Component(x1, y1, x2 + 1, y2 + 1, area, border))
    return out


def _is_outline(mask: BoolArray, c: Component) -> bool:
    """An outlined (not filled) rectangle: its ink lies along the edges of its box."""
    m = mask[c.y1:c.y2, c.x1:c.x2]
    h, w = m.shape
    if h < 5 or w < 5:
        return False
    t = max(1, round(min(h, w) * 0.2))
    edge = np.zeros_like(m)
    edge[:t, :] = edge[-t:, :] = edge[:, :t] = edge[:, -t:] = True
    on_edge = float(m[edge].mean()) if edge.any() else 0.0
    inner = float(m[~edge].mean()) if (~edge).any() else 1.0
    return on_edge > 0.35 and inner < 0.15


def _door(mask: BoolArray, outline: tuple[int, int, int, int]) -> tuple[str, float] | None:
    """The widest break in the outer wall: (side, position along it 0–1)."""
    x1, y1, x2, y2 = outline
    band = 2
    sides = {
        "bottom": mask[max(0, y2 - 1 - band):y2, x1:x2].any(axis=0),
        "top": mask[y1:y1 + band + 1, x1:x2].any(axis=0),
        "left": mask[y1:y2, x1:x1 + band + 1].any(axis=1),
        "right": mask[y1:y2, max(0, x2 - 1 - band):x2].any(axis=1),
    }
    best: tuple[str, float, int] | None = None
    for side, inked in sides.items():
        n = len(inked)
        run, start = 0, 0
        for i in range(1, n - 1):  # corners do not count
            if not inked[i]:
                if run == 0:
                    start = i
                run += 1
                if run >= max(3, int(0.06 * n)) and (best is None or run > best[2]):
                    best = (side, (start + run / 2) / n, run)
            else:
                run = 0
    return (best[0], best[1]) if best else None


def _classify(x1: float, y1: float, x2: float, y2: float, door: tuple[str, float] | None) -> FixtureKind:
    near = 0.08
    w, h = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if door is not None and max(w, h) < 0.2:
        side, pos = door
        dx, dy = {"bottom": (pos, 1.0), "top": (pos, 0.0), "left": (0.0, pos), "right": (1.0, pos)}[side]
        if abs(cx - dx) + abs(cy - dy) < 0.45:
            return "counter"
    if y1 < near:
        return "fridge"
    if x1 < near or x2 > 1 - near or y2 > 1 - near:
        return "shelf"
    return "gondola"


def classic_read(img: Image.Image) -> FloorPlanReading:
    mask = ink_mask(img)
    h, w = mask.shape
    ink = components(mask)
    if not ink:
        raise ValueError("no drawing found on the image")
    walls = max(ink, key=lambda c: c.box_area)
    ox1, oy1, ox2, oy2 = walls.x1, walls.y1, walls.x2, walls.y2
    ow, oh = max(1, ox2 - ox1), max(1, oy2 - oy1)
    min_area = max(6, int(0.002 * ow * oh))
    rects: list[tuple[int, int, int, int]] = []
    for c in ink:
        if c is walls or c.area < min_area or c.box_area < 2 * min_area:
            continue
        inside = c.x1 >= ox1 and c.x2 <= ox2 and c.y1 >= oy1 and c.y2 <= oy2
        if inside and (c.fill >= 0.5 or _is_outline(mask, c)):
            rects.append((c.x1, c.y1, c.x2, c.y2))
    holes = [c for c in components(~mask) if not c.touches_border and c.area >= min_area
             and c.x1 >= ox1 and c.x2 <= ox2 and c.y1 >= oy1 and c.y2 <= oy2]
    if holes:
        interior = max(holes, key=lambda c: c.area)
        for c in holes:
            if c is not interior and c.fill > 0.55 and c.box_area < 0.4 * ow * oh:
                rects.append((c.x1 - 1, c.y1 - 1, c.x2 + 1, c.y2 + 1))
    door = _door(mask, (ox1, oy1, ox2, oy2))
    fixtures: list[PlanFixture] = []
    for rx1, ry1, rx2, ry2 in sorted(set(rects), key=lambda r: (r[1], r[0])):
        nx1, ny1 = max(0.0, (rx1 - ox1) / ow), max(0.0, (ry1 - oy1) / oh)
        nx2, ny2 = min(1.0, (rx2 - ox1) / ow), min(1.0, (ry2 - oy1) / oh)
        if any(f.x1 <= nx1 and f.y1 <= ny1 and f.x2 >= nx2 and f.y2 >= ny2 for f in fixtures):
            continue  # a box inside a box already found (e.g. hatching)
        fixtures.append(PlanFixture(kind=_classify(nx1, ny1, nx2, ny2, door), x1=nx1, y1=ny1, x2=nx2, y2=ny2))
    notes: list[str] = []
    if door is not None:
        side, pos = door
        dx, dy = {"bottom": (pos, 1.0), "top": (pos, 0.0), "left": (0.0, pos), "right": (1.0, pos)}[side]
        fixtures.append(PlanFixture(kind="entrance", x1=max(0.0, dx - 0.03), y1=max(0.0, dy - 0.03), x2=min(1.0, dx + 0.03), y2=min(1.0, dy + 0.03)))
    else:
        notes.append("no break in the outer wall; the entrance goes to the bottom-left corner")
    long_side = DEFAULT_LONG_SIDE_M
    scale = long_side / max(ow, oh)
    notes.append(f"no scale read from the drawing; the longer side is taken as {long_side:g} m")
    return FloorPlanReading(
        width_m=round(ow * scale, 2), depth_m=round(oh * scale, 2), fixtures=fixtures, reader="classic",
        outline=(ox1 / w, oy1 / h, ox2 / w, oy2 / h), notes=notes,
    )


# ── vision-language model ────────────────────────────────────────────────────────

type ImageCoordinate = Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False)]


class _VLMFixture(BaseModel):
    kind: Literal["shelf", "gondola", "fridge", "freezer", "counter", "entrance"]
    box: list[ImageCoordinate] = Field(min_length=4, max_length=4,
                                      description="[x1, y1, x2, y2] on a 0–1000 scale of the whole image")
    label: str = Field(default="", max_length=60)


class _VLMPlan(BaseModel):
    outline: list[ImageCoordinate] = Field(min_length=4, max_length=4,
                                          description="the store's outer walls as [x1, y1, x2, y2] on a 0–1000 scale")
    width_m: float = Field(default=0.0, ge=0, allow_inf_nan=False,
                           description="outer width in metres if a scale or dimensions are written, else 0")
    depth_m: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    fixtures: list[_VLMFixture] = []

    @model_validator(mode="after")
    def positive_outline(self) -> Self:
        x1, y1, x2, y2 = self.outline
        if x2 <= x1 or y2 <= y1:
            raise ValueError("The outline must run from top-left to bottom-right: x1 < x2 and y1 < y2.")
        return self


PLAN_PROMPT = """You read retail store floor plans: hand sketches, CAD exports or scanned drawings.
Find the store's outer walls and every fixture inside them. Kinds:
- fridge: reach-in coolers / chillers (usually along a wall); freezer: chest or upright freezers
- shelf: a shelf against a wall (one side shopped); gondola: a free-standing double-sided shelf in the floor
- counter: the checkout / cash desk; entrance: the door or opening in the outer wall
Give every box as [x1, y1, x2, y2] on a 0–1000 scale of the whole image (x right, y down).
Every box and outline must contain exactly four finite numbers between 0 and 1000.
The outline runs from top-left to bottom-right: x1 < x2 and y1 < y2.
If the plan writes dimensions or a scale bar, give the outer width and depth in metres; otherwise 0.
Dimensions must be finite and nonnegative; do not use NaN or Infinity.
Copy any category words written on a fixture into label ("drinks", "snacks", "noodles", …), else ""."""


def _unit(v: float) -> float:
    return min(1.0, max(0.0, v))


class PlanLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...


async def vlm_read(llm: PlanLLM, img: Image.Image, *, model: str = "vlm") -> FloorPlanReading:
    url, _ = image_data_url(ImageOps.exif_transpose(img).convert("RGB"), max_side=1280, fmt="JPEG")
    plan = await llm.generate_structured_with_image_async(_VLMPlan, PLAN_PROMPT, "Read this floor plan.", url, max_retries=2, seed=0)
    ox1, oy1, ox2, oy2 = (v / 1000 for v in plan.outline)
    ow, oh = max(1e-3, ox2 - ox1), max(1e-3, oy2 - oy1)
    fixtures: list[PlanFixture] = []
    for f in plan.fixtures:
        x1, y1, x2, y2 = (v / 1000 for v in f.box)
        nx1, nx2 = sorted(((x1 - ox1) / ow, (x2 - ox1) / ow))
        ny1, ny2 = sorted(((y1 - oy1) / oh, (y2 - oy1) / oh))
        fixtures.append(PlanFixture(kind=f.kind, x1=_unit(nx1), y1=_unit(ny1), x2=_unit(nx2), y2=_unit(ny2), label=f.label.strip()))
    notes: list[str] = []
    if plan.width_m > 0 and plan.depth_m > 0:
        width_m, depth_m = plan.width_m, plan.depth_m
    else:
        scale = DEFAULT_LONG_SIDE_M / max(ow, oh)
        width_m, depth_m = round(ow * scale, 2), round(oh * scale, 2)
        notes.append(f"no scale read from the drawing; the longer side is taken as {DEFAULT_LONG_SIDE_M:g} m")
    return FloorPlanReading(width_m=width_m, depth_m=depth_m, fixtures=fixtures, reader=model,
                            outline=(ox1, oy1, ox2, oy2), notes=notes)
