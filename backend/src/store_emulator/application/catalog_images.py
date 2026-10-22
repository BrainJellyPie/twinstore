"""Serve individual packshots from the bundled, unmodified product image atlas."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image
from store_emulator.engine.layout_gen.catalog_expansion import PACKSHOT_SHEETS

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "catalog"


@lru_cache(maxsize=128)
def packshot(sheet: str, index: int) -> bytes:
    if sheet not in PACKSHOT_SHEETS or not 0 <= index < len(PACKSHOT_SHEETS[sheet]):
        raise ValueError("Unknown catalog image")
    with Image.open(ASSETS / f"{sheet}.png") as atlas:
        width, height = atlas.size
        row, column = divmod(index, 4)
        rows = (0, .245, .5, .71, 1) if sheet == "starter-01" else (0, .25, .5, .735, 1)
        tile = atlas.crop((round(column * width / 4), round(rows[row] * height),
                           round((column + 1) * width / 4), round(rows[row + 1] * height)))
        result = BytesIO()
        tile.save(result, format="WEBP", quality=88)
        return result.getvalue()
