"""Serve individual packshots from the bundled, unmodified product image atlas."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "catalog"


@lru_cache(maxsize=128)
def packshot(sheet: str, index: int) -> bytes:
    if sheet != "starter-01" or not 0 <= index < 16:
        raise ValueError("Unknown catalog image")
    with Image.open(ASSETS / f"{sheet}.png") as atlas:
        width, height = atlas.size
        row, column = divmod(index, 4)
        rows = (0, .245, .5, .71, 1)
        tile = atlas.crop((round(column * width / 4), round(rows[row] * height),
                           round((column + 1) * width / 4), round(rows[row + 1] * height)))
        result = BytesIO()
        tile.save(result, format="WEBP", quality=88)
        return result.getvalue()
