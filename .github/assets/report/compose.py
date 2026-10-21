"""Framed figure layouts for the report refresh: row of screens or a stack."""
import sys
from PIL import Image, ImageDraw, ImageFilter

def framed(im, width):
    h = round(im.height * width / im.width)
    im = im.convert("RGB").resize((width, h), Image.LANCZOS)
    r = 18
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=r, fill=255)
    card = Image.new("RGBA", (im.width + 60, im.height + 60), (0, 0, 0, 0))
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([30, 38, 30 + im.width, 38 + im.height], radius=r, fill=(20, 24, 40, 60))
    card = Image.alpha_composite(card, shadow.filter(ImageFilter.GaussianBlur(14)))
    card.paste(im, (30, 30), mask)
    ImageDraw.Draw(card).rounded_rectangle([30, 30, 30 + im.width - 1, 30 + im.height - 1], radius=r, outline=(222, 225, 232), width=2)
    return card

def row(paths, height):
    cards = []
    for p in paths:
        im = Image.open(p)
        cards.append(framed(im, round(im.width * height / im.height)))
    W = sum(c.width for c in cards) + 40
    H = max(c.height for c in cards) + 40
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    x = 20
    for c in cards:
        canvas.alpha_composite(c, (x, 20 + (H - 40 - c.height) // 2)); x += c.width
    return canvas

def stack(paths, width):
    cards = [framed(Image.open(p), width) for p in paths]
    canvas = Image.new("RGBA", (width + 100, sum(c.height for c in cards) + 40), (255, 255, 255, 255))
    y = 20
    for c in cards:
        canvas.alpha_composite(c, (20, y)); y += c.height
    return canvas

mode, out, *paths = sys.argv[1:]
img = row(paths, 1100) if mode == "row" else stack(paths, 1280)
img.convert("RGB").save(out, quality=88)
print(out, img.size)
