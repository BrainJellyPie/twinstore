"""Annotated capture image: shelf bands, product facings with their labels, and empty gaps."""

import colorsys
import io
import os
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from store_emulator.domain.capture import CaptureResult
from store_emulator.engine.prompting import display_price

from .planogram import display_name

type _Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

# Windows need not live on C:.
_WINDOWS_FONTS = os.environ.get("WINDIR", "C:/Windows").replace("\\", "/") + "/Fonts"
_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    f"{_WINDOWS_FONTS}/malgunbd.ttf",
)


@cache
def _font(size: int) -> _Font:
    for path in _FONTS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def _color(i: int) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb((i * 0.618034) % 1.0, 0.75, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def render_overlay(photo: Image.Image, result: CaptureResult, *, max_side: int = 1600) -> bytes:
    """PNG of the photo with bands (tinted), facings (one colour per product) and gaps (red, hatched)."""
    s = min(1.0, max_side / max(photo.size))
    base = photo.convert("RGB")
    if s < 1.0:
        base = base.resize((round(photo.width * s), round(photo.height * s)), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    small = _font(max(12, round(min(base.size) / 55)))
    for band in result.bands:
        poly = [(x * s, y * s) for x, y in band.polygon]
        if len(poly) == 4:
            fill = (40, 120, 255, 28) if band.index % 2 == 0 else (40, 200, 160, 28)
            draw.polygon(poly, fill=fill, outline=(40, 120, 255, 160))
            draw.text((poly[0][0] + 6, poly[0][1] + 4), f"L{band.level}", font=small, fill=(255, 255, 255, 230),
                      stroke_width=2, stroke_fill=(20, 40, 90, 230))
    for gap in result.gaps:
        b = gap.box
        x1, y1, x2, y2 = b.x1 * s, b.y1 * s, b.x2 * s, b.y2 * s
        draw.rectangle((x1, y1, x2, y2), fill=(230, 40, 40, 50), outline=(230, 40, 40, 255), width=3)
        gw, gh = max(1, round(x2 - x1)), max(1, round(y2 - y1))
        hatch = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        hatch_draw = ImageDraw.Draw(hatch)
        step = max(8, gw // 6)
        for k in range(-gh, gw, step):
            hatch_draw.line((k, gh, k + gh, 0), fill=(230, 40, 40, 140), width=2)
        layer.alpha_composite(hatch, (round(x1), round(y1)))
        draw.text((x1 + 4, y1 + 4), "gap", font=small, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(150, 0, 0, 255))
    for n, item in enumerate(result.items):
        color = _color(n)
        for b in item.boxes:
            draw.rectangle((b.x1 * s, b.y1 * s, b.x2 * s, b.y2 * s), outline=(*color, 255), width=3)
        if not item.boxes:
            continue
        first = min(item.boxes, key=lambda b: b.x1)
        price = display_price(item.price, result.currency) if item.price is not None else "?"
        if item.price_estimated and item.price is not None:
            price = f"~{price}"
        text = f"{display_name(item)[:28]}  {price}" + (f"  ×{item.facings}" if item.facings > 1 else "")
        tx, ty = first.x1 * s + 2, first.y1 * s + 2
        bbox = draw.textbbox((tx, ty), text, font=small)
        draw.rectangle((bbox[0] - 3, bbox[1] - 2, bbox[2] + 3, bbox[3] + 2), fill=(0, 0, 0, 170))
        draw.text((tx, ty), text, font=small, fill=(*color, 255))
    out = Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()
