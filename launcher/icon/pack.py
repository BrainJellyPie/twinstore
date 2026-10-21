"""Packs the rendered icon PNGs (render.mjs) into the files the launchers embed:

  twinstore.ico     Windows (16–256 px; heavier strokes up to 48 px)
  TwinStore.icns    macOS app bundle
  twinstore.png     Linux menu entry and the boot screen (512 px)

Run with any Python that has Pillow:  python3 launcher/icon/pack.py
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PNG = HERE / "png"


def sized(src: Image.Image, size: int) -> Image.Image:
    return src.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    flat = Image.open(PNG / "flat-1024.png").convert("RGBA")
    small = Image.open(PNG / "flat-small-1024.png").convert("RGBA")
    mac = Image.open(PNG / "mac-1024.png").convert("RGBA")

    ico_sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [sized(small if s <= 48 else flat, s) for s in ico_sizes]
    frames[-1].save(HERE / "twinstore.ico", format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=frames[:-1])

    mac_sizes = [16, 32, 64, 128, 256, 512]
    mac.save(HERE / "TwinStore.icns", format="ICNS", append_images=[sized(mac, s) for s in mac_sizes])

    sized(flat, 512).save(HERE / "twinstore.png", optimize=True)
    print("wrote twinstore.ico, TwinStore.icns, twinstore.png")


if __name__ == "__main__":
    main()
