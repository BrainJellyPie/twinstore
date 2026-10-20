"""Working frame of a shelf photo: downscaled, deskewed RGB image plus the mapping back to the photo.

All capture stages run on the work image (bounded size, shelves roughly horizontal); results are
mapped back to the photo's pixel coordinates with `to_image_box` / `to_image_points`.
"""

import io
import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageFilter, ImageOps

from store_emulator.domain.capture import Box

type FloatArray = npt.NDArray[np.float32]
type BoolArray = npt.NDArray[np.bool_]

WORK_MAX_SIDE = 1024


@dataclass(frozen=True)
class WorkFrame:
    image: Image.Image          # RGB work image (deskewed, downscaled)
    gray: FloatArray            # float32 luminance of `image`, lightly smoothed
    scale: float                # photo pixels per work pixel
    angle: float                # degrees the photo was rotated (PIL convention, counter-clockwise) to deskew
    photo_size: tuple[int, int]

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size

    def to_image_points(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Work-frame points → photo pixel coordinates (undo the deskew rotation, then the downscale)."""
        w, h = self.image.size
        cx, cy = w / 2, h / 2
        a = math.radians(self.angle)
        cos_a, sin_a = math.cos(a), math.sin(a)
        out: list[tuple[float, float]] = []
        for x, y in points:
            dx, dy = x - cx, y - cy
            # Inverse of PIL's counter-clockwise rotation by `angle` (y axis pointing down).
            ox = cx + dx * cos_a - dy * sin_a
            oy = cy + dx * sin_a + dy * cos_a
            out.append((ox * self.scale, oy * self.scale))
        return out

    def to_image_box(self, x1: float, y1: float, x2: float, y2: float) -> Box:
        pts = self.to_image_points([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
        pw, ph = self.photo_size
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return Box(x1=max(0.0, min(xs)), y1=max(0.0, min(ys)), x2=min(float(pw), max(xs)), y2=min(float(ph), max(ys)))

    def to_work_points(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Photo pixel coordinates → work frame (inverse of `to_image_points`)."""
        w, h = self.image.size
        cx, cy = w / 2, h / 2
        a = math.radians(self.angle)
        cos_a, sin_a = math.cos(a), math.sin(a)
        out: list[tuple[float, float]] = []
        for px, py in points:
            ox, oy = px / self.scale - cx, py / self.scale - cy
            out.append((cx + ox * cos_a + oy * sin_a, cy - ox * sin_a + oy * cos_a))
        return out


def load_photo(data: bytes | Image.Image) -> Image.Image:
    """Decode an upload, apply its EXIF orientation and drop metadata (location, camera) — RGB only."""
    if isinstance(data, Image.Image):
        img = data
    else:
        img = Image.open(io.BytesIO(data))
        img.load()
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.getchannel("A"))
        img = background
    return img


def gray_array(img: Image.Image) -> FloatArray:
    """Luminance as float32, smoothed with a small Gaussian so sensor noise does not read as edges."""
    return np.asarray(img.convert("L").filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32)


def sobel(gray: FloatArray) -> tuple[FloatArray, FloatArray]:
    """|∂/∂x| and |∂/∂y| (3×3 Sobel)."""
    p = np.pad(gray, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.abs(gx).astype(np.float32), np.abs(gy).astype(np.float32)


def make_frame(photo: Image.Image, *, angle: float = 0.0, max_side: int = WORK_MAX_SIDE) -> WorkFrame:
    w, h = photo.size
    scale = max(1.0, max(w, h) / max_side)
    small = photo if scale == 1.0 else photo.resize((round(w / scale), round(h / scale)), Image.Resampling.LANCZOS)
    if abs(angle) >= 0.05:
        fill = tuple(int(v) for v in np.asarray(small, dtype=np.float32).reshape(-1, 3).mean(axis=0))
        small = small.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(fill[0], fill[1], fill[2]))
    else:
        angle = 0.0
    return WorkFrame(image=small, gray=gray_array(small), scale=scale, angle=angle, photo_size=(w, h))


def rgb_array(img: Image.Image) -> FloatArray:
    return np.asarray(img, dtype=np.float32)
