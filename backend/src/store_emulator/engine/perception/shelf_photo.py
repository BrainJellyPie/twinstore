"""Photographs of rack faces from the 3D store, shown to vision shoppers above the shelf chart.

The browser renders each stocked face of a layout in Realistic mode, straight on from a shopper's eye
height, and reports where every product sits in the picture. A face is stored under a key computed
from what it shows (the rack's products, prices, promotions and fixture, the face and the currency), so
an edited rack is rendered again and a run never shows a picture of an older layout.

At a glance the photo gets the chart's own badge numbers on yellow tags and is stacked above the chart:
the photo for what catches the eye, the chart for names and prices the model can read.
"""

import hashlib
import io
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

from store_emulator.domain.rack import Rack, Slot
from store_emulator.domain.types import Face

from .shelf_render import MarkedItem, ShelfView, load_font

# Bumped when the browser's renderer changes what a face looks like, so stored pictures are renewed.
RENDER_VERSION = "shelf-photo-1"
MAX_SIDE = 2048
MAX_BYTES = 4_000_000
_KEY = re.compile(r"^[0-9a-f]{64}$")

type Box = tuple[float, float, float, float]


def item_ref(slot: Slot, index: int) -> str:
    """One product of one slot: the browser tags its boxes with the same reference."""
    return f"{slot.face.value}:{slot.level}:{slot.block}:{index}"


def face_key(rack: Rack, face: Face, currency: str) -> str:
    """What a picture of this face depends on; the rack's position and shopper timings do not change it."""
    shown = rack.model_dump(mode="json", include={"id", "type", "shape", "rotation", "levels", "rack_name",
                                                  "design_variant", "slots"})
    payload = json.dumps([RENDER_VERSION, face.value, currency.upper(), shown], sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def stocked_faces(rack: Rack) -> list[Face]:
    return [face for face in Face if any(s.face == face and s.items for s in rack.slots)]


@dataclass(frozen=True)
class ShelfPhoto:
    image: Image.Image
    boxes: dict[str, tuple[Box, ...]]


def _paths(directory: Path, key: str) -> tuple[Path, Path]:
    return directory / f"{key}.jpg", directory / f"{key}.json"


def save_shelf_photo(directory: Path, key: str, image_bytes: bytes, boxes: dict[str, list[Box]]) -> tuple[int, int]:
    """Stores a face picture (JPEG or PNG) as JPEG with its product boxes. ValueError on bad input."""
    if not _KEY.match(key):
        raise ValueError("invalid face key")
    if len(image_bytes) > MAX_BYTES:
        raise ValueError("the picture is larger than 4 MB")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as e:
        raise ValueError("the picture could not be read") from e
    if img.format not in ("JPEG", "PNG") or max(img.size) > MAX_SIDE or min(img.size) < 64:
        raise ValueError("the picture must be a JPEG or PNG between 64 and 2048 pixels a side")
    w, h = img.size
    clean: dict[str, list[list[float]]] = {}
    for ref, items in boxes.items():
        kept = [[max(0.0, min(w, x1)), max(0.0, min(h, y1)), max(0.0, min(w, x2)), max(0.0, min(h, y2))]
                for x1, y1, x2, y2 in items[:24]]
        kept = [b for b in kept if b[2] - b[0] >= 2 and b[3] - b[1] >= 2]
        if kept:
            clean[ref[:40]] = kept
    directory.mkdir(parents=True, exist_ok=True)
    jpg, meta = _paths(directory, key)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    jpg.write_bytes(buf.getvalue())
    meta.write_text(json.dumps({"size": [w, h], "boxes": clean}), encoding="utf-8")
    load_shelf_photo.cache_clear()
    return w, h


@lru_cache(maxsize=256)
def load_shelf_photo(directory: str, key: str) -> ShelfPhoto | None:
    if not directory or not _KEY.match(key):
        return None
    jpg, meta = _paths(Path(directory), key)
    if not jpg.is_file() or not meta.is_file():
        return None
    try:
        img = Image.open(jpg)
        img.load()
        data = json.loads(meta.read_text(encoding="utf-8"))
        boxes = {str(ref): tuple((float(b[0]), float(b[1]), float(b[2]), float(b[3])) for b in items)
                 for ref, items in dict(data.get("boxes") or {}).items()}
    except (OSError, ValueError, TypeError, IndexError):
        return None
    return ShelfPhoto(image=img.convert("RGB"), boxes=boxes)


def has_shelf_photo(directory: Path, key: str) -> bool:
    jpg, meta = _paths(directory, key)
    return jpg.is_file() and meta.is_file()


def _ref_of(marked: MarkedItem) -> str:
    return item_ref(marked.slot, marked.slot.items.index(marked.item))


def photo_chart_view(chart: ShelfView, photo: ShelfPhoto, *, width: int | None = None) -> ShelfView:
    """The photo with the chart's numbers on yellow tags, stacked above the chart, as one view.

    The view keeps the chart's marks, so the model's "#N" maps to the same product either way."""
    width = width or chart.size[0]
    scale = width / photo.image.width
    img = photo.image.resize((width, max(1, round(photo.image.height * scale))), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(img)
    font = load_font(max(11, width // 40), bold=True)
    for marked in chart.items:
        boxes = photo.boxes.get(_ref_of(marked))
        if not boxes:
            continue
        x1, _, x2, y2 = boxes[0]
        # The number only: products stand close together on a photo, and the price is on the shelf tag and the chart.
        text = f"#{marked.mark}"
        left, top, right, bottom = d.textbbox((0, 0), text, font=font)
        tw, th = right - left, bottom - top
        cx = (x1 + x2) / 2 * scale
        y = min(img.height - th - 6, y2 * scale - th * 0.4)
        tx = max(1.0, min(img.width - tw - 8, cx - tw / 2 - 4))
        d.rounded_rectangle((tx + 1, y + 2, tx + tw + 9, y + th + 7), radius=3, fill=(0, 0, 0))
        d.rounded_rectangle((tx, y, tx + tw + 8, y + th + 5), radius=3, fill=(255, 220, 40), outline=(120, 95, 0))
        d.text((tx + 4 - left, y + 2 - top), text, font=font, fill=(15, 15, 15))
    chart_img = Image.open(io.BytesIO(chart.png)).convert("RGB")
    if chart_img.width != width:
        chart_img = chart_img.resize((width, max(1, round(chart_img.height * width / chart_img.width))),
                                     Image.Resampling.LANCZOS)
    gap = 8
    out = Image.new("RGB", (width, img.height + gap + chart_img.height), (24, 24, 28))
    out.paste(img, (0, 0))
    out.paste(chart_img, (0, img.height + gap))
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return ShelfView(rack=chart.rack, face=chart.face, items=chart.items, png=buf.getvalue(), size=out.size)
