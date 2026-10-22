"""Serve individual packshots from the bundled, unmodified product image atlas."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image
from store_emulator.engine.layout_gen.catalog_expansion import PACKSHOT_SHEETS

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "catalog"
ROW_BOUNDS = {
    "starter-01": (0, .245, .5, .71, 1),
    "starter-02": (0, .25, .5, .735, 1),
    "starter-03": (0, .25, .5, .75, 1),
    "starter-04": (0, .25, .5, .75, 1),
    "starter-05": (0, .25, .5, .75, 1),
    "starter-06": (0, .25, .5, .75, 1),
    "starter-07": (0, .25, .5, .75, 1),
    "starter-08": (0, .25, .5, .75, 1),
    "starter-09": (0, .25, .5, .75, 1),
    "starter-10": (0, .25, .5, .75, 1),
    "starter-11": (0, .25, .5, .75, 1),
    "starter-12": (0, .25, .5, .75, 1),
    "starter-13": (0, .29, .49, .69, 1),
    "starter-14": (0, .25, .5, .75, 1),
    "starter-15": (0, .25, .5, .75, 1),
    "starter-16": (0, .25, .5, .75, 1),
    "starter-17": (0, .25, .5, .75, 1),
    "starter-18": (0, .25, .5, .75, 1),
    "starter-19": (0, .25, .5, .75, 1),
    "starter-20": (0, .25, .5, .75, 1),
    "starter-21": (0, .25, .5, .75, 1),
    "starter-22": (0, .25, .5, .75, 1),
    "starter-23": (0, .25, .5, .75, 1),
    "starter-24": (0, .25, .5, .75, 1),
    "starter-25": (0, .25, .5, .75, 1),
    "starter-26": (0, .25, .5, .75, 1),
    "starter-27": (0, .25, .5, .75, 1),
    "starter-28": (0, .25, .5, .735, 1),
    "starter-29": (0, .25, .5, .74, 1),
    "starter-30": (0, .25, .5, .75, 1),
    "starter-31": (0, .25, .5, .75, 1),
    "starter-32": (0, .25, .5, .75, 1),
    "starter-33": (0, .25, .5, .75, 1),
    "starter-34": (0, .25, .5, .75, 1),
    "starter-35": (0, .25, .5, .735, 1),
    "starter-36": (0, .25, .5, .735, 1),
    "starter-37": (0, 0.25, 0.5, 0.725, 1),
    "starter-38": (0, 0.25, 0.5, 0.75, 1),
    "starter-39": (0, 0.25, 0.5, 0.75, 1),
    "starter-40": (0, 0.25, 0.5, 0.75, 1),
    "starter-41": (0, 0.25, 0.5, 0.725, 1),
    "starter-42": (0, 0.25, 0.5, 0.735, 1),
    "starter-43": (0, 0.25, 0.5, 0.75, 1),
    "starter-44": (0, 0.25, 0.5, 0.735, 1),
    "starter-45": (0, 0.25, 0.5, 0.75, 1),
    "starter-46": (0, 0.25, 0.5, 0.735, 1),
    "starter-47": (0, 0.25, 0.485, 0.725, 1),
    "starter-48": (0, 0.25, 0.5, 0.75, 1),
    "starter-49": (0, 0.25, 0.5, 0.725, 1),
    "starter-50": (0, 0.25, 0.5, 0.75, 1),
    "starter-51": (0, 0.25, 0.5, 0.735, 1),
    "starter-52": (0, 0.25, 0.5, 0.75, 1),
    "starter-53": (0, 0.25, 0.5, 0.725, 1),
    "starter-54": (0, 0.25, 0.5, 0.75, 1),
    "starter-55": (0, 0.25, 0.5, 0.735, 1),
    "starter-56": (0, 0.25, 0.5, 0.75, 1),
    "starter-57": (0, 0.25, 0.5, 0.75, 1),
    "starter-58": (0, 0.25, 0.5, 0.75, 1),
    "starter-59": (0, 0.25, 0.5, 0.75, 1),
    "starter-60": (0, 0.25, 0.5, 0.75, 1),
    "starter-61": (0, 0.25, 0.5, 0.735, 1),
    "starter-62": (0, 0.25, 0.5, 0.735, 1),
    "starter-63": (0, 0.25, 0.5, 0.75, 1),
    "starter-64": (0, 0.25, 0.5, 0.75, 1),
    "starter-65": (0, 0.25, 0.5, 0.735, 1),
    "starter-66": (0, 0.25, 0.5, 0.75, 1),
    "starter-67": (0, 0.25, 0.5, 0.735, 1),
    "starter-68": (0, 0.25, 0.5, 0.75, 1),
    "starter-69": (0, 0.25, 0.5, 0.71, 1),
    "starter-70": (0, 0.25, 0.485, 0.725, 1),
    "starter-71": (0, 0.25, 0.5, 0.75, 1),
    "starter-72": (0, 0.25, 0.5, 0.725, 1),
}


@lru_cache(maxsize=128)
def packshot(sheet: str, index: int) -> bytes:
    if sheet not in PACKSHOT_SHEETS or not 0 <= index < len(PACKSHOT_SHEETS[sheet]):
        raise ValueError("Unknown catalog image")
    with Image.open(ASSETS / f"{sheet}.png") as atlas:
        width, height = atlas.size
        row, column = divmod(index, 4)
        rows = ROW_BOUNDS[sheet]
        tile = atlas.crop((round(column * width / 4), round(rows[row] * height),
                           round((column + 1) * width / 4), round(rows[row + 1] * height)))
        result = BytesIO()
        tile.save(result, format="WEBP", quality=88)
        return result.getvalue()
