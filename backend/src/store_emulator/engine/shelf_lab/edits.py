"""Counterfactual edits of a shelf photo with exact ground truth.

Each edit rewrites only the pixels of the products it touches and returns, alongside the edited
photo, the boxes that changed and the planogram the edited photo now shows. Products move as
whole facings: a swap puts one facing of product A into every facing box of product B and back,
so facing counts per position are kept and the result stays a valid planogram.

Pasted pixels are colour-matched to the light at their destination, blurred to the photo's
sharpness and blended with feathered edges, so an edit reads as the same photograph rather than a
collage. Emptied facings are filled with real empty shelf from a gap in the same shelf when the
photo has one, otherwise with a synthesized shadowed back panel.
"""

import colorsys
import hashlib
import math
import random
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from store_emulator.domain.capture import Box, CaptureGap, CaptureItem, CaptureResult
from store_emulator.domain.shelf_lab import EditChange, PhotoEdit
from store_emulator.engine.capture.catalog_match import typical_price
from store_emulator.engine.capture.planogram import display_name, sku_for
from store_emulator.engine.perception.shelf_render import (
    load_font,
    text_color,
    wrap_text,
)
from store_emulator.engine.prompting import display_price

type FloatArray = npt.NDArray[np.float32]
type PixelBox = tuple[int, int, int, int]

# Identity of a product on the shelf: everything but where it stands.
_IDENTITY = ("sku", "name", "brand", "size", "category", "raw_category", "price", "price_estimated",
             "price_text", "confidence", "labeled")


@dataclass
class EditOutcome:
    image: Image.Image
    result: CaptureResult
    changes: list[EditChange]
    promos: dict[str, str]


def pixel_box(box: Box, size: tuple[int, int]) -> PixelBox:
    w, h = size
    x1 = max(0, min(w - 1, math.floor(box.x1)))
    y1 = max(0, min(h - 1, math.floor(box.y1)))
    x2 = max(x1 + 1, min(w, math.ceil(box.x2)))
    y2 = max(y1 + 1, min(h, math.ceil(box.y2)))
    return x1, y1, x2, y2


def _as_box(b: PixelBox) -> Box:
    return Box(x1=float(b[0]), y1=float(b[1]), x2=float(b[2]), y2=float(b[3]))


def _array(img: Image.Image) -> FloatArray:
    return np.asarray(img.convert("RGB"), dtype=np.float32)


