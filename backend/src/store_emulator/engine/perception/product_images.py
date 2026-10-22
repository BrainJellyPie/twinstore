"""Local product pictures for shelf charts. Project URLs are resolved by the application."""
import io
import re
import warnings
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

from store_emulator.domain.rack import SlotItem
from store_emulator.engine.perception.catalog_images import packshot

type ProductImageLoader = Callable[[SlotItem], Image.Image | None]


def decode_product_image(data: bytes) -> Image.Image | None:
    if len(data) > 10 * 1024 * 1024:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.width * source.height > 16_000_000:
                    return None
                picture = ImageOps.exif_transpose(source).convert("RGBA")
                picture.thumbnail((512, 512), Image.Resampling.LANCZOS)
                return picture
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None


def file_product_image(path: Path) -> Image.Image | None:
    try:
        if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            return None
        return decode_product_image(path.read_bytes())
    except OSError:
        return None


@lru_cache(maxsize=128)
def bundled_product_image(url: str) -> Image.Image | None:
    match = re.fullmatch(r"/api/catalog-images/(starter-\d+)/([0-9]+)\.webp", url)
    if match is None:
        return None
    try:
        return decode_product_image(packshot(match[1], int(match[2])))
    except (OSError, ValueError):
        return None


def default_product_image(item: SlotItem) -> Image.Image | None:
    url = item.image_url
    if not url:
        return None
    if url.startswith("file://"):
        # Existing local marketing experiments pass their prepared package file directly.
        return file_product_image(Path(url.removeprefix("file://")))
    return bundled_product_image(url)
