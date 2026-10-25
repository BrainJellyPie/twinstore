"""Draw a page as the shopper's screen: a browser window (tab, back button, address bar) around the shop.

Every usable control carries a numbered badge ("set-of-mark" prompting): a vision model answers with a number, so
its choice maps to exactly one action, and the same boxes make the screenshot clickable in the app. Rendering is
deterministic for a page and its numbering, so a recorded step always looks the way the shopper saw it.
"""

import base64
import hashlib
import io
import math
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from store_emulator.domain.online import OnlineProduct, OnlineSite, PageKind, Vision
from store_emulator.engine.perception.shelf_render import load_font, wrap_text

from .browser import Card, Control, Grid, Line, Page, Panel, money

type ProductPicture = Callable[[OnlineProduct], Image.Image | None]
type _Font = ImageFont.FreeTypeFont | ImageFont.ImageFont
type Box = tuple[int, int, int, int]
type RGB = tuple[int, int, int]

DESKTOP_WIDTH = 1024
MOBILE_WIDTH = 430
_MAX_HEIGHT = 6000
_CHROME = 80

INK: RGB = (17, 24, 39)
MUTED: RGB = (107, 114, 128)
RULE: RGB = (229, 231, 235)
PAPER: RGB = (255, 255, 255)
SOFT: RGB = (246, 247, 249)
GOOD: RGB = (21, 128, 61)
ALERT: RGB = (185, 28, 28)
BADGE: RGB = (225, 29, 72)


@dataclass(frozen=True)
class Screenshot:
    png: bytes
    width: int
    height: int
    boxes: dict[int, Box]  # control index → (left, top, right, bottom)

    def data_url(self) -> str:
        return "data:image/png;base64," + base64.b64encode(self.png).decode("ascii")

    def scaled_data_url(self, width: int) -> str:
        """The screenshot no wider than `width` (what a model is sent)."""
        if width >= self.width:
            return self.data_url()
        with Image.open(io.BytesIO(self.png)) as source:
            small = source.convert("RGB").resize((width, round(self.height * width / self.width)), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        small.save(out, format="PNG")
        return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def _hex(color: str) -> RGB:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t), round(a[2] + (b[2] - a[2]) * t))


def _tint(name: str) -> RGB:
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    return _mix(((h >> 16) & 255, (h >> 8) & 255, h & 255), PAPER, 0.82)