def _image(arr: FloatArray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def match_colors(patch: FloatArray, reference: FloatArray, strength: float) -> FloatArray:
    """Move the patch's per-channel mean and contrast toward the reference's by `strength` (0–1)."""
    p = patch.reshape(-1, 3)
    r = reference.reshape(-1, 3)
    pm, ps = p.mean(axis=0), p.std(axis=0) + 1e-3
    rm, rs = r.mean(axis=0), r.std(axis=0) + 1e-3
    target_s = ps + (rs - ps) * strength
    target_m = pm + (rm - pm) * strength
    out = (patch - pm) / ps * target_s + target_m
    return np.clip(out, 0, 255).astype(np.float32)


def sharpness(arr: FloatArray) -> float:
    """Variance of the Laplacian of the luminance: higher = sharper."""
    g = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def match_blur(patch: Image.Image, reference: FloatArray) -> Image.Image:
    """Blur a (sharper) patch until its sharpness is closest to the destination's."""
    target = sharpness(reference)
    if target <= 0:
        return patch
    best, best_err = patch, abs(math.log((sharpness(_array(patch)) + 1) / (target + 1)))
    for radius in (0.5, 0.9, 1.4, 2.0, 2.8):
        cand = patch.filter(ImageFilter.GaussianBlur(radius))
        err = abs(math.log((sharpness(_array(cand)) + 1) / (target + 1)))
        if err < best_err:
            best, best_err = cand, err
    return best


def feather_mask(size: tuple[int, int], radius: float) -> Image.Image:
    w, h = size
    r = max(1, int(radius))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((r, r, max(r, w - 1 - r), max(r, h - 1 - r)), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(r / 2))


def expand(box: PixelBox, size: tuple[int, int], frac: float = 0.05) -> tuple[PixelBox, int]:
    """`box` grown by `frac` of its smaller side on every side (clipped), and the margin used."""
    x1, y1, x2, y2 = box
    m = max(2, round(min(x2 - x1, y2 - y1) * frac))
    w, h = size
    return (max(0, x1 - m), max(0, y1 - m), min(w, x2 + m), min(h, y2 + m)), m


def _paste(base: Image.Image, patch: Image.Image, box: PixelBox, alpha: Image.Image | None = None, *, margin: int = 2) -> None:
    """Blend `patch` into `box`; only the outer `margin` pixels fade, so the inner box is fully covered."""
    x1, y1, x2, y2 = box
    size = (x2 - x1, y2 - y1)
    if patch.size != size:
        patch = patch.resize(size, Image.Resampling.LANCZOS)
    feather = feather_mask(size, margin)
    mask = feather if alpha is None else Image.fromarray(
        (np.asarray(feather, dtype=np.float32) * np.asarray(alpha.resize(size), dtype=np.float32) / 255).astype(np.uint8), "L",
    )
    base.paste(patch.convert("RGB"), (x1, y1), mask)


def context_mean(arr: FloatArray, box: PixelBox) -> FloatArray:
    """Mean colour of the ring around `box` (the light falling on that spot, not the product)."""
    x1, y1, x2, y2 = box
    h, w = arr.shape[:2]
    m = max(4, round(min(x2 - x1, y2 - y1) * 0.35))
    ox1, oy1, ox2, oy2 = max(0, x1 - m), max(0, y1 - m), min(w, x2 + m), min(h, y2 + m)
    outer = arr[oy1:oy2, ox1:ox2].reshape(-1, 3)
    inner_n = (x2 - x1) * (y2 - y1)
    total = outer.sum(axis=0) - arr[y1:y2, x1:x2].reshape(-1, 3).sum(axis=0)
    n = max(1, len(outer) - inner_n)
    return (total / n).astype(np.float32)


def relight(patch: FloatArray, src_ctx: FloatArray, dst_ctx: FloatArray) -> FloatArray:
    """Carry a patch from a spot lit like `src_ctx` to one lit like `dst_ctx` (per-channel gain, clamped)."""
    gain = np.clip((dst_ctx + 4) / (src_ctx + 4), 0.75, 1.3)
    return np.clip(patch * gain, 0, 255).astype(np.float32)


def settle(patch: FloatArray, reference: FloatArray, dst_ctx: FloatArray, strength: float = 0.25) -> FloatArray:
    """Bring studio-lit pixels toward the photo: luminance level and contrast toward the destination
    by `strength`, white balance toward the destination's light; product colours are kept."""
    lum_w = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    pl = patch @ lum_w
    rl = reference @ lum_w
    pm, ps = float(pl.mean()), float(pl.std()) + 1e-3
    rm, rs = float(rl.mean()), float(rl.std()) + 1e-3
    tm, ts = pm + (rm - pm) * strength, ps + (rs - ps) * strength
    new_l = (pl - pm) / ps * ts + tm
    out = patch * ((new_l + 1) / (pl + 1))[:, :, None]
    tint = (dst_ctx + 4) / (float(dst_ctx.mean()) + 4)
    out = out * (1 + (np.clip(tint, 0.8, 1.25) - 1) * 0.5)
    return np.clip(out, 0, 255).astype(np.float32)


def _rng(seed: str, *parts: object) -> random.Random:
    key = "|".join([seed, *map(str, parts)])
    return random.Random(int(hashlib.sha1(key.encode()).hexdigest()[:12], 16))


# ── empty shelf ──────────────────────────────────────────────────────────────────

def empty_shelf(photo: Image.Image, box: PixelBox, gap_boxes: list[PixelBox], rng: random.Random) -> Image.Image:
    """Empty shelf for `box`: real empty stretch from the same shelf when there is one, else a
    shadowed back panel synthesized from the shelf's own colours."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    arr = _array(photo)
    usable = [g for g in gap_boxes if g[2] - g[0] >= 6 and g[3] - g[1] >= 6]
    if usable:
        g = max(usable, key=lambda b: b[2] - b[0])
        tile = arr[g[1]:g[3], g[0]:g[2]]
        tile = np.asarray(_image(tile).resize((tile.shape[1], h), Image.Resampling.LANCZOS), dtype=np.float32)
        reps = math.ceil(w / tile.shape[1])
        strip = np.concatenate([tile[:, ::-1] if k % 2 else tile for k in range(reps)], axis=1)[:, :w]
        return _image(relight(strip, context_mean(arr, g), context_mean(arr, box)))
    region = arr[y1:y2, max(0, x1 - w):min(arr.shape[1], x2 + w)].reshape(-1, 3)
    lum = region @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    dark = region[lum <= np.percentile(lum, 25)]
    base_col = (dark.mean(axis=0) * 0.6 + region.mean(axis=0) * 0.4) if len(dark) else region.mean(axis=0)
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    shade = 0.62 + 0.3 * ys                     # darker at the back/top of the shelf opening
    shade = shade + 0.12 * np.clip((ys - 0.9) / 0.1, 0, 1)  # lit shelf floor
    panel = np.broadcast_to(base_col[None, None, :], (h, w, 3)).astype(np.float32) * shade
    noise = np.random.default_rng(rng.getrandbits(32)).normal(0.0, 2.5, (h, w, 1)).astype(np.float32)
    return _image((panel + noise).astype(np.float32)).filter(ImageFilter.GaussianBlur(0.6))


# ── packages ─────────────────────────────────────────────────────────────────────

def cut_out(package: Image.Image) -> Image.Image:
    """RGBA package: keeps an alpha channel; otherwise removes a flat background touching the corners."""
    if package.mode in ("RGBA", "LA") or "transparency" in package.info:
        rgba = package.convert("RGBA")
    else:
        rgb = package.convert("RGB")
        marked = rgb.copy()
        sentinel = (255, 0, 255)
        w, h = rgb.size
        for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            if marked.getpixel(corner) != sentinel:
                ImageDraw.floodfill(marked, corner, sentinel, thresh=34)
        m = np.asarray(marked, dtype=np.int16)
        alpha = np.where(np.all(m == np.array(sentinel, dtype=np.int16), axis=2), 0, 255).astype(np.uint8)
        rgba = rgb.convert("RGBA")
        rgba.putalpha(Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(0.7)))
    bbox = rgba.getchannel("A").getbbox()
    return rgba.crop(bbox) if bbox else rgba


def synth_package(name: str, brand: str = "", size: tuple[int, int] = (240, 320)) -> Image.Image:
    """A plain printed package for a product without an uploaded image."""
    digest = hashlib.sha1(name.encode()).digest()
    hue = digest[0] / 255
    r, g, b = colorsys.hls_to_rgb(hue, 0.5, 0.62)
    body = (int(r * 255), int(g * 255), int(b * 255))
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 10, w - 5, h - 3), radius=int(w * 0.08), fill=(*body, 255))
    d.rounded_rectangle((4, 10, w - 5, h - 3), radius=int(w * 0.08), outline=(0, 0, 0, 60), width=2)
    d.rectangle((4, int(h * 0.36), w - 5, int(h * 0.68)), fill=(250, 250, 248, 255))
    ink = text_color(body)
    font = load_font(max(12, int(w * 0.12)), bold=True)
    small = load_font(max(10, int(w * 0.08)))
    lines = wrap_text(d, name, font, int(w * 0.84), 2)
    line_h = font.size if isinstance(font, ImageFont.FreeTypeFont) else 14
    top = h * 0.52 - len(lines) * line_h * 0.6
    for k, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        d.text(((w - tw) / 2, top + k * line_h * 1.15), line, font=font, fill=(25, 25, 30, 255))
    if brand:
        bw = d.textlength(brand[:20], font=small)
        d.text(((w - bw) / 2, h * 0.2), brand[:20], font=small, fill=(*ink, 255))
    return img


def fit_package(package: Image.Image, size: tuple[int, int]) -> tuple[Image.Image, Image.Image]:
    """(RGB, alpha) of the package standing on the shelf, bottom-centred in a box of `size`, with a soft
    contact shadow."""
    w, h = size
    pkg = cut_out(package)
    pw, ph = pkg.size
    scale = min(w * 0.9 / max(1, pw), h * 0.95 / max(1, ph))
    nw, nh = max(1, int(pw * scale)), max(1, int(ph * scale))
    pkg = pkg.resize((nw, nh), Image.Resampling.LANCZOS)
    ox, oy = (w - nw) // 2, h - nh - max(1, h // 60)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow_alpha = Image.new("L", size, 0)
    shadow_alpha.paste(pkg.getchannel("A"), (ox + max(1, w // 40), oy + max(1, h // 50)))
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha.filter(ImageFilter.GaussianBlur(max(1.5, w / 30))).point(lambda v: int(v * 0.45)))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(pkg, (ox, oy))
    return canvas.convert("RGB"), canvas.getchannel("A")


# ── signage ──────────────────────────────────────────────────────────────────────

def draw_price_tag(img: Image.Image, item: Box, text: str, *, was: str = "") -> PixelBox:
    """A shelf-edge price tag under the product, large enough to cover the old one (a red sale tag with
    the struck-through old price when `was` is set)."""
    d = ImageDraw.Draw(img)
    h = max(16, int(item.height * 0.2))
    font = load_font(max(10, int(h * 0.6)), bold=True)
    small = load_font(max(8, int(h * 0.4)))
    width = max(int(h * 2.6), int(item.width * 0.6), int(d.textlength(text, font=font)) + h // 2)
    x1 = int(max(0, min(img.width - width - 3, item.cx - width / 2)))
    y1 = int(max(0, min(img.height - h - 4, item.y2 + 1)))
    x2, y2 = x1 + width, y1 + h
    d.rounded_rectangle((x1 + 2, y1 + 3, x2 + 2, y2 + 3), radius=h // 6, fill=(0, 0, 0))
    sale = bool(was)
    d.rounded_rectangle((x1, y1, x2, y2), radius=h // 6, fill=(228, 32, 40) if sale else (255, 222, 52),
                        outline=(255, 255, 255) if sale else (140, 110, 0), width=1)
    ink = (255, 255, 255) if sale else (20, 20, 22)
    tw = d.textlength(text, font=font)
    d.text((x1 + (width - tw) / 2, y1 + h * 0.16), text, font=font, fill=ink)
    top = y1
    if sale:
        ww = int(d.textlength(was, font=small))
        wy = max(0, y1 - int(h * 0.62))
        d.rounded_rectangle((x1, wy, x1 + ww + 10, y1 - 1), radius=3, fill=(255, 255, 255))
        d.text((x1 + 5, wy + 1), was, font=small, fill=(90, 90, 90))
        d.line((x1 + 3, (wy + y1) // 2, x1 + ww + 7, (wy + y1) // 2), fill=(200, 30, 30), width=2)
        top = wy
    return x1, top, x2 + 4, y2 + 4  # exclusive: the shadow is drawn up to x2+2, y2+3 inclusive


def draw_promo(img: Image.Image, item: Box, text: str) -> PixelBox:
    """A starburst promotion sticker on the product's upper right corner."""
    size = int(max(22, min(item.width, item.height) * 0.36))
    layer = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = cy = size
    spikes = 14
    pts: list[tuple[float, float]] = []
    for k in range(spikes * 2):
        r = size * (0.92 if k % 2 == 0 else 0.74)
        a = math.pi * k / spikes - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    shadow = [(x + size * 0.06, y + size * 0.08) for x, y in pts]
    d.polygon(shadow, fill=(0, 0, 0, 90))
    d.polygon(pts, fill=(232, 24, 46, 255), outline=(255, 255, 255, 255))
    label = text.strip()[:8] or "SALE"
    font = load_font(max(10, int(size * (0.62 if len(label) <= 3 else 0.42))), bold=True)
    tw = d.textlength(label, font=font)
    d.text((cx - tw / 2, cy - size * (0.36 if len(label) <= 3 else 0.26)), label, font=font, fill=(255, 255, 255, 255))
    layer = layer.rotate(-12, resample=Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(0.4))
    x = int(min(img.width - size * 2, max(0, item.x2 - size * 1.6)))
    y = int(min(img.height - size * 2, max(0, item.y1 - size * 0.7)))
    base = img.convert("RGBA")
    base.alpha_composite(layer, (x, y))
    img.paste(base.convert("RGB"))
    return x, y, x + size * 2, y + size * 2


# ── edits ────────────────────────────────────────────────────────────────────────

def _identity(item: CaptureItem) -> dict[str, object]:
    return {k: getattr(item, k) for k in _IDENTITY}


def _gap_boxes(result: CaptureResult, band: int, size: tuple[int, int]) -> list[PixelBox]:
    """Real empty stretches to copy from: the same shelf first, then any shelf of the photo."""
    same = [pixel_box(g.box, size) for g in result.gaps if g.band == band]
    return same or [pixel_box(g.box, size) for g in result.gaps]


def _find(items: dict[str, CaptureItem], item_id: str) -> CaptureItem:
    item = items.get(item_id)
    if item is None:
        raise ValueError(f"product not found on this shelf: {item_id}")
    if not item.boxes:
        raise ValueError(f"product {item_id} has no boxes on the photo")
    return item


def apply_edits(
    photo: Image.Image,
    result: CaptureResult,
    edits: list[PhotoEdit],
    *,
    packages: dict[str, Image.Image] | None = None,
    seed: str = "",
) -> EditOutcome:
    """Apply `edits` in order to a copy of the photo and its planogram."""
    img = photo.convert("RGB").copy()
    items = {i.id: i.model_copy(deep=True) for i in result.items}
    gaps = list(result.gaps)
    changes: list[EditChange] = []
    promos: dict[str, str] = {}
    packages = packages or {}
    currency = result.currency

    for n, edit in enumerate(edits):
        item = _find(items, edit.item_id)
        before_img = img.copy()
        match edit.kind:
            case "remove":
                rng = _rng(seed, n, item.id)
                for box in item.boxes:
                    pb = pixel_box(box, img.size)
                    eb, m = expand(pb, img.size)
                    fill = empty_shelf(before_img, eb, _gap_boxes(result, item.band, img.size), rng)
                    _paste(img, fill, eb, margin=m)
                    changes.append(EditChange(kind="remove", item_id=item.id, box=_as_box(eb), before=display_name(item), after="(empty)"))
                    gaps.append(CaptureGap(band=item.band, level=item.level, box=_as_box(pb), facings=1.0))
                del items[item.id]
            case "swap" | "duplicate":
                other = _find(items, edit.other_id)
                if other.id == item.id:
                    raise ValueError("a product cannot trade places with itself")
                pairs = [(item, other), (other, item)] if edit.kind == "swap" else [(item, other)]
                src_arr = _array(before_img)
                for src, dst in pairs:
                    sbox = pixel_box(src.boxes[len(src.boxes) // 2], img.size)
                    s_eb, _ = expand(sbox, img.size)
                    crop = src_arr[s_eb[1]:s_eb[3], s_eb[0]:s_eb[2]]
                    s_ctx = context_mean(src_arr, sbox)
                    for box in dst.boxes:
                        pb = pixel_box(box, img.size)
                        eb, m = expand(pb, img.size)
                        resized = _array(_image(crop).resize((eb[2] - eb[0], eb[3] - eb[1]), Image.Resampling.LANCZOS))
                        _paste(img, _image(relight(resized, s_ctx, context_mean(src_arr, pb))), eb, margin=m)
                        changes.append(EditChange(kind=edit.kind, item_id=dst.id, box=_as_box(eb),
                                                  before=display_name(dst), after=display_name(src)))
                a, b = _identity(item), _identity(other)
                if edit.kind == "swap":
                    items[item.id] = item.model_copy(update=b)
                items[other.id] = other.model_copy(update=a)
            case "replace":
                name = edit.name.strip() or "New product"
                pkg = packages.get(edit.asset_id) if edit.asset_id else None
                if edit.asset_id and pkg is None:
                    raise ValueError(f"package image not found: {edit.asset_id}")
                pkg = pkg if pkg is not None else synth_package(name, edit.brand)
                rng = _rng(seed, n, item.id)
                src_arr = _array(before_img)
                for box in item.boxes:
                    pb = pixel_box(box, img.size)
                    eb, m = expand(pb, img.size)
                    ref = src_arr[pb[1]:pb[3], pb[0]:pb[2]]
                    shelf = empty_shelf(before_img, eb, _gap_boxes(result, item.band, img.size), rng)
                    # The package stands in the original facing box; the margin around it is shelf.
                    rgb, alpha = fit_package(pkg, (pb[2] - pb[0], pb[3] - pb[1]))
                    rgb = match_blur(_image(settle(_array(rgb), ref, context_mean(src_arr, pb))), ref)
                    composed = shelf.copy()
                    composed.paste(rgb, (pb[0] - eb[0], pb[1] - eb[1]), alpha)
                    _paste(img, composed, eb, margin=m)
                    changes.append(EditChange(kind="replace", item_id=item.id, box=_as_box(eb), before=display_name(item), after=name))
                category = edit.category or item.category
                typical, _ = typical_price(category, name, currency) if category else (None, "")
                price = edit.price if edit.price is not None else (typical if typical is not None else item.price)
                items[item.id] = item.model_copy(update={
                    "sku": sku_for(name, edit.brand, ""), "name": name, "brand": edit.brand.strip(), "size": "",
                    "category": category, "raw_category": category, "price": price,
                    "price_estimated": edit.price is None, "price_text": display_price(price, currency) if price is not None else "",
                    "confidence": 10, "labeled": True,
                })
            case "price":
                if edit.price is None:
                    raise ValueError("a price edit needs a price")
                was = display_price(item.price, currency) if item.price is not None and edit.price < item.price else ""
                region = Box(x1=min(b.x1 for b in item.boxes), y1=min(b.y1 for b in item.boxes),
                             x2=max(b.x2 for b in item.boxes), y2=max(b.y2 for b in item.boxes))
                text = display_price(edit.price, currency)
                pb = draw_price_tag(img, region, text, was=was)
                changes.append(EditChange(kind="price", item_id=item.id, box=_as_box(pixel_box(_as_box(pb), img.size)),
                                          before=display_price(item.price, currency) if item.price is not None else "", after=text))
                items[item.id] = item.model_copy(update={"price": edit.price, "price_text": text, "price_estimated": False})
            case "promo":
                label = edit.promo.strip() or "SALE"
                region = item.boxes[-1]
                pb = draw_promo(img, region, label)
                changes.append(EditChange(kind="promo", item_id=item.id, box=_as_box(pixel_box(_as_box(pb), img.size)),
                                          before=promos.get(item.id, ""), after=label))
                promos[item.id] = label

    ordered = sorted(items.values(), key=lambda i: (i.band, i.order))
    edited = result.model_copy(update={"items": ordered, "gaps": gaps, "edited": True})
    return EditOutcome(image=img, result=edited, changes=changes, promos=promos)
