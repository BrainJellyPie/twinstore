"""Draw a page as the shopper's screen: a browser window (tab, back button, address bar) around the shop.

Every usable control carries a numbered badge ("set-of-mark" prompting): a vision model answers with a number, so
its choice maps to exactly one action, and the same boxes make the screenshot clickable in the app. Rendering is
deterministic for a page and its numbering, so a recorded step always looks the way the shopper saw it.
"""

import base64
import colorsys
import hashlib
import io
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from store_emulator.domain.online import OnlineProduct, OnlineSite, PageKind, PageStyle, Vision
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


def _luma(c: RGB) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255


def _on(fill: RGB) -> RGB:
    """Text colour that reads on `fill`."""
    return PAPER if _luma(fill) < 0.7 else INK


def _readable(color: RGB, ground: RGB) -> RGB:
    """`color`, lightened or darkened just enough to stand apart from `ground` (a theme colour on a dark page)."""
    toward = PAPER if _luma(ground) < 0.5 else INK
    for t in (0.0, 0.2, 0.4, 0.6, 0.8):
        shade = _mix(color, toward, t)
        if abs(_luma(shade) - _luma(ground)) >= 0.3:
            return shade
    return toward


def _hue(color: RGB, turn: float) -> RGB:
    h, l, sat = colorsys.rgb_to_hls(*(v / 255 for v in color))
    r, g, b = colorsys.hls_to_rgb((h + turn) % 1.0, l, sat)
    return round(r * 255), round(g * 255), round(b * 255)


def _tint(name: str, ground: RGB = PAPER) -> RGB:
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    return _mix(((h >> 16) & 255, (h >> 8) & 255, h & 255), ground, 0.82 if _luma(ground) > 0.5 else 0.7)


@dataclass(frozen=True)
class _Style:
    """How a shop's pages look. The browser window around them and the numbered badges never change."""
    paper: RGB = PAPER  # page background
    surface: RGB = PAPER  # cards, panels and popups
    ink: RGB = INK
    muted: RGB = MUTED
    rule: RGB = RULE
    soft: RGB = SOFT  # nav row, footer, search box
    good: RGB = GOOD
    alert: RGB = ALERT
    radius: float = 1.0  # corner radii, relative to the classic look (0 = square)
    pill: bool = True  # buttons and search boxes fully rounded
    outline: int = 1  # card and panel border width (0 = none)
    edge: RGB | None = None  # border colour (None = rule)
    shadow: int = 0  # hard offset shadow under cards and buttons, in pixels
    shade: RGB = INK  # its colour
    header: Literal["light", "theme", "dark", "centered"] = "light"
    bar: RGB = (19, 25, 33)  # header colour of a dark header
    nav: Literal["soft", "theme", "dark", "underline"] = "soft"
    banner: Literal["stripe", "gradient", "outline", "dots", "framed", "neon", "wave", "bevel"] = "stripe"
    display: Literal["sans", "serif", "mono"] = "sans"  # type of the logo, headings and prices
    caps: bool = False  # menu labels and headings in capitals
    ink_buttons: bool = False  # main buttons in ink instead of the theme colour
    space: float = 1.0  # gaps between cards
    glow: bool = False  # a neon halo around theme-coloured edges
    bevel: bool = False  # raised 3-D edges on buttons and cards
    bleed: bool = False  # product pictures run to the card's edges
    center: bool = False  # product names and prices centred under the picture

    @property
    def dark(self) -> bool:
        return _luma(self.paper) < 0.5