class _Paint:
    def __init__(self, width: int, scale: float, theme: str) -> None:
        self.w = width
        self.img = Image.new("RGB", (width, _MAX_HEIGHT), PAPER)
        self.d = ImageDraw.Draw(self.img)
        self.k = scale
        self.theme = _hex(theme)
        self.boxes: dict[int, Box] = {}
        self.mobile = width < 700
        self.pad = 14 if self.mobile else 24

    def font(self, size: int, bold: bool = False) -> _Font:
        return load_font(max(8, round(size * self.k)), bold)

    def lh(self, size: int) -> int:
        return round(size * self.k * 1.38)

    def text(self, x: int, y: int, text: str, size: int, color: RGB = INK, bold: bool = False) -> int:
        self.d.text((x, y), text, font=self.font(size, bold), fill=color)
        return y + self.lh(size)

    def width_of(self, text: str, size: int, bold: bool = False) -> int:
        return round(self.d.textlength(text, font=self.font(size, bold)))

    def fit(self, text: str, size: int, width: int, bold: bool = False) -> str:
        lines = self.wrap(text, size, width, 1, bold)
        return lines[0] if lines else ""

    def wrap(self, text: str, size: int, width: int, max_lines: int, bold: bool = False) -> list[str]:
        return wrap_text(self.d, text, self.font(size, bold), max(10, width), max_lines)

    def mark(self, control: Control | None, box: Box) -> None:
        if control is not None:
            self.boxes[control.index] = box

    def button(self, control: Control | None, x: int, y: int, label: str, *, w: int = 0, h: int = 0,
               style: str = "fill", size: int = 15) -> Box:
        h = h or round(40 * self.k)
        w = w or self.width_of(label, size, True) + 36
        box = (x, y, x + w, y + h)
        if style == "fill":
            self.d.rounded_rectangle(box, radius=h // 2, fill=self.theme)
            color = PAPER
        elif style == "dark":
            self.d.rounded_rectangle(box, radius=h // 2, fill=INK)
            color = PAPER
        elif style == "outline":
            self.d.rounded_rectangle(box, radius=h // 2, fill=PAPER, outline=self.theme, width=2)
            color = self.theme
        else:  # link: underlined text, left-aligned after the badge's room
            text = self.fit(label, size, w - 16, True)
            self.d.text((x + 12, y + h // 2), text, font=self.font(size, True), fill=self.theme, anchor="lm")
            tw = self.width_of(text, size, True)
            self.d.line((x + 12, y + h // 2 + self.lh(size) // 2 - 1, x + 12 + tw, y + h // 2 + self.lh(size) // 2 - 1),
                        fill=self.theme, width=1)
            self.mark(control, box)
            return box
        text = self.fit(label, size, w - 20, True)
        self.d.text((x + w // 2, y + h // 2), text, font=self.font(size, True), fill=color, anchor="mm")
        self.mark(control, box)
        return box


# ── icons ──────────────────────────────────────────────────────────────────────


def _icon(d: ImageDraw.ImageDraw, kind: str, box: Box, color: RGB) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    s = min(w, h)
    lw = max(2, s // 12)
    if kind == "menu":
        for i in (-1, 0, 1):
            d.rounded_rectangle((x0 + s * .15, cy + i * s * .28 - lw, x1 - s * .15, cy + i * s * .28 + lw), radius=lw, fill=color)
    elif kind == "search":
        r = s * .3
        d.ellipse((cx - r - s * .08, cy - r - s * .08, cx + r - s * .08, cy + r - s * .08), outline=color, width=lw)
        d.line((cx + r * .55, cy + r * .55, x1 - s * .1, y1 - s * .1), fill=color, width=lw + 1)
    elif kind == "cart":
        d.line((x0 + s * .05, y0 + s * .2, x0 + s * .22, y0 + s * .2, x0 + s * .32, y0 + s * .68, x1 - s * .15, y0 + s * .68,
                x1 - s * .05, y0 + s * .32, x0 + s * .26, y0 + s * .32), fill=color, width=lw, joint="curve")
        for wx in (x0 + s * .38, x1 - s * .22):
            d.ellipse((wx - s * .07, y1 - s * .2, wx + s * .07, y1 - s * .06), fill=color)
    elif kind == "gear":
        r = s * .32
        for i in range(8):
            a = i * math.pi / 4
            d.line((cx + math.cos(a) * r * .6, cy + math.sin(a) * r * .6, cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35),
                   fill=color, width=lw + 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
        d.ellipse((cx - r * .45, cy - r * .45, cx + r * .45, cy + r * .45), fill=PAPER)
    elif kind == "heart":
        r = s * .2
        d.ellipse((cx - 2 * r, cy - 1.4 * r, cx, cy + .6 * r), fill=color)
        d.ellipse((cx, cy - 1.4 * r, cx + 2 * r, cy + .6 * r), fill=color)
        d.polygon([(cx - 1.95 * r, cy - .1 * r), (cx + 1.95 * r, cy - .1 * r), (cx, cy + 2 * r)], fill=color)
    elif kind == "back":
        d.line((x0 + s * .25, cy, x1 - s * .2, cy), fill=color, width=lw + 1)
        d.line((x0 + s * .25, cy, x0 + s * .5, cy - s * .25), fill=color, width=lw + 1)
        d.line((x0 + s * .25, cy, x0 + s * .5, cy + s * .25), fill=color, width=lw + 1)
    elif kind == "forward":
        d.line((x0 + s * .2, cy, x1 - s * .25, cy), fill=color, width=lw + 1)
        d.line((x1 - s * .25, cy, x1 - s * .5, cy - s * .25), fill=color, width=lw + 1)
        d.line((x1 - s * .25, cy, x1 - s * .5, cy + s * .25), fill=color, width=lw + 1)
    elif kind == "reload":
        d.arc((x0 + s * .22, y0 + s * .22, x1 - s * .22, y1 - s * .22), 40, 330, fill=color, width=lw + 1)
        d.polygon([(x1 - s * .2, y0 + s * .2), (x1 - s * .2, y0 + s * .45), (x1 - s * .45, y0 + s * .36)], fill=color)
    elif kind == "lock":
        d.rounded_rectangle((x0 + s * .2, cy - s * .05, x1 - s * .2, y1 - s * .12), radius=2, fill=color)
        d.arc((x0 + s * .3, y0 + s * .1, x1 - s * .3, cy + s * .2), 180, 360, fill=color, width=lw)
    elif kind == "close":
        d.line((x0 + s * .28, y0 + s * .28, x1 - s * .28, y1 - s * .28), fill=color, width=lw)
        d.line((x1 - s * .28, y0 + s * .28, x0 + s * .28, y1 - s * .28), fill=color, width=lw)
    else:
        _glyph(d, kind, box, color)


def _glyph(d: ImageDraw.ImageDraw, kind: str, box: Box, color: RGB) -> None:
    """A simple product picture for products without a photo."""
    x0, y0, x1, y1 = box
    s = min(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    u = s / 10
    if kind == "bottle":
        d.rounded_rectangle((cx - 1.6 * u, cy - 1.5 * u, cx + 1.6 * u, cy + 3.8 * u), radius=u, fill=color)
        d.rectangle((cx - .7 * u, cy - 3.6 * u, cx + .7 * u, cy - 1.4 * u), fill=color)
        d.rectangle((cx - 1.6 * u, cy + .2 * u, cx + 1.6 * u, cy + 1.6 * u), fill=PAPER)
    elif kind == "carton":
        d.polygon([(cx - 2 * u, cy - 1.6 * u), (cx, cy - 3.6 * u), (cx + 2 * u, cy - 1.6 * u), (cx + 2 * u, cy + 3.6 * u),
                   (cx - 2 * u, cy + 3.6 * u)], fill=color)
    elif kind == "cup":
        d.polygon([(cx - 2.4 * u, cy - 2.2 * u), (cx + 2.4 * u, cy - 2.2 * u), (cx + 1.7 * u, cy + 3.2 * u), (cx - 1.7 * u, cy + 3.2 * u)], fill=color)
        d.arc((cx + 1.4 * u, cy - 1.2 * u, cx + 3.6 * u, cy + 1.4 * u), 270, 90, fill=color, width=max(2, round(u * .6)))
    elif kind == "snack":
        d.polygon([(cx - 2.6 * u, cy - 3 * u), (cx + 2.6 * u, cy - 3 * u), (cx + 2.2 * u, cy + 3.4 * u), (cx - 2.2 * u, cy + 3.4 * u)], fill=color)
        d.ellipse((cx - 1.2 * u, cy - .8 * u, cx + 1.2 * u, cy + 1.6 * u), fill=PAPER)
    elif kind == "bowl":
        d.pieslice((cx - 3.4 * u, cy - 2.6 * u, cx + 3.4 * u, cy + 3.4 * u), 0, 180, fill=color)
        d.ellipse((cx - 2.2 * u, cy - 1.6 * u, cx + 2.2 * u, cy + .8 * u), fill=_mix(color, PAPER, .45))
    elif kind == "bread":
        d.rounded_rectangle((cx - 3.2 * u, cy - 1.8 * u, cx + 3.2 * u, cy + 2.4 * u), radius=round(2 * u), fill=color)
        for i in (-1, 0, 1):
            d.line((cx + i * 1.4 * u - .5 * u, cy - .8 * u, cx + i * 1.4 * u + .5 * u, cy + .8 * u), fill=PAPER, width=max(2, round(u * .4)))
    elif kind == "leaf":
        d.chord((cx - 3 * u, cy - 3 * u, cx + 3 * u, cy + 3 * u), 200, 340, fill=color)
        d.chord((cx - 3 * u, cy - 3.6 * u, cx + 3 * u, cy + 2.4 * u), 20, 160, fill=color)
        d.line((cx - 2.6 * u, cy + .8 * u, cx + 2.6 * u, cy - .6 * u), fill=PAPER, width=max(2, round(u * .4)))
    elif kind == "cross":
        d.rounded_rectangle((cx - 1 * u, cy - 3 * u, cx + 1 * u, cy + 3 * u), radius=round(u * .4), fill=color)
        d.rounded_rectangle((cx - 3 * u, cy - 1 * u, cx + 3 * u, cy + 1 * u), radius=round(u * .4), fill=color)
    elif kind == "drop":
        d.ellipse((cx - 2.4 * u, cy - .6 * u, cx + 2.4 * u, cy + 4.2 * u), fill=color)
        d.polygon([(cx, cy - 3.8 * u), (cx - 2.2 * u, cy + 1 * u), (cx + 2.2 * u, cy + 1 * u)], fill=color)
    elif kind == "paw":
        d.ellipse((cx - 2 * u, cy, cx + 2 * u, cy + 3.2 * u), fill=color)
        for dx, dy in ((-2.4, -1.2), (-.9, -2.6), (.9, -2.6), (2.4, -1.2)):
            d.ellipse((cx + dx * u - .8 * u, cy + dy * u - .8 * u, cx + dx * u + .8 * u, cy + dy * u + .8 * u), fill=color)
    elif kind == "star":
        pts = [(cx + math.cos(math.pi / 2 + i * math.pi / 5) * (3.4 if i % 2 == 0 else 1.4) * u,
                cy - math.sin(math.pi / 2 + i * math.pi / 5) * (3.4 if i % 2 == 0 else 1.4) * u) for i in range(10)]
        d.polygon(pts, fill=color)
    elif kind == "block":
        d.rectangle((cx - 3 * u, cy - .4 * u, cx - .2 * u, cy + 3 * u), fill=color)
        d.rectangle((cx + .2 * u, cy - .4 * u, cx + 3 * u, cy + 3 * u), fill=_mix(color, INK, .2))
        d.rectangle((cx - 1.4 * u, cy - 3.4 * u, cx + 1.4 * u, cy - .8 * u), fill=_mix(color, PAPER, .3))
    elif kind == "pencil":
        d.polygon([(cx - 3 * u, cy + 3 * u), (cx - 2.4 * u, cy + 1.2 * u), (cx + 2 * u, cy - 3.2 * u), (cx + 3.2 * u, cy - 2 * u),
                   (cx - 1.2 * u, cy + 2.4 * u)], fill=color)
    elif kind == "device":
        d.rounded_rectangle((cx - 2 * u, cy - 3.6 * u, cx + 2 * u, cy + 3.6 * u), radius=round(u * .8), fill=color)
        d.rectangle((cx - 1.5 * u, cy - 2.8 * u, cx + 1.5 * u, cy + 2.4 * u), fill=_mix(color, PAPER, .7))
    elif kind == "pot":
        d.rounded_rectangle((cx - 3 * u, cy - 1.2 * u, cx + 3 * u, cy + 3 * u), radius=round(u), fill=color)
        d.rectangle((cx - 3.6 * u, cy - 1.8 * u, cx + 3.6 * u, cy - 1 * u), fill=color)
        d.line((cx - 4.6 * u, cy - .2 * u, cx - 3 * u, cy - .2 * u), fill=color, width=max(2, round(u * .6)))
    elif kind == "house":
        d.polygon([(cx - 3.4 * u, cy - .4 * u), (cx, cy - 3.6 * u), (cx + 3.4 * u, cy - .4 * u)], fill=color)
        d.rectangle((cx - 2.6 * u, cy - .6 * u, cx + 2.6 * u, cy + 3.2 * u), fill=color)
        d.rectangle((cx - .8 * u, cy + 1 * u, cx + .8 * u, cy + 3.2 * u), fill=PAPER)
    elif kind == "flower":
        for dx, dy in ((0, -1.6), (1.6, 0), (0, 1.6), (-1.6, 0)):
            d.ellipse((cx + dx * u - 1.4 * u, cy + dy * u - 1.4 * u - u, cx + dx * u + 1.4 * u, cy + dy * u + 1.4 * u - u), fill=color)
        d.ellipse((cx - u, cy - 2 * u, cx + u, cy), fill=_mix(color, INK, .3))
        d.line((cx, cy + .4 * u, cx, cy + 4 * u), fill=GOOD, width=max(2, round(u * .5)))
    elif kind == "shirt":
        d.polygon([(cx - 1.2 * u, cy - 3.2 * u), (cx - 3.6 * u, cy - 2 * u), (cx - 2.8 * u, cy - .2 * u), (cx - 2 * u, cy - .8 * u),
                   (cx - 2 * u, cy + 3.4 * u), (cx + 2 * u, cy + 3.4 * u), (cx + 2 * u, cy - .8 * u), (cx + 2.8 * u, cy - .2 * u),
                   (cx + 3.6 * u, cy - 2 * u), (cx + 1.2 * u, cy - 3.2 * u), (cx, cy - 2.4 * u)], fill=color)
    elif kind == "shoe":
        d.polygon([(cx - 3.6 * u, cy - 1.6 * u), (cx - 1.4 * u, cy - 1.6 * u), (cx - .4 * u, cy - .2 * u), (cx + 2.8 * u, cy + .6 * u),
                   (cx + 3.6 * u, cy + 1.8 * u), (cx - 3.6 * u, cy + 1.8 * u)], fill=color)
        d.rectangle((cx - 3.6 * u, cy + 1.8 * u, cx + 3.6 * u, cy + 2.4 * u), fill=_mix(color, INK, .4))
    elif kind == "gem":
        d.polygon([(cx - 3 * u, cy - 1 * u), (cx - 1.6 * u, cy - 2.6 * u), (cx + 1.6 * u, cy - 2.6 * u), (cx + 3 * u, cy - 1 * u),
                   (cx, cy + 3.4 * u)], fill=color)
        d.line((cx - 3 * u, cy - 1 * u, cx + 3 * u, cy - 1 * u), fill=PAPER, width=max(1, round(u * .3)))
    elif kind == "ball":
        d.ellipse((cx - 3.2 * u, cy - 3.2 * u, cx + 3.2 * u, cy + 3.2 * u), fill=color)
        d.arc((cx - 3.2 * u, cy - 1.4 * u, cx + 3.2 * u, cy + 5 * u), 200, 340, fill=PAPER, width=max(2, round(u * .4)))
    elif kind == "tent":
        d.polygon([(cx - 3.8 * u, cy + 3 * u), (cx, cy - 3.4 * u), (cx + 3.8 * u, cy + 3 * u)], fill=color)
        d.polygon([(cx - 1 * u, cy + 3 * u), (cx, cy + .4 * u), (cx + 1 * u, cy + 3 * u)], fill=PAPER)
    elif kind == "tool":
        d.line((cx - 2.6 * u, cy + 2.6 * u, cx + 1.6 * u, cy - 1.6 * u), fill=color, width=max(3, round(u * 1.2)))
        d.ellipse((cx + .6 * u, cy - 3.6 * u, cx + 3.6 * u, cy - .6 * u), outline=color, width=max(3, round(u * .9)))
    elif kind == "gift":
        d.rectangle((cx - 3 * u, cy - 1 * u, cx + 3 * u, cy + 3.2 * u), fill=color)
        d.rectangle((cx - 3.4 * u, cy - 2 * u, cx + 3.4 * u, cy - .6 * u), fill=color)
        d.rectangle((cx - .5 * u, cy - 2 * u, cx + .5 * u, cy + 3.2 * u), fill=PAPER)
    else:
        d.rounded_rectangle((cx - 3 * u, cy - 2.4 * u, cx + 3 * u, cy + 3 * u), radius=round(u * .6), fill=color)
        d.line((cx - 3 * u, cy - .6 * u, cx + 3 * u, cy - .6 * u), fill=PAPER, width=max(2, round(u * .4)))


def _picture(p: _Paint, product: OnlineProduct, glyph: str, box: Box, picture: ProductPicture | None) -> None:
    tint = _tint(glyph + product.category_id)
    p.d.rounded_rectangle(box, radius=10, fill=tint)
    image = picture(product) if picture is not None else None
    x0, y0, x1, y1 = box
    if image is not None:
        fitted = image.copy()
        fitted.thumbnail((x1 - x0 - 16, y1 - y0 - 16), Image.Resampling.LANCZOS)
        backing = Image.new("RGB", fitted.size, PAPER)
        if fitted.mode == "RGBA":
            backing.paste(fitted, mask=fitted.split()[3])
        else:
            backing.paste(fitted.convert("RGB"))
        ox = x0 + (x1 - x0 - fitted.width) // 2
        oy = y0 + (y1 - y0 - fitted.height) // 2
        p.d.rounded_rectangle(box, radius=10, fill=PAPER, outline=RULE)
        p.img.paste(backing, (ox, oy))
    else:
        side = min(x1 - x0, y1 - y0) * 0.62
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        _glyph(p.d, glyph, (round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2)),
               _mix(tint, INK, 0.45))
    if product.stock == 0:
        overlay = Image.new("RGBA", (x1 - x0, y1 - y0), (255, 255, 255, 150))
        p.img.paste(overlay, (x0, y0), overlay)
        p.d.rounded_rectangle((x0 + 8, (y0 + y1) // 2 - 14, x1 - 8, (y0 + y1) // 2 + 14), radius=8, fill=MUTED)
        p.d.text(((x0 + x1) // 2, (y0 + y1) // 2), "Sold out", font=p.font(14, True), fill=PAPER, anchor="mm")


def _pill(p: _Paint, x: int, y: int, text: str, fill: RGB, color: RGB = PAPER, size: int = 11) -> int:
    w = p.width_of(text, size, True) + 14
    h = p.lh(size) + 4
    p.d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=fill)
    p.d.text((x + w // 2, y + h // 2), text, font=p.font(size, True), fill=color, anchor="mm")
    return x + w + 4


def _stars(p: _Paint, x: int, y: int, rating: float, size: int) -> int:
    full = round(rating)
    text = "★" * full + "☆" * (5 - full)
    p.d.text((x, y), text, font=p.font(size), fill=(234, 179, 8))
    return x + p.width_of(text, size) + 6


# ── page parts ─────────────────────────────────────────────────────────────────


def _chrome(p: _Paint, page: Page) -> int:
    d, w = p.d, p.w
    d.rectangle((0, 0, w, 36), fill=(222, 225, 230))
    tab_w = min(320, w - 40)
    d.rounded_rectangle((8, 6, 8 + tab_w, 44), radius=10, fill=(241, 243, 244))
    d.ellipse((20, 15, 34, 29), fill=p.theme)
    title = p.fit(page.title, 13, tab_w - 80)
    d.text((42, 22), title, font=load_font(13), fill=INK, anchor="lm")
    close = (8 + tab_w - 30, 10, 8 + tab_w - 6, 34)
    _icon(d, "close", close, MUTED)
    p.mark(page.leave, close)
    d.rectangle((0, 36, w, _CHROME), fill=(241, 243, 244))
    back_box = (8, 44, 36, 72)
    _icon(d, "back", back_box, INK if page.back else (189, 193, 198))
    p.mark(page.back, back_box)
    _icon(d, "forward", (40, 44, 68, 72), (189, 193, 198))
    left = 72
    if not p.mobile:
        _icon(d, "reload", (72, 44, 100, 72), MUTED)
        left = 108
    d.rounded_rectangle((left, 43, w - 12, 73), radius=15, fill=PAPER)
    _icon(d, "lock", (left + 8, 48, left + 28, 68), MUTED)
    d.text((left + 32, 58), p.fit(page.url.removeprefix("https://"), 13, w - left - 60), font=load_font(13), fill=INK, anchor="lm")
    d.line((0, _CHROME - 1, w, _CHROME - 1), fill=RULE)
    return _CHROME


def _header(p: _Paint, page: Page, y: int) -> int:
    h = page.header
    d = p.d
    tall = round(64 * p.k) if not p.mobile else round(56 * p.k)
    x = p.pad
    menu_box = (x - 4, y + tall // 2 - 16, x + 28, y + tall // 2 + 16)
    _icon(d, "menu", menu_box, INK)
    p.mark(h.menu, menu_box)
    x += 40
    logo_size = 20 if p.mobile else 24
    logo = p.fit(page.site_name, logo_size, 170 if p.mobile else 240, True)
    lw = p.width_of(logo, logo_size, True)
    d.text((x, y + tall // 2), logo, font=p.font(logo_size, True), fill=p.theme, anchor="lm")
    p.mark(h.home, (x - 4, y + 8, x + lw + 4, y + tall - 8))
    right = p.w - p.pad
    icons: list[tuple[str, Control | None]] = [("gear", h.settings), ("cart", h.cart)]
    if h.wishlist is not None:
        icons.append(("heart", h.wishlist))
    for kind, control in icons:
        box = (right - 34, y + tall // 2 - 17, right, y + tall // 2 + 17)
        _icon(d, kind, box, INK)
        if kind == "cart" and h.cart_count:
            d.ellipse((right - 14, box[1] - 4, right + 4, box[1] + 14), fill=BADGE)
            d.text((right - 5, box[1] + 5), str(h.cart_count), font=load_font(11, True), fill=PAPER, anchor="mm")
        p.mark(control, box)
        right -= 46
    if not p.mobile:
        account = h.account
        aw = p.width_of(account, 13)
        d.text((right - aw, y + tall // 2), account, font=p.font(13), fill=MUTED, anchor="lm")
        right -= aw + 18
        if h.search is not None:
            sx = x + lw + 28
            box = (sx, y + 12, max(sx + 120, right), y + tall - 12)
            d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=SOFT, outline=RULE)
            _icon(d, "search", (box[0] + 10, box[1] + 6, box[0] + 30, box[3] - 6), MUTED)
            d.text((box[0] + 38, (box[1] + box[3]) // 2), p.fit(f"Search {page.site_name}…", 14, box[2] - box[0] - 50),
                   font=p.font(14), fill=MUTED, anchor="lm")
            p.mark(h.search, box)
    y += tall
    if p.mobile and h.search is not None:
        box = (p.pad, y, p.w - p.pad, y + round(40 * p.k))
        d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=SOFT, outline=RULE)
        _icon(d, "search", (box[0] + 10, box[1] + 8, box[0] + 30, box[3] - 8), MUTED)
        d.text((box[0] + 38, (box[1] + box[3]) // 2), f"Search {page.site_name}…", font=p.font(14), fill=MUTED, anchor="lm")
        p.mark(h.search, box)
        y = box[3] + 10
    d.line((0, y, p.w, y), fill=RULE)
    return y + 1


def _nav(p: _Paint, page: Page, y: int) -> int:
    if not page.nav:
        return y
    size = 14
    row_h = round(42 * p.k)
    x = p.pad + 18
    top = y
    p.d.rectangle((0, y, p.w, y + row_h), fill=SOFT)
    for control in page.nav:
        label = control.action.label.removeprefix("Top menu: ")
        tw = p.width_of(label, size, True)
        if x + tw > p.w - p.pad and x > p.pad + 18:
            y += row_h
            x = p.pad + 18
            p.d.rectangle((0, y, p.w, y + row_h), fill=SOFT)
        color = ALERT if label.lower() == "deals" else INK
        p.d.text((x, y + row_h // 2 + 3), label[:1].upper() + label[1:], font=p.font(size, True), fill=color, anchor="lm")
        p.mark(control, (x - 18, y + 8, x + tw + 4, y + row_h - 4))
        x += tw + 34
    y += row_h
    p.d.line((0, y, p.w, y), fill=RULE)
    return y + 1 if y > top else y


def _notice(p: _Paint, page: Page, y: int) -> int:
    if not page.notice:
        return y
    bad = any(w in page.notice.lower() for w in ("not valid", "sold out", "no account", "type something"))
    h = round(36 * p.k)
    p.d.rectangle((0, y, p.w, y + h), fill=(254, 226, 226) if bad else (220, 252, 231))
    p.d.text((p.pad, y + h // 2), p.fit(page.notice, 14, p.w - 2 * p.pad), font=p.font(14, True),
             fill=ALERT if bad else GOOD, anchor="lm")
    return y + h


def _banner(p: _Paint, page: Page, y: int) -> int:
    if page.banner is None:
        return y
    headline, small, cta = page.banner
    h = round((128 if p.mobile else 150) * p.k)
    box = (p.pad, y, p.w - p.pad, y + h)
    p.d.rounded_rectangle(box, radius=18, fill=p.theme)
    p.d.polygon([(box[2] - 260, box[1]), (box[2] - 150, box[1]), (box[2] - 300, box[3]), (box[2] - 410, box[3])],
                fill=_mix(p.theme, PAPER, 0.18))
    lines = p.wrap(headline, 26 if p.mobile else 30, box[2] - box[0] - 48, 2, True)
    ty = box[1] + 18
    for line in lines:
        ty = p.text(box[0] + 24, ty, line, 26 if p.mobile else 30, PAPER, True)
    p.text(box[0] + 24, ty + 2, p.fit(small, 14, box[2] - box[0] - 48), 14, _mix(PAPER, p.theme, 0.15))
    if cta is not None:
        label = "Shop now"
        bw = p.width_of(label, 14, True) + 34
        bx, by = box[2] - bw - 22, box[3] - round(40 * p.k) - 16
        p.d.rounded_rectangle((bx, by, bx + bw, by + round(40 * p.k)), radius=round(20 * p.k), fill=PAPER)
        p.d.text((bx + bw // 2, by + round(20 * p.k)), label, font=p.font(14, True), fill=p.theme, anchor="mm")
        p.mark(cta, (bx, by, bx + bw, by + round(40 * p.k)))
    return box[3] + 18


def _card_height(p: _Paint, cw: int, grid: Grid, flags: tuple[bool, bool, bool]) -> int:
    ratings, extras, quick = flags
    img = min(190, round(cw * 0.74))
    h = img + 10 + p.lh(14) * 2 + p.lh(17) + 8
    if any(c.sponsored for c in grid.cards):
        h += p.lh(11)
    if ratings:
        h += p.lh(12)
    if extras:
        h += p.lh(11)
    if quick:
        h += round(34 * p.k) + 8
    return h + 10


def _card(p: _Paint, site: OnlineSite, card: Card, box: Box, picture: ProductPicture | None,
          flags: tuple[bool, bool, bool]) -> None:
    ratings, _, quick = flags
    urgency, social = site.options.urgency, site.options.social_proof
    category = site.category(card.product.category_id)
    glyph = category.glyph if category else "box"
    x0, y0, x1, y1 = box
    p.d.rounded_rectangle(box, radius=14, fill=PAPER, outline=RULE)
    product = card.product
    img = min(190, round((x1 - x0) * 0.74))
    _picture(p, product, glyph, (x0 + 8, y0 + 8, x1 - 8, y0 + img), picture)
    bx = x0 + 14
    if product.discount_percent:
        bx = _pill(p, bx, y0 + 14, f"-{product.discount_percent}%", ALERT)
    if "bestseller" in product.badges:
        bx = _pill(p, bx, y0 + 14, "Best seller", (217, 119, 6))
    elif "new" in product.badges:
        bx = _pill(p, bx, y0 + 14, "New", (37, 99, 235))
    if "eco" in product.badges and bx < x1 - 50:
        _pill(p, bx, y0 + 14, "Eco", GOOD)
    y = y0 + img + 8
    tx, tw = x0 + 12, x1 - x0 - 24
    if card.sponsored:
        y = p.text(tx, y, "Sponsored", 11, MUTED, True)
    for line in p.wrap(product.name, 14, tw, 2):
        y = p.text(tx, y, line, 14)
    if len(p.wrap(product.name, 14, tw, 2)) == 1:
        y += p.lh(14)
    if ratings:
        sx = _stars(p, tx, y, product.rating, 12)
        p.d.text((sx, y), p.fit(f"{product.rating:.1f} ({product.reviews:,})", 12, x1 - sx - 10), font=p.font(12), fill=MUTED)
        y += p.lh(12)
    price = money(product.price, site)
    p.d.text((tx, y), price, font=p.font(17, True), fill=ALERT if product.discount_percent else INK)
    if product.discount_percent:
        px = tx + p.width_of(price, 17, True) + 8
        was = money(product.list_price, site)
        p.d.text((px, y + 4), was, font=p.font(12), fill=MUTED)
        ww = p.width_of(was, 12)
        p.d.line((px, y + 4 + p.lh(12) // 2, px + ww, y + 4 + p.lh(12) // 2), fill=MUTED, width=1)
    y += p.lh(17)
    extra = ""
    if urgency and product.stock is not None and 0 < product.stock <= 5:
        extra = f"Only {product.stock} left!"
    elif social and product.weekly_sales:
        extra = f"{product.weekly_sales:,} bought this week"
    if extra:
        p.text(tx, y, p.fit(extra, 11, tw), 11, ALERT if extra.startswith("Only") else (180, 83, 9), True)
    if quick and card.quick_add is not None:
        bh = round(34 * p.k)
        p.button(card.quick_add, x0 + 10, y1 - bh - 10, "Add to cart", w=x1 - x0 - 20, h=bh, style="outline", size=13)
        p.mark(card.open, (x0, y0, x1, y1 - bh - 14))
    else:
        p.mark(card.open, box)


def _grid(p: _Paint, site: OnlineSite, grid: Grid, y: int, picture: ProductPicture | None) -> int:
    o = site.options
    columns = 2 if p.mobile else o.grid_columns
    x0 = p.pad
    y = p.text(x0, y, grid.title, 20, INK, True) + 2
    if grid.note:
        y = p.text(x0, y, p.fit(grid.note, 13, p.w - 2 * p.pad), 13, MUTED) + 4
    if grid.controls:
        x = x0
        for control in grid.controls:
            label = control.action.label
            w = p.width_of(label, 12, True) + 26
            if x + w > p.w - p.pad:
                x = x0
                y += round(32 * p.k) + 6
            p.button(control, x, y, label, w=w, h=round(30 * p.k), style="outline", size=12)
            x += w + 8
        y += round(30 * p.k) + 12
    if not grid.cards:
        return y + 8
    gap = 12 if p.mobile else 16
    cw = (p.w - 2 * p.pad - gap * (columns - 1)) // columns
    flags = (o.show_ratings, o.urgency or o.social_proof, o.quick_add and any(c.quick_add for c in grid.cards))
    ch = _card_height(p, cw, grid, flags)
    for i, card in enumerate(grid.cards):
        row, col = divmod(i, columns)
        cx = x0 + col * (cw + gap)
        cy = y + row * (ch + gap)
        _card(p, site, card, (cx, cy, cx + cw, cy + ch), picture, flags)
    rows = (len(grid.cards) + columns - 1) // columns
    return y + rows * (ch + gap) + 10


_LINE_COLORS: dict[str, RGB] = {"muted": MUTED, "alert": ALERT, "good": GOOD}


def _line(p: _Paint, line: Line, x: int, y: int, width: int) -> int:
    if line.control is not None:
        style = "fill" if line.style == "strong" else "outline" if line.style == "text" else "link"
        h = round((42 if style == "fill" else 34) * p.k)
        w = min(width, max(200, p.width_of(line.text, 15, True) + 40)) if style != "link" else min(width, p.width_of(line.text, 14, True) + 32)
        p.button(line.control, x, y, line.text, w=w, h=h, style=style, size=15 if style == "fill" else 14)
        return y + h + 8
    size = {"title": 20, "total": 19, "price": 22}.get(line.style, 14)
    bold = line.style in ("title", "total", "price", "strong", "alert", "good")
    color = _LINE_COLORS.get(line.style, INK)
    for text in p.wrap(line.text, size, width, 4, bold):
        y = p.text(x, y, text, size, color, bold)
    return y + 4


def _panel_height(p: _Paint, panel: Panel, width: int) -> int:
    probe = _Paint(width + 40, p.k, "#000000")
    y = probe.text(0, 0, panel.title, 18, INK, True) + 6
    for line in panel.lines:
        y = _line(probe, line, 0, y, width)
    return y + 36


def _panel(p: _Paint, panel: Panel, box_x: int, y: int, width: int) -> int:
    if panel.chips:
        y = p.text(box_x, y, panel.title, 20, INK, True) + 4
        x = box_x
        h = round(44 * p.k)
        for line in panel.lines:
            w = p.width_of(line.text, 14, True) + 56
            if x + w > box_x + width:
                x = box_x
                y += h + 10
            p.d.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=SOFT, outline=RULE)
            _glyph(p.d, "box", (x + 8, y + 8, x + h - 8, y + h - 8), p.theme)
            p.d.text((x + h, y + h // 2), line.text, font=p.font(14, True), fill=INK, anchor="lm")
            p.mark(line.control, (x, y, x + w, y + h))
            x += w + 10
        return y + h + 22
    height = _panel_height(p, panel, width - 40)
    p.d.rounded_rectangle((box_x, y, box_x + width, y + height), radius=16, fill=PAPER, outline=RULE)
    iy = p.text(box_x + 20, y + 16, panel.title, 18, INK, True) + 6
    for line in panel.lines:
        iy = _line(p, line, box_x + 20, iy, width - 40)
    return y + height + 16


def _detail(p: _Paint, site: OnlineSite, page: Page, y: int, picture: ProductPicture | None) -> int:
    detail = page.detail
    if detail is None:
        return p.text(p.pad, y + 20, "This product is no longer available.", 16, MUTED) + 20
    product = detail.product
    if detail.breadcrumb is not None:
        label = "‹ " + detail.breadcrumb.action.label.removeprefix("Category: ")
        w = p.width_of(label, 13, True)
        p.d.text((p.pad, y), label, font=p.font(13, True), fill=p.theme)
        p.mark(detail.breadcrumb, (p.pad - 4, y - 4, p.pad + w + 4, y + p.lh(13) + 2))
        y += p.lh(13) + 10
    if p.mobile:
        side = p.w - 2 * p.pad
        img_box = (p.pad, y, p.pad + side, y + round(side * 0.8))
        cx, cy, cw = p.pad, img_box[3] + 14, side
    else:
        img_box = (p.pad, y, p.pad + 400, y + 400)
        cx, cy, cw = p.pad + 424, y, p.w - p.pad * 2 - 424
    category = site.category(product.category_id)
    _picture(p, product, category.glyph if category else "box", img_box, picture)
    ty = cy
    for line in p.wrap(product.name, 24, cw, 3, True):
        ty = p.text(cx, ty, line, 24, INK, True)
    ty += 4
    bx = cx
    if product.discount_percent:
        bx = _pill(p, bx, ty, f"-{product.discount_percent}%", ALERT, size=12)
    if "bestseller" in product.badges:
        bx = _pill(p, bx, ty, "Best seller", (217, 119, 6), size=12)
    if "new" in product.badges:
        bx = _pill(p, bx, ty, "New", (37, 99, 235), size=12)
    if bx != cx:
        ty += p.lh(12) + 10
    for line in detail.facts:
        if line.text.endswith("stars") or " out of 5 stars" in line.text:
            sx = _stars(p, cx, ty, product.rating, 15)
            p.d.text((sx, ty), p.fit(line.text, 14, cx + cw - sx), font=p.font(14), fill=MUTED)
            ty += p.lh(15) + 4
            continue
        ty = _line(p, line, cx, ty, cw)
    ty += 6
    for control in detail.buttons:
        kind = control.action.kind.value
        label = control.action.label.split(":")[0] if kind in ("add_to_cart", "buy_now") else control.action.label
        style = {"add_to_cart": "fill", "buy_now": "dark", "add_to_wishlist": "outline"}.get(kind, "link")
        w = min(cw, 300) if style != "link" else p.width_of(label, 14, True) + 32
        box = p.button(control, cx, ty, label, w=w, h=round((46 if style != "link" else 32) * p.k), style=style,
                       size=16 if style != "link" else 14)
        ty = box[3] + 10
    for line in detail.reviews:
        ty = _line(p, line, cx, ty, cw)
    return max(ty, img_box[3]) + 22


def _footer(p: _Paint, page: Page, y: int) -> int:
    h = round(58 * p.k)
    p.d.rectangle((0, y, p.w, y + h), fill=SOFT)
    p.d.line((0, y, p.w, y), fill=RULE)
    x = p.pad
    for control in page.footer:
        label = control.action.label.removeprefix("Footer: ").capitalize()
        w = p.width_of(label, 13, True)
        p.d.text((x, y + h // 2), label, font=p.font(13, True), fill=INK, anchor="lm")
        p.mark(control, (x - 4, y + 10, x + w + 4, y + h - 10))
        x += w + 24
    if page.trust:
        _icon(p.d, "lock", (x, y + h // 2 - 10, x + 20, y + h // 2 + 10), GOOD)
        p.d.text((x + 24, y + h // 2), "Secure checkout", font=p.font(12, True), fill=GOOD, anchor="lm")
    if not p.mobile:
        mark = f"© 2026 {page.site_name}"
        p.d.text((p.w - p.pad - p.width_of(mark, 12), y + h // 2), mark, font=p.font(12), fill=MUTED, anchor="lm")
    return y + h


def _cookie(p: _Paint, page: Page, y: int) -> int:
    if page.cookie is None:
        return y
    accept, reject = page.cookie
    h = round((104 if p.mobile else 66) * p.k)
    p.d.rectangle((0, y, p.w, y + h), fill=(31, 41, 55))
    text = "We use cookies to improve your shopping experience."
    p.d.text((p.pad, y + 14 if p.mobile else y + h // 2), p.fit(text, 13, p.w - 2 * p.pad if p.mobile else p.w - 420),
             font=p.font(13), fill=PAPER, anchor="la" if p.mobile else "lm")
    bh = round(36 * p.k)
    by = y + h - bh - 12 if p.mobile else y + (h - bh) // 2
    right = p.w - p.pad
    rw = p.width_of("Reject non-essential", 13, True) + 28
    p.button(reject, right - rw, by, "Reject non-essential", w=rw, h=bh, style="outline", size=13)
    aw = p.width_of("Accept all", 13, True) + 28
    p.button(accept, right - rw - aw - 10, by, "Accept all", w=aw, h=bh, style="fill", size=13)
    return y + h


def _shade(img: Image.Image, top: int) -> None:
    veil = Image.new("RGBA", (img.width, img.height - top), (15, 23, 42, 120))
    img.paste(veil, (0, top), veil)


def _overlay(p: _Paint, page: Page, height: int) -> None:
    overlay = page.overlay
    if overlay is None:
        return
    _shade(p.img, _CHROME)
    if overlay.kind == "menu":
        w = min(320, round(p.w * 0.82))
        p.d.rectangle((0, _CHROME, w, height), fill=PAPER)
        y = p.text(20, _CHROME + 16, overlay.title, 20, INK, True) + 8
        for line in overlay.lines:
            if line.control is None:
                continue
            h = round(40 * p.k)
            label = line.control.action.label.removeprefix("Menu: ")
            label = "Close menu" if line.control.action.kind.value == "close_menu" else label
            p.d.text((36, y + h // 2), p.fit(label[:1].upper() + label[1:], 15, w - 56), font=p.font(15, line.style == "strong"),
                     fill=MUTED if line.style == "muted" else INK, anchor="lm")
            p.mark(line.control, (10, y, w - 10, y + h))
            p.d.line((20, y + h, w - 20, y + h), fill=RULE)
            y += h + 2
        return
    w = min(460, p.w - 2 * p.pad)
    x0 = (p.w - w) // 2
    probe_lines = [line for line in overlay.lines if line.control is None]
    h = 70 + sum(p.lh(15) * len(p.wrap(line.text, 15, w - 48, 3)) for line in probe_lines) + round(110 * p.k)
    y0 = _CHROME + 90
    p.d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=20, fill=PAPER)
    p.d.rectangle((x0, y0, x0 + w, y0 + 8), fill=p.theme)
    y = p.text(x0 + 24, y0 + 24, p.fit(overlay.title, 20, w - 48, True), 20, INK, True) + 6
    for line in probe_lines:
        for text in p.wrap(line.text, 15, w - 48, 3):
            y = p.text(x0 + 24, y, text, 15, MUTED)
    y += 10
    for line in overlay.lines:
        if line.control is None:
            continue
        if line.style == "strong":
            box = p.button(line.control, x0 + 24, y, line.text, w=w - 48, h=round(44 * p.k), style="fill")
        else:
            box = p.button(line.control, x0 + 24, y, line.text, w=w - 48, h=round(34 * p.k), style="link", size=14)
        y = box[3] + 6


def _badges(p: _Paint, numbers: dict[int, int]) -> None:
    font = load_font(13, True)
    for index, number in numbers.items():
        box = p.boxes.get(index)
        if box is None:
            continue
        text = str(number)
        w = round(p.d.textlength(text, font=font)) + 10
        h = 19
        x = min(max(1, box[0] - 5), p.img.width - w - 1)
        y = min(max(1, box[1] - 7), p.img.height - h - 1)
        p.d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=BADGE, outline=PAPER, width=2)
        p.d.text((x + w // 2, y + h // 2), text, font=font, fill=PAPER, anchor="mm")


def render_page(page: Page, site: OnlineSite, numbers: dict[int, int], picture: ProductPicture | None = None) -> Screenshot:
    """`page` of `site`, with the badge number of each usable control in `numbers` (see browser.numbering)."""
    width = MOBILE_WIDTH if page.device == "mobile" else DESKTOP_WIDTH
    p = _Paint(width, 1.25 if page.large_text else 1.0, page.theme)
    y = _chrome(p, page)
    y = _header(p, page, y)
    y = _nav(p, page, y)
    y = _notice(p, page, y) + 18
    y = _banner(p, page, y)
    if page.kind == PageKind.PRODUCT:
        y = _detail(p, site, page, y, picture)
    side_by_side = page.kind == PageKind.CART and len(page.panels) == 2 and not p.mobile
    if side_by_side:
        left_w = round((p.w - 2 * p.pad) * 0.58)
        y_left = _panel(p, page.panels[0], p.pad, y, left_w - 8)
        y_right = _panel(p, page.panels[1], p.pad + left_w + 8, y, p.w - 2 * p.pad - left_w - 8)
        y = max(y_left, y_right)
    else:
        narrow = page.kind in (PageKind.CART, PageKind.SIGN_IN, PageKind.CHECKOUT, PageKind.ORDER_COMPLETE,
                               PageKind.HELP, PageKind.SETTINGS)
        width_used = min(680, p.w - 2 * p.pad) if narrow else p.w - 2 * p.pad
        x = (p.w - width_used) // 2 if narrow else p.pad
        for panel in page.panels:
            if panel.chips:
                y = _panel(p, panel, p.pad, y, p.w - 2 * p.pad)
            else:
                y = _panel(p, panel, x, y, width_used)
    for grid in page.grids:
        y = _grid(p, site, grid, y, picture)
    y = max(y + 10, 420)
    if page.chat:
        p.d.ellipse((p.w - p.pad - 52, y - 62, p.w - p.pad, y - 10), fill=p.theme)
        p.d.text((p.w - p.pad - 26, y - 36), "?", font=load_font(24, True), fill=PAPER, anchor="mm")
    y = _footer(p, page, y)
    y = _cookie(p, page, y)
    height = min(y, _MAX_HEIGHT)
    p.img = p.img.crop((0, 0, width, height))
    p.d = ImageDraw.Draw(p.img)
    _overlay(p, page, height)
    _badges(p, numbers)
    out = io.BytesIO()
    p.img.save(out, format="PNG", compress_level=6)
    usable = {index: box for index, box in p.boxes.items() if index in numbers}
    return Screenshot(out.getvalue(), width, height, usable)



# Red–green colour blindness (deuteranopia) in sRGB, after Viénot, Brettel & Mollon (1999); an approximation for
# showing a model what such a shopper can tell apart, not a clinical simulation.
_DEUTERANOPIA = (0.625, 0.375, 0.0, 0.0, 0.7, 0.3, 0.0, 0.0, 0.0, 0.3, 0.7, 0.0)


def see_as(shot: Screenshot, vision: Vision, *, large_text: bool = False) -> Screenshot:
    """The screenshot as a shopper with this eyesight sees it: blurred and flatter for low vision (less so with large
    text switched on), slightly blurred and yellowed for older eyes, red–green shifted for colour blindness."""
    if vision == "typical":
        return shot
    with Image.open(io.BytesIO(shot.png)) as source:
        image = source.convert("RGB")
    if vision == "color_blind":
        image = image.convert("RGB", _DEUTERANOPIA)
    elif vision == "low_vision":
        image = image.filter(ImageFilter.GaussianBlur(1.6 if large_text else 2.8))
        image = ImageEnhance.Contrast(image).enhance(0.72)
    else:
        image = image.filter(ImageFilter.GaussianBlur(0.8 if large_text else 1.4))
        image = ImageEnhance.Contrast(image).enhance(0.85)
        r, g, b = image.split()
        image = Image.merge("RGB", (r, g, b.point([round(v * 0.82) for v in range(256)])))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return Screenshot(out.getvalue(), shot.width, shot.height, shot.boxes)
