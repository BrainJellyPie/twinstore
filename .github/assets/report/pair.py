"""Side-by-side comparison figure: Parastore (left) vs TwinStore (right), or a single framed TwinStore screen.
usage: pair.py out.jpg left.jpg|- right.jpg [crop_l x0,y0,x1,y1|-] [crop_r x0,y0,x1,y1|-]"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
W_EACH = 1180

def load(path, crop):
    im = Image.open(path).convert("RGB")
    if crop and crop != "-":
        x0, y0, x1, y1 = (int(v) for v in crop.split(","))
        im = im.crop((x0, y0, x1, y1))
    return im

def framed(im, width):
    h = round(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
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

def label(draw, x, y, text, fill, ink):
    f = ImageFont.truetype(FONT, 34)
    w = int(f.getlength(text)) + 56
    draw.rounded_rectangle([x, y, x + w, y + 58], radius=29, fill=fill)
    draw.text((x + 28, y + 29), text, font=f, fill=ink, anchor="lm")

out, left, right = sys.argv[1:4]
cl = sys.argv[4] if len(sys.argv) > 4 else "-"
cr = sys.argv[5] if len(sys.argv) > 5 else "-"
R = framed(load(right, cr), W_EACH)
if left == "-":
    canvas = Image.new("RGBA", (R.width + 40, R.height + 40), (255, 255, 255, 255))
    canvas.alpha_composite(R, (20, 20))
else:
    L = framed(load(left, cl), W_EACH)
    top = 96
    h = max(L.height, R.height)
    canvas = Image.new("RGBA", (L.width + R.width + 60, h + top + 10), (255, 255, 255, 255))
    d = ImageDraw.Draw(canvas)
    label(d, 50, 26, "Parastore", (236, 238, 242, 255), (70, 76, 92, 255))
    label(d, L.width + 50 + 30, 26, "TwinStore", (107, 77, 255, 255), (255, 255, 255, 255))
    canvas.alpha_composite(L, (20, top - 20 + (h - L.height) // 2))
    canvas.alpha_composite(R, (L.width + 40, top - 20 + (h - R.height) // 2))
    # arrow between the two
    ax = L.width + 32
    ay = top - 20 + h // 2
    d.polygon([(ax - 4, ay - 22), (ax - 4, ay + 22), (ax + 22, ay)], fill=(107, 77, 255, 255))
canvas.convert("RGB").save(out, quality=88)
print(out, canvas.size)