STYLES: dict[PageStyle, _Style] = {
    "classic": _Style(),
    "minimal": _Style(ink=(23, 23, 23), muted=(115, 115, 115), rule=(236, 236, 236), soft=(250, 250, 250), radius=0.25,
                      pill=False, outline=0, nav="underline", banner="outline", caps=True, ink_buttons=True, space=1.4,
                      bleed=True),
    "luxury": _Style(paper=(250, 247, 242), surface=(255, 253, 249), ink=(28, 25, 23), muted=(120, 113, 108),
                     rule=(226, 219, 207), soft=(243, 238, 229), radius=0, pill=False, header="dark", bar=(17, 16, 15),
                     nav="underline", banner="framed", display="serif", caps=True, ink_buttons=True, space=1.3,
                     center=True),
    "brutalist": _Style(paper=(255, 252, 228), ink=(0, 0, 0), muted=(55, 55, 55), rule=(0, 0, 0), soft=(255, 236, 140),
                        radius=0, pill=False, outline=3, shadow=6, shade=(0, 0, 0), nav="dark", bar=(0, 0, 0),
                        banner="outline", display="mono", caps=True),
    "playful": _Style(paper=(255, 249, 244), ink=(45, 35, 62), muted=(122, 110, 138), rule=(240, 228, 242),
                      soft=(255, 240, 232), radius=1.8, outline=2, edge=(246, 214, 236), shadow=5, shade=(250, 222, 240),
                      nav="theme", banner="dots"),
    "marketplace": _Style(paper=(234, 237, 237), ink=(15, 17, 17), muted=(86, 89, 89), rule=(213, 217, 217),
                          soft=(243, 243, 243), radius=0.35, pill=False, header="dark", bar=(19, 25, 33), nav="dark",
                          banner="gradient", space=0.6),
    "editorial": _Style(ink=(17, 17, 17), muted=(98, 98, 98), rule=(17, 17, 17), soft=(247, 245, 240), radius=0,
                        pill=False, outline=0, header="centered", nav="underline", banner="outline", display="serif",
                        caps=True, ink_buttons=True, space=1.5, bleed=True, center=True),
    "neon": _Style(paper=(9, 10, 16), surface=(20, 22, 33), ink=(236, 239, 247), muted=(148, 156, 178), rule=(42, 46, 64),
                   soft=(15, 17, 26), good=(74, 222, 128), alert=(255, 99, 132), radius=1.0, edge=(52, 58, 84),
                   header="dark", bar=(13, 14, 22), nav="dark", banner="neon", glow=True),
    "retro": _Style(paper=(192, 192, 192), surface=(212, 208, 200), ink=(0, 0, 0), muted=(64, 64, 64),
                    rule=(128, 128, 128), soft=(200, 200, 200), radius=0, pill=False, header="theme", banner="bevel",
                    display="mono", bevel=True, space=0.8),
    "organic": _Style(paper=(246, 243, 233), surface=(252, 250, 243), ink=(42, 50, 36), muted=(112, 116, 98),
                      rule=(226, 220, 203), soft=(238, 233, 217), radius=1.6, nav="soft", banner="wave", display="serif"),
    "tech": _Style(paper=(247, 249, 252), ink=(15, 23, 42), muted=(100, 116, 139), rule=(226, 232, 240),
                   soft=(241, 245, 249), radius=0.8, pill=False, edge=(226, 232, 240), shadow=3, shade=(226, 232, 240),
                   nav="underline", banner="gradient"),
}

_WINDOWS_FONTS = os.environ.get("WINDIR", "C:/Windows").replace("\\", "/") + "/Fonts"
_DISPLAY_FONTS: dict[tuple[str, bool], tuple[str, ...]] = {
    ("serif", False): ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
                       "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
                       "/System/Library/Fonts/Supplemental/Georgia.ttf", f"{_WINDOWS_FONTS}/georgia.ttf"),
    ("serif", True): ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                      "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
                      "/System/Library/Fonts/Supplemental/Georgia Bold.ttf", f"{_WINDOWS_FONTS}/georgiab.ttf"),
    ("mono", False): ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                      "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                      "/System/Library/Fonts/Menlo.ttc", f"{_WINDOWS_FONTS}/consola.ttf"),
    ("mono", True): ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                     "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
                     "/System/Library/Fonts/Menlo.ttc", f"{_WINDOWS_FONTS}/consolab.ttf"),
}


@cache
def _display_font(family: str, size: int, bold: bool) -> _Font:
    """A serif or monospaced face for headings, or the usual sans when the machine has none."""
    for path in _DISPLAY_FONTS.get((family, bold), ()):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return load_font(size, bold)


def _latin(text: str) -> bool:
    """Text a Latin display face can set; Hangul, kana and CJK stay in the sans face, which covers them."""
    return all(ord(ch) < 0x2E80 for ch in text)


