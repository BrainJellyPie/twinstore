"""Render one rack face as the shopper standing in front of it would see it.

The image is a front elevation of the face: four shelf levels (top = level 4),
packages with their product names, shelf-edge price tags, promotion ribbons, and
a numbered badge on every product ("set-of-mark" prompting). The badge numbers
are how a vision-language model answers ("item 7"), so its reply maps back to
an exact SKU without fuzzy name matching.

Rendering is deterministic for a given (rack, face, currency, width, mark order),
which keeps VLM responses cacheable and paired layout comparisons exact.
"""

import base64
import colorsys
import hashlib
import io
import os
import random
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType, Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.engine.prompting import display_price
from store_emulator.engine.perception.product_images import ProductImageLoader, default_product_image

type _Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

# Windows need not live on C:.
_WINDOWS_FONTS = os.environ.get("WINDIR", "C:/Windows").replace("\\", "/") + "/Fonts"
# Fonts with Hangul coverage first, so Korean product names render too.
_REGULAR_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    f"{_WINDOWS_FONTS}/malgun.ttf",
)
_BOLD_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    f"{_WINDOWS_FONTS}/malgunbd.ttf",
    *_REGULAR_FONTS,
)


@cache
def load_font(size: int, bold: bool = False) -> _Font:
    for path in _BOLD_FONTS if bold else _REGULAR_FONTS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


@dataclass(frozen=True)
class MarkedItem:
    mark: int
    slot: Slot
    item: SlotItem


@dataclass(frozen=True)
class ShelfView:
    rack: Rack
    face: Face
    items: tuple[MarkedItem, ...]
    png: bytes
    size: tuple[int, int]

    def by_mark(self, mark: int) -> MarkedItem | None:
        return next((m for m in self.items if m.mark == mark), None)

    def data_url(self) -> str:
        return "data:image/png;base64," + base64.b64encode(self.png).decode("ascii")


def face_slots(rack: Rack, face: Face) -> list[list[tuple[Slot, SlotItem]]]:
    """Items on one face, as rows from the top level down, each row left to right."""
    cells = rack.block_cells
    # Along-face order: N/S faces run along x (column), E/W faces along y (row).
    def along(slot: Slot) -> int:
        if not 0 <= slot.block < len(cells):
            return slot.block
        r, c = cells[slot.block]
        return c if face in (Face.N, Face.S) else r

    rows: list[list[tuple[Slot, SlotItem]]] = []
    for level in range(RACK_LEVELS, 0, -1):
        slots = sorted((s for s in rack.slots if s.face == face and s.level == level), key=along)
        rows.append([(slot, item) for slot in slots for item in slot.items])
    return rows


def _package_color(name: str) -> tuple[int, int, int]:
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    hue = (h % 360) / 360.0
    sat = 0.45 + ((h >> 9) % 30) / 100.0
    val = 0.62 + ((h >> 15) % 25) / 100.0
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return int(r * 255), int(g * 255), int(b * 255)