class _Paint:
    def __init__(self, width: int, scale: float, theme: str, style: _Style = STYLES["classic"]) -> None:
        self.w = width
        self.s = style
        self.img = Image.new("RGB", (width, _MAX_HEIGHT), style.paper)
        self.d = ImageDraw.Draw(self.img)
        self.k = scale
        self.theme = _hex(theme)
        self.accent = _readable(self.theme, style.paper)  # the theme colour as text or lines on the page
        self.boxes: dict[int, Box] = {}
        self.mobile = width < 700
        self.pad = 14 if self.mobile else 24

    def font(self, size: int, bold: bool = False, display: bool = False, text: str = "") -> _Font:
        size = max(8, round(size * self.k))
        if display and self.s.display != "sans" and _latin(text):
            return _display_font(self.s.display, size, bold)
        return load_font(size, bold)

    def lh(self, size: int) -> int:
        return round(size * self.k * 1.38)

    def text(self, x: int, y: int, text: str, size: int, color: RGB | None = None, bold: bool = False,
             display: bool = False) -> int:
        self.d.text((x, y), text, font=self.font(size, bold, display, text), fill=color or self.s.ink)
        return y + self.lh(size)

    def width_of(self, text: str, size: int, bold: bool = False, display: bool = False) -> int:
        return round(self.d.textlength(text, font=self.font(size, bold, display, text)))

    def fit(self, text: str, size: int, width: int, bold: bool = False, display: bool = False) -> str:
        lines = self.wrap(text, size, width, 1, bold, display)
        return lines[0] if lines else ""

    def wrap(self, text: str, size: int, width: int, max_lines: int, bold: bool = False, display: bool = False) -> list[str]:
        return wrap_text(self.d, text, self.font(size, bold, display, text), max(10, width), max_lines)

    def caps(self, text: str) -> str:
        return text.upper() if self.s.caps else text

    def mark(self, control: Control | None, box: Box) -> None:
        if control is not None:
            self.boxes[control.index] = box

    def radius(self, classic: int) -> int:
        return round(classic * self.s.radius)

    def frame(self, box: Box, radius: int, fill: RGB, *, outline: RGB | None = None, width: int = 1,
              lift: bool = True) -> None:
        """A filled shape with the style's hard shadow, neon halo and bevel."""
        s = self.s
        x0, y0, x1, y1 = box
        if lift and s.shadow:
            self.d.rounded_rectangle((x0 + s.shadow, y0 + s.shadow, x1 + s.shadow, y1 + s.shadow), radius=radius, fill=s.shade)
        if lift and s.glow:
            for grow, t in ((5, 0.86), (3, 0.72), (1, 0.5)):
                self.d.rounded_rectangle((x0 - grow, y0 - grow, x1 + grow, y1 + grow), radius=radius + grow,
                                         outline=_mix(self.theme, s.paper, t), width=2)
        self.d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
        if lift and s.bevel:
            light, dark = _mix(fill, PAPER, 0.75), _mix(fill, (0, 0, 0), 0.55)
            self.d.line((x0, y1 - 1, x0, y0, x1 - 1, y0), fill=light, width=2)
            self.d.line((x0 + 1, y1 - 1, x1 - 1, y1 - 1, x1 - 1, y0 + 1), fill=dark, width=2)

    def button(self, control: Control | None, x: int, y: int, label: str, *, w: int = 0, h: int = 0,
               style: str = "fill", size: int = 15) -> Box:
        s = self.s
        h = h or round(40 * self.k)
        w = w or self.width_of(label, size, True) + 36
        box = (x, y, x + w, y + h)
        radius = h // 2 if s.pill else self.radius(8)
        if style == "fill":
            fill = s.ink if s.ink_buttons else self.theme
            self.frame(box, radius, fill)
            color = _on(fill)
        elif style == "dark":
            self.frame(box, radius, s.ink)
            color = _on(s.ink)
        elif style == "outline":
            self.frame(box, radius, s.surface, outline=self.accent, width=max(2, s.outline))
            color = self.accent
        else:  # link: underlined text, left-aligned after the badge's room
            text = self.fit(label, size, w - 16, True)
            self.d.text((x + 12, y + h // 2), text, font=self.font(size, True), fill=self.accent, anchor="lm")
            tw = self.width_of(text, size, True)
            self.d.line((x + 12, y + h // 2 + self.lh(size) // 2 - 1, x + 12 + tw, y + h // 2 + self.lh(size) // 2 - 1),
                        fill=self.accent, width=1)
            self.mark(control, box)
            return box
        text = self.fit(label, size, w - 20, True)
        self.d.text((x + w // 2, y + h // 2), text, font=self.font(size, True), fill=color, anchor="mm")
        self.mark(control, box)
        return box


# ── icons ──────────────────────────────────────────────────────────────────────


def _icon(d: ImageDraw.ImageDraw, kind: str, box: Box, color: RGB, hole: RGB = PAPER) -> None:
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
        d.ellipse((cx - r * .45, cy - r * .45, cx + r * .45, cy + r * .45), fill=hole)
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
    tint = _tint(glyph + product.category_id, p.s.surface)
    radius = p.radius(10)
    p.d.rounded_rectangle(box, radius=radius, fill=tint)
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
        p.d.rounded_rectangle(box, radius=radius, fill=PAPER, outline=p.s.rule)
        p.img.paste(backing, (ox, oy))
    else:
        side = min(x1 - x0, y1 - y0) * 0.62
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        _glyph(p.d, glyph, (round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2)),
               _mix(tint, PAPER if p.s.dark else INK, 0.45))
    if product.stock == 0:
        overlay = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 150) if p.s.dark else (255, 255, 255, 150))
        p.img.paste(overlay, (x0, y0), overlay)
        p.d.rounded_rectangle((x0 + 8, (y0 + y1) // 2 - 14, x1 - 8, (y0 + y1) // 2 + 14), radius=8, fill=MUTED)
        p.d.text(((x0 + x1) // 2, (y0 + y1) // 2), "Sold out", font=p.font(14, True), fill=PAPER, anchor="mm")


def _pill(p: _Paint, x: int, y: int, text: str, fill: RGB, color: RGB = PAPER, size: int = 11) -> int:
    w = p.width_of(text, size, True) + 14
    h = p.lh(size) + 4
    p.d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2 if p.s.pill else min(h // 2, p.radius(6)), fill=fill)
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


def _search_box(p: _Paint, page: Page, box: Box, on_bar: bool, long: bool) -> None:
    s = p.s
    radius = (box[3] - box[1]) // 2 if s.pill else p.radius(8)
    if on_bar:
        p.d.rounded_rectangle(box, radius=radius, fill=PAPER)
    else:
        p.d.rounded_rectangle(box, radius=radius, fill=s.soft, outline=s.rule, width=max(1, min(2, s.outline)))
    color = MUTED if on_bar else s.muted
    _icon(p.d, "search", (box[0] + 10, box[1] + (6 if long else 8), box[0] + 30, box[3] - (6 if long else 8)), color)
    label = f"Search {page.site_name}…"
    p.d.text((box[0] + 38, (box[1] + box[3]) // 2), p.fit(label, 14, box[2] - box[0] - 50) if long else label,
             font=p.font(14), fill=color, anchor="lm")
    p.mark(page.header.search, box)


def _header(p: _Paint, page: Page, y: int) -> int:
    h = page.header
    d, s = p.d, p.s
    tall = round(64 * p.k) if not p.mobile else round(56 * p.k)
    # A coloured header (dark, or the theme) carries light text; a light one shows the logo in the theme colour.
    bar = p.theme if s.header == "theme" else s.bar if s.header == "dark" else s.paper
    on_bar = s.header in ("theme", "dark")
    fg = _on(bar) if on_bar else s.ink
    d.rectangle((0, y + 1, p.w, y + tall), fill=bar)  # the browser bar's last row stays
    if s.bevel and on_bar:
        d.rectangle((0, y, p.w, y + tall), fill=_mix(bar, (0, 0, 0), 0.15))
        d.rectangle((0, y, p.w, y + tall // 2), fill=bar)
    x = p.pad
    menu_box = (x - 4, y + tall // 2 - 16, x + 28, y + tall // 2 + 16)
    _icon(d, "menu", menu_box, fg)
    p.mark(h.menu, menu_box)
    x += 40
    logo_size = 20 if p.mobile else 24
    if s.header == "centered" and not p.mobile:
        logo_size = 30
    logo = p.fit(page.site_name, logo_size, 170 if p.mobile else 240, True, display=True)
    lw = p.width_of(logo, logo_size, True, display=True)
    if s.header == "centered":
        x = (p.w - lw) // 2
    d.text((x, y + tall // 2), logo, font=p.font(logo_size, True, True, logo), fill=fg if on_bar else p.accent, anchor="lm")
    p.mark(h.home, (x - 4, y + 8, x + lw + 4, y + tall - 8))
    right = p.w - p.pad
    icons: list[tuple[str, Control | None]] = [("gear", h.settings), ("cart", h.cart)]
    if h.wishlist is not None:
        icons.append(("heart", h.wishlist))
    for kind, control in icons:
        box = (right - 34, y + tall // 2 - 17, right, y + tall // 2 + 17)
        _icon(d, kind, box, fg, hole=bar)
        if kind == "cart" and h.cart_count:
            d.ellipse((right - 14, box[1] - 4, right + 4, box[1] + 14), fill=BADGE)
            d.text((right - 5, box[1] + 5), str(h.cart_count), font=load_font(11, True), fill=PAPER, anchor="mm")
        p.mark(control, box)
        right -= 46
    # The search box sits in the header row on desktop, or on its own row on phones and in a centred header.
    own_row = p.mobile or s.header == "centered"
    if not p.mobile:
        account = h.account
        aw = p.width_of(account, 13)
        if s.header != "centered":
            d.text((right - aw, y + tall // 2), account, font=p.font(13), fill=_mix(fg, bar, 0.35) if on_bar else s.muted,
                   anchor="lm")
            right -= aw + 18
        if h.search is not None and not own_row:
            sx = x + lw + 28
            _search_box(p, page, (sx, y + 12, max(sx + 120, right), y + tall - 12), on_bar, True)
    y += tall
    if own_row and h.search is not None:
        row = round(40 * p.k)
        if on_bar:
            d.rectangle((0, y, p.w, y + row + 10), fill=bar)
        width = p.w - 2 * p.pad if p.mobile else min(560, p.w - 2 * p.pad)
        left = p.pad if p.mobile else (p.w - width) // 2
        _search_box(p, page, (left, y, left + width, y + row), on_bar, not p.mobile)
        y += row + 10
    d.line((0, y, p.w, y), fill=s.rule, width=max(1, s.outline if s.outline > 1 else 1))
    return y + 1


def _nav(p: _Paint, page: Page, y: int) -> int:
    if not page.nav:
        return y
    s = p.s
    size = 14
    row_h = round(42 * p.k)
    x = p.pad + 18
    top = y
    fill = p.theme if s.nav == "theme" else _mix(s.bar, PAPER, 0.1) if s.nav == "dark" else s.paper if s.nav == "underline" else s.soft
    ink = _on(fill) if s.nav in ("theme", "dark") else s.ink
    deals = (250, 204, 21) if ink == PAPER and s.nav in ("theme", "dark") else s.alert
    p.d.rectangle((0, y, p.w, y + row_h), fill=fill)
    for control in page.nav:
        raw = control.action.label.removeprefix("Top menu: ")
        label = p.caps(raw[:1].upper() + raw[1:])
        tw = p.width_of(label if s.caps else raw, size, True)
        if x + tw > p.w - p.pad and x > p.pad + 18:
            y += row_h
            x = p.pad + 18
            p.d.rectangle((0, y, p.w, y + row_h), fill=fill)
        color = deals if label.lower() == "deals" else ink
        p.d.text((x, y + row_h // 2 + 3), label, font=p.font(size, True), fill=color, anchor="lm")
        p.mark(control, (x - 18, y + 8, x + tw + 4, y + row_h - 4))
        x += tw + 34
    y += row_h
    p.d.line((0, y, p.w, y), fill=s.rule)
    return y + 1 if y > top else y


def _notice(p: _Paint, page: Page, y: int) -> int:
    if not page.notice:
        return y
    s = p.s
    bad = any(w in page.notice.lower() for w in ("not valid", "sold out", "no account", "type something"))
    h = round(36 * p.k)
    if s.dark:
        fill = _mix(s.alert if bad else s.good, s.paper, 0.78)
    else:
        fill = (254, 226, 226) if bad else (220, 252, 231)
    p.d.rectangle((0, y, p.w, y + h), fill=fill)
    p.d.text((p.pad, y + h // 2), p.fit(page.notice, 14, p.w - 2 * p.pad), font=p.font(14, True),
             fill=s.alert if bad else s.good, anchor="lm")
    return y + h


def _banner_ground(p: _Paint, box: Box, radius: int) -> tuple[RGB, RGB]:
    """Paint the banner's background in the style's way; returns the headline and the small-print colours."""
    s, d = p.s, p.d
    x0, y0, x1, y1 = box
    kind = s.banner
    if kind == "outline":
        p.frame(box, radius, s.surface, outline=p.accent if s.outline < 2 else s.ink, width=max(2, s.outline))
        d.rectangle((x0 + 24, y1 - 22, x0 + 84, y1 - 18), fill=p.accent)
        return s.ink, s.muted
    if kind == "framed":
        dark = s.bar
        d.rectangle(box, fill=dark)
        d.rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), outline=_readable(p.theme, dark), width=1)
        return (250, 247, 240), _mix((250, 247, 240), dark, 0.35)
    if kind == "neon":
        p.frame(box, radius, s.surface, outline=p.accent, width=2)
        return _mix(p.accent, PAPER, 0.25), s.muted
    if kind == "gradient":
        strip = Image.new("RGB", (2, 1))
        strip.putpixel((0, 0), p.theme)
        strip.putpixel((1, 0), _mix(_hue(p.theme, -0.08), (0, 0, 0), 0.3))
        ground = strip.resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR)
        mask = Image.new("L", ground.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, ground.width - 1, ground.height - 1), radius=radius, fill=255)
        p.img.paste(ground, (x0, y0), mask)
        return PAPER, _mix(PAPER, p.theme, 0.15)
    p.frame(box, radius, p.theme)
    if kind == "dots":
        dot = _mix(p.theme, PAPER, 0.2)
        for row, cy in enumerate(range(y0 + 16, y1 - 8, 22)):
            for cx in range(x1 - 300 + (row % 2) * 11, x1 - 12, 22):
                d.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=dot)
    elif kind == "wave":
        layer = Image.new("RGB", (x1 - x0, y1 - y0), p.theme)
        ld = ImageDraw.Draw(layer)
        w, h = layer.size
        ld.ellipse((w - 420, h - 40, w + 140, h + 260), fill=_mix(p.theme, PAPER, 0.16))
        ld.ellipse((w - 220, -90, w + 80, 110), fill=_mix(p.theme, PAPER, 0.08))
        mask = Image.new("L", layer.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
        p.img.paste(layer, (x0, y0), mask)
    else:  # stripe and bevel
        d.polygon([(x1 - 260, y0), (x1 - 150, y0), (x1 - 300, y1), (x1 - 410, y1)], fill=_mix(p.theme, PAPER, 0.18))
    return _on(p.theme), _mix(_on(p.theme), p.theme, 0.15)


def _banner(p: _Paint, page: Page, y: int, picture: ProductPicture | None) -> int:
    if page.banner is None:
        return y
    s = p.s
    banner = page.banner
    headline, small, cta = banner.headline, banner.small, banner.control
    h = round((176 if p.mobile and cta is not None else 128 if p.mobile else 150) * p.k)
    box = (p.pad, y, p.w - p.pad, y + h)
    ink, faint = _banner_ground(p, box, p.radius(18))
    label = p.caps("Shop now")
    bw, bh = p.width_of(label, 14, True) + 34, round(40 * p.k)
    text_w = box[2] - box[0] - 48 - (bw + 24 if cta is not None and not p.mobile else 0)
    if banner.product is not None:
        side = h - 24
        _picture(p, banner.product, "box", (box[2] - side - 150, box[1] + 12, box[2] - 150, box[1] + 12 + side), picture)
        text_w -= side + 150
    if banner.sponsored:
        _pill(p, box[2] - 110, box[1] + 12, "Sponsored", _mix(INK, PAPER, 0.25), size=11)
    size = 26 if p.mobile else 30
    lines = p.wrap(headline, size, text_w, 2, True, display=True)
    ty = box[1] + 18
    for line in lines:
        ty = p.text(box[0] + 24, ty, line, size, ink, True, display=True)
    p.text(box[0] + 24, ty + 2, p.fit(small, 14, text_w), 14, faint)
    if cta is not None:
        bx, by = (box[0] + 24 if p.mobile else box[2] - bw - 22), box[3] - bh - 16
        on_theme = s.banner in ("stripe", "dots", "wave", "bevel", "gradient")
        fill = PAPER if on_theme or s.banner == "framed" else s.ink if s.ink_buttons else p.theme
        color = p.theme if on_theme else _on(fill)
        p.frame((bx, by, bx + bw, by + bh), round(20 * p.k) if s.pill else p.radius(8), fill)
        p.d.text((bx + bw // 2, by + bh // 2), label, font=p.font(14, True), fill=color, anchor="mm")
        p.mark(cta, (bx, by, bx + bw, by + bh))
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
    st = p.s
    p.frame(box, p.radius(14), st.surface, outline=(st.edge or st.rule) if st.outline else None, width=max(1, st.outline))
    product = card.product
    img = min(190, round((x1 - x0) * 0.74))
    inset = 0 if st.bleed else 8
    _picture(p, product, glyph, (x0 + inset, y0 + inset, x1 - inset, y0 + img), picture)
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

    def left(width: int) -> int:
        """Where a run of `width` pixels starts: at the margin, or centred in a centred style."""
        return x0 + (x1 - x0 - width) // 2 if st.center else tx

    if card.sponsored:
        y = p.text(left(p.width_of("Sponsored", 11, True)), y, "Sponsored", 11, st.muted, True)
    for line in p.wrap(product.name, 14, tw, 2):
        y = p.text(left(p.width_of(line, 14)), y, line, 14)
    if len(p.wrap(product.name, 14, tw, 2)) == 1:
        y += p.lh(14)
    if ratings:
        score = f"{product.rating:.1f} ({product.reviews:,})"
        sx = _stars(p, max(tx, left(p.width_of("★" * 5, 12) + 6 + p.width_of(score, 12))), y, product.rating, 12)
        p.d.text((sx, y), p.fit(score, 12, x1 - sx - 10), font=p.font(12), fill=st.muted)
        y += p.lh(12)
    price = money(product.price, site)
    was = money(product.list_price, site)
    pw = p.width_of(price, 17, True, display=True) + (8 + p.width_of(was, 12) if product.discount_percent else 0)
    px = max(tx, left(pw))
    p.d.text((px, y), price, font=p.font(17, True, True, price), fill=st.alert if product.discount_percent else st.ink)
    if product.discount_percent:
        px += p.width_of(price, 17, True, display=True) + 8
        p.d.text((px, y + 4), was, font=p.font(12), fill=st.muted)
        ww = p.width_of(was, 12)
        p.d.line((px, y + 4 + p.lh(12) // 2, px + ww, y + 4 + p.lh(12) // 2), fill=st.muted, width=1)
    y += p.lh(17)
    extra = ""
    if urgency and product.stock is not None and 0 < product.stock <= 5:
        extra = f"Only {product.stock} left!"
    elif social and product.weekly_sales:
        extra = f"{product.weekly_sales:,} bought this week"
    if extra:
        social_color = (251, 191, 36) if st.dark else (180, 83, 9)
        p.text(tx, y, p.fit(extra, 11, tw), 11, st.alert if extra.startswith("Only") else social_color, True)
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
    y = p.text(x0, y, p.caps(grid.title), 20, p.s.ink, True, display=True) + 2
    if p.s.caps or p.s.display != "sans":
        p.d.rectangle((x0, y, x0 + 40, y + 2), fill=p.accent)
        y += 8
    if grid.note:
        y = p.text(x0, y, p.fit(grid.note, 13, p.w - 2 * p.pad), 13, p.s.muted) + 4
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
    gap = round((12 if p.mobile else 16) * p.s.space)
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


def _line(p: _Paint, line: Line, x: int, y: int, width: int) -> int:
    if line.control is not None:
        style = "fill" if line.style == "strong" else "outline" if line.style == "text" else "link"
        h = round((42 if style == "fill" else 34) * p.k)
        w = min(width, max(200, p.width_of(line.text, 15, True) + 40)) if style != "link" else min(width, p.width_of(line.text, 14, True) + 32)
        p.button(line.control, x, y, line.text, w=w, h=h, style=style, size=15 if style == "fill" else 14)
        return y + h + 8
    size = {"title": 20, "total": 19, "price": 22}.get(line.style, 14)
    bold = line.style in ("title", "total", "price", "strong", "alert", "good")
    display = line.style in ("title", "total", "price")
    color = {"muted": p.s.muted, "alert": p.s.alert, "good": p.s.good}.get(line.style, p.s.ink)
    for text in p.wrap(line.text, size, width, 4, bold, display):
        y = p.text(x, y, text, size, color, bold, display)
    return y + 4


def _panel_height(p: _Paint, panel: Panel, width: int) -> int:
    probe = _Paint(width + 40, p.k, "#000000", p.s)
    y = probe.text(0, 0, panel.title, 18, None, True, display=True) + 6
    for line in panel.lines:
        y = _line(probe, line, 0, y, width)
    return y + 36


def _panel(p: _Paint, panel: Panel, box_x: int, y: int, width: int) -> int:
    st = p.s
    if panel.chips:
        y = p.text(box_x, y, p.caps(panel.title), 20, st.ink, True, display=True) + 4
        x = box_x
        h = round(44 * p.k)
        for line in panel.lines:
            w = p.width_of(line.text, 14, True) + 56
            if x + w > box_x + width:
                x = box_x
                y += h + 10
            p.frame((x, y, x + w, y + h), p.radius(12), st.soft, outline=st.edge or st.rule, width=max(1, st.outline))
            _glyph(p.d, "box", (x + 8, y + 8, x + h - 8, y + h - 8), p.accent)
            p.d.text((x + h, y + h // 2), line.text, font=p.font(14, True), fill=st.ink, anchor="lm")
            p.mark(line.control, (x, y, x + w, y + h))
            x += w + 10
        return y + h + 22
    height = _panel_height(p, panel, width - 40)
    p.frame((box_x, y, box_x + width, y + height), p.radius(16), st.surface, outline=(st.edge or st.rule) if st.outline else None,
            width=max(1, st.outline))
    iy = p.text(box_x + 20, y + 16, panel.title, 18, st.ink, True, display=True) + 6
    for line in panel.lines:
        iy = _line(p, line, box_x + 20, iy, width - 40)
    return y + height + 16


def _detail(p: _Paint, site: OnlineSite, page: Page, y: int, picture: ProductPicture | None) -> int:
    detail = page.detail
    if detail is None:
        return p.text(p.pad, y + 20, "This product is no longer available.", 16, p.s.muted) + 20
    product = detail.product
    if detail.breadcrumb is not None:
        label = "‹ " + detail.breadcrumb.action.label.removeprefix("Category: ")
        w = p.width_of(label, 13, True)
        p.d.text((p.pad, y), label, font=p.font(13, True), fill=p.accent)
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
    for line in p.wrap(product.name, 24, cw, 3, True, display=True):
        ty = p.text(cx, ty, line, 24, p.s.ink, True, display=True)
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
            p.d.text((sx, ty), p.fit(line.text, 14, cx + cw - sx), font=p.font(14), fill=p.s.muted)
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
    st = p.s
    fill = st.bar if st.header == "dark" else st.soft
    ink = _on(fill) if st.header == "dark" else st.ink
    p.d.rectangle((0, y, p.w, y + h), fill=fill)
    p.d.line((0, y, p.w, y), fill=st.rule, width=max(1, st.outline if st.outline > 1 else 1))
    x = p.pad
    for control in page.footer:
        label = control.action.label.removeprefix("Footer: ").capitalize()
        w = p.width_of(label, 13, True)
        p.d.text((x, y + h // 2), label, font=p.font(13, True), fill=ink, anchor="lm")
        p.mark(control, (x - 4, y + 10, x + w + 4, y + h - 10))
        x += w + 24
    if page.trust:
        good = _readable(st.good, fill)
        _icon(p.d, "lock", (x, y + h // 2 - 10, x + 20, y + h // 2 + 10), good)
        p.d.text((x + 24, y + h // 2), "Secure checkout", font=p.font(12, True), fill=good, anchor="lm")
    if not p.mobile:
        mark = f"© 2026 {page.site_name}"
        p.d.text((p.w - p.pad - p.width_of(mark, 12), y + h // 2), mark, font=p.font(12), fill=_mix(ink, fill, 0.4) if st.header == "dark" else st.muted, anchor="lm")
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


def _overlay(p: _Paint, page: Page, height: int, picture: ProductPicture | None) -> int:
    overlay = page.overlay
    if overlay is None:
        return height
    _shade(p.img, _CHROME)
    st = p.s
    if overlay.kind == "menu":
        w = min(320, round(p.w * 0.82))
        p.d.rectangle((0, _CHROME, w, p.img.height), fill=st.surface)
        y = p.text(20, _CHROME + 16, overlay.title, 20, st.ink, True, display=True) + 8
        for line in overlay.lines:
            if line.control is None:
                continue
            h = round(40 * p.k)
            label = line.control.action.label.removeprefix("Menu: ")
            label = "Close menu" if line.control.action.kind.value == "close_menu" else label
            p.d.text((36, y + h // 2), p.fit(label[:1].upper() + label[1:], 15, w - 56), font=p.font(15, line.style == "strong"),
                     fill=st.muted if line.style == "muted" else st.ink, anchor="lm")
            p.mark(line.control, (10, y, w - 10, y + h))
            p.d.line((20, y + h, w - 20, y + h), fill=st.rule)
            y += h + 2
        return max(height, y + 16)
    w = min(460, p.w - 2 * p.pad)
    x0 = (p.w - w) // 2
    probe_lines = [line for line in overlay.lines if line.control is None]
    extra = round(150 * p.k) if overlay.product is not None else 0  # a promo shows its product above the text
    h = 70 + sum(p.lh(15) * len(p.wrap(line.text, 15, w - 48, 3)) for line in probe_lines) + round(110 * p.k) + extra
    y0 = _CHROME + 90
    p.frame((x0, y0, x0 + w, y0 + h), p.radius(20), st.surface)
    p.d.rectangle((x0, y0, x0 + w, y0 + 8), fill=p.theme)
    if overlay.product is not None:
        side = extra - 30
        _picture(p, overlay.product, "box", (x0 + (w - side) // 2, y0 + 24, x0 + (w + side) // 2, y0 + 24 + side), picture)
        _pill(p, x0 + w - 104, y0 + 18, "Sponsored", _mix(INK, PAPER, 0.25), size=11)
    title = p.fit(overlay.title, 20, w - 48, True, display=True)
    y = p.text(x0 + 24, y0 + extra + 24, title, 20, st.ink, True, display=True) + 6
    for line in probe_lines:
        for text in p.wrap(line.text, 15, w - 48, 3):
            y = p.text(x0 + 24, y, text, 15, st.muted)
    y += 10
    for line in overlay.lines:
        if line.control is None:
            continue
        if line.style == "strong":
            box = p.button(line.control, x0 + 24, y, line.text, w=w - 48, h=round(44 * p.k), style="fill")
        else:
            box = p.button(line.control, x0 + 24, y, line.text, w=w - 48, h=round(34 * p.k), style="link", size=14)
        y = box[3] + 6
    return max(height, y0 + h + 16, y + 16)


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
    p = _Paint(width, 1.25 if page.large_text else 1.0, page.theme, STYLES[page.style])
    y = _chrome(p, page)
    y = _header(p, page, y)
    y = _nav(p, page, y)
    y = _notice(p, page, y) + 18
    y = _banner(p, page, y, picture)
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
        p.d.text((p.w - p.pad - 26, y - 36), "?", font=load_font(24, True), fill=_on(p.theme), anchor="mm")
    y = _footer(p, page, y)
    y = _cookie(p, page, y)
    height = min(_overlay(p, page, y, picture), _MAX_HEIGHT)
    p.img = p.img.crop((0, 0, width, height))
    p.d = ImageDraw.Draw(p.img)
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


_GIF_BAND = 58


def animate(frames: list[tuple[bytes, str, str]], *, width: int = 640, seconds: float = 1.6) -> bytes:
    """A visit as an animated GIF: each screenshot (PNG) scaled down to at most `width` and padded to the tallest,
    with a band below giving its caption and the shopper's thought; the last frame stays three times as long. Loops
    forever."""
    sizes: list[tuple[int, int]] = []
    for png, _, _ in frames:
        with Image.open(io.BytesIO(png)) as source:
            sizes.append(source.size)
    width = min(width, max(w for w, _ in sizes))  # a phone screen is not blown up
    height = max(max(1, round(h * width / w)) for w, h in sizes) + _GIF_BAND
    bold, plain = load_font(15, True), load_font(13, False)
    out_frames: list[Image.Image] = []
    for png, caption, thought in frames:
        # Decode one page at a time; retaining every full-height RGB page can exhaust a local app's memory.
        with Image.open(io.BytesIO(png)) as source, source.convert("RGB") as original:
            picture = original.resize((width, max(1, round(original.height * width / original.width))), Image.Resampling.LANCZOS)
        with picture, Image.new("RGB", (width, height), SOFT) as canvas:
            canvas.paste(picture, (0, 0))
            d = ImageDraw.Draw(canvas)
            d.rectangle((0, height - _GIF_BAND, width, height), fill=INK)
            lines = wrap_text(d, caption, bold, width - 24, 1)
            d.text((12, height - _GIF_BAND + 9), lines[0] if lines else "", font=bold, fill=PAPER)
            if thought:
                said = wrap_text(d, f"“{thought}”", plain, width - 24, 1)
                d.text((12, height - _GIF_BAND + 33), said[0] if said else "", font=plain, fill=RULE)
            out_frames.append(canvas.quantize(colors=255, method=Image.Quantize.MEDIANCUT))
    durations = [round(seconds * 1000)] * len(out_frames)
    durations[-1] *= 3
    out = io.BytesIO()
    out_frames[0].save(out, format="GIF", save_all=True, append_images=out_frames[1:], duration=durations, loop=0,
                       optimize=True)
    return out.getvalue()