def text_color(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    luminance = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    return (20, 20, 20) if luminance > 150 else (255, 255, 255)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: _Font, width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
        # A single word wider than the box (long Korean names have no spaces) is cut by characters.
        while draw.textlength(line, font=font) > width and len(line) > 1:
            cut = len(line)
            while cut > 1 and draw.textlength(line[:cut], font=font) > width:
                cut -= 1
            lines.append(line[:cut])
            line = line[cut:]
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def render_face(
    rack: Rack,
    face: Face,
    *,
    currency: str = "USD",
    width: int = 768,
    rng: random.Random | None = None,
    number_on_tag: bool = True,
    image_loader: ProductImageLoader | None = None,
) -> ShelfView:
    """Render a rack face. With `rng`, badge numbers are a random permutation of 1..N.

    `number_on_tag` repeats the badge number on the price tag ("#7  $2.49"): small VLMs
    read text far more reliably than they localize a badge, so this ties number, name
    and price together on the line the model actually reads.
    """
    if width < 128:
        raise ValueError("Shelf charts need a width of at least 128 pixels")
    shelf_rows = face_slots(rack, face)
    flat = [entry for row in shelf_rows for entry in row]
    marks = list(range(1, len(flat) + 1))
    if rng is not None:
        rng.shuffle(marks)

    margin, frame, header = 14, 10, 46
    inner_w = width - 2 * margin - 2 * frame
    max_columns = max(1, inner_w // 120)
    rows = [(RACK_LEVELS - level, row[start:start + max_columns])
            for level, row in enumerate(shelf_rows)
            for start in range(0, max(1, len(row)), max_columns)]
    columns = max(1, max((len(row) for _, row in rows), default=1))
    cell_w = inner_w // columns
    pkg_h = max(100, min(170, int(cell_w * 0.78)))
    tag_h = max(44 if any(item.regular_price > item.price for _, item in flat) else 26, cell_w // 6)
    level_h = 18
    row_h = level_h + pkg_h + tag_h + 10
    height = margin * 2 + header + frame * 2 + row_h * len(rows)

    fridge = rack.type == RackType.FRIDGE
    img = Image.new("RGB", (width, height), (238, 234, 226))
    draw = ImageDraw.Draw(img)

    # Unit frame and header sign.
    body = (margin, margin + header, width - margin, height - margin)
    draw.rounded_rectangle(body, radius=8, fill=(214, 228, 240) if fridge else (226, 216, 200),
                           outline=(70, 78, 90) if fridge else (96, 74, 52), width=frame)
    sign_font = load_font(22, bold=True)
    kind = "Fridge" if fridge else "Shelf"
    title = rack.rack_name or kind
    draw.rounded_rectangle((margin, margin, width - margin, margin + header - 6), radius=6, fill=(38, 50, 66))
    draw.text((margin + 14, margin + (header - 6) // 2), f"{title}", font=sign_font, fill=(255, 255, 255), anchor="lm")
    draw.text((width - margin - 14, margin + (header - 6) // 2), kind, font=load_font(16), fill=(190, 205, 220), anchor="rm")

    name_size = max(12, min(18, cell_w // 10))
    mark_size = max(14, min(20, cell_w // 8))
    promo_size = max(11, name_size - 3)
    name_font = load_font(name_size, bold=True)
    price_font = load_font(max(13, min(20, tag_h - 8)), bold=True)
    mark_font = load_font(mark_size, bold=True)
    promo_font = load_font(promo_size, bold=True)

    top = body[1] + frame
    left = body[0] + frame
    index = 0
    for r, (level, row) in enumerate(rows):
        y0 = top + r * row_h + level_h
        draw.text((left + 4, y0 - level_h), f"Level {level}", font=load_font(12), fill=(65, 65, 65))
        board_y = y0 + 6 + pkg_h
        # Shelf board with the price-tag strip.
        draw.rectangle((left, board_y, left + inner_w, board_y + tag_h), fill=(250, 250, 248) if fridge else (245, 240, 230))
        draw.line((left, board_y, left + inner_w, board_y), fill=(120, 120, 120), width=2)
        for c, entry in enumerate(row):
            _, item = entry
            mark = marks[index]
            index += 1
            x0 = left + c * cell_w + 6
            x1 = left + (c + 1) * cell_w - 6
            color = _package_color(item.name)
            package = (image_loader or default_product_image)(item)
            if package is not None:
                # The product's own package art, standing on the shelf; its name stays readable underneath.
                art = package.copy()
                caption_h = (name_size + 3) * 2 + 6
                art.thumbnail((max(1, x1 - x0 - 8), max(1, pkg_h - caption_h - 8)))
                art = art.convert("RGBA")
                img.paste(art, ((x0 + x1) // 2 - art.width // 2, board_y - caption_h - art.height), art)
                names = wrap_text(draw, item.name or item.sku, name_font, x1 - x0 - 8, max_lines=2)
                for line, name in enumerate(names):
                    draw.text(((x0 + x1) // 2, board_y - caption_h + 3 + line * (name_size + 3)), name,
                              font=name_font, fill=(30, 30, 34), anchor="mt")
            else:
                draw.rounded_rectangle((x0, y0 + 6, x1, board_y - 2), radius=10, fill=color, outline=(40, 40, 40), width=2)
                lines = wrap_text(draw, item.name, name_font, x1 - x0 - 14, max_lines=4)
                line_h = name_size + 3
                ty = y0 + 6 + (pkg_h - line_h * len(lines)) // 2 + 6
                for i, line in enumerate(lines):
                    draw.text(((x0 + x1) // 2, ty + i * line_h), line, font=name_font, fill=text_color(color), anchor="mt")
            if item.promo:
                ribbon = wrap_text(draw, item.promo.strip()[:12].upper(), promo_font, x1 - x0 - 14, max_lines=1)
                ribbon_text = ribbon[0] if ribbon else ""
                rw = min(x1 - x0, int(draw.textlength(ribbon_text, font=promo_font)) + 12)
                draw.rectangle((x1 - rw, y0 + 8, x1 - 2, y0 + 8 + promo_size + 6), fill=(214, 32, 39))
                draw.text((x1 - rw // 2 - 1, y0 + 11), ribbon_text, font=promo_font, fill=(255, 255, 255), anchor="mt")
            # Price tag on the shelf edge.
            price = display_price(item.price, currency)
            if number_on_tag:
                price = f"#{mark}  {price}"
            tag_font = price_font
            for size in range(max(13, min(20, tag_h - 8)), 9, -1):
                tag_font = load_font(size, bold=True)
                if draw.textlength(price, font=tag_font) <= x1 - x0 - 6:
                    break
            price = wrap_text(draw, price, tag_font, x1 - x0 - 6, max_lines=1)[0]
            pw = min(x1 - x0, int(draw.textlength(price, font=tag_font)) + 8)
            px = (x0 + x1) // 2 - pw // 2
            draw.rectangle((px, board_y + 3, px + pw, board_y + tag_h - 3), fill=(255, 221, 64), outline=(60, 60, 60))
            discounted = item.regular_price > item.price
            draw.text(((x0 + x1) // 2, board_y + (14 if discounted else tag_h // 2)), price, font=tag_font, fill=(0, 0, 0), anchor="mm")
            if discounted:
                previous = wrap_text(draw, f"was {display_price(item.regular_price, currency)}", load_font(10), x1 - x0 - 6, max_lines=1)[0]
                draw.text(((x0 + x1) // 2, board_y + 31), previous, font=load_font(10), fill=(40, 40, 40), anchor="mm")
            # Number badge.
            rad = max(13, mark_size - 2, int(draw.textlength(str(mark), font=mark_font) / 2) + 4)
            cx, cy = x0 + rad - 2, y0 + rad + 2
            draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(0, 0, 0), outline=(255, 255, 255), width=2)
            draw.text((cx, cy), str(mark), font=mark_font, fill=(255, 255, 255), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)
    items = tuple(sorted(
        (MarkedItem(mark=marks[i], slot=e[0], item=e[1]) for i, e in enumerate(flat)), key=lambda m: m.mark,
    ))
    return ShelfView(rack=rack, face=face, items=items, png=buf.getvalue(), size=(width, height))
