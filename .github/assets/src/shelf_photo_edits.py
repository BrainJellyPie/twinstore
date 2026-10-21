"""Shelf Lab on a studio render: the photoreal shelf from frontend/studio.html, edited by the real
counterfactual engine with its exact facing boxes, plus the tagged view a vision shopper sees.

  uv run --project backend python .github/assets/src/shelf_photo_edits.py shelf.png shelf.json volt.png OUT_DIR

Writes OUT_DIR/{shelf-photo,shelf-photo-edited,shelf-photo-tagged}.jpg, shelf-photo-mask.png,
changes.json (the ground-truth boxes of every edit) and overlay.json (one merged box per edit and the
numbered tags of the tagged view, as fractions of the image) for the figures and the film.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.shelf_lab import PhotoEdit
from store_emulator.engine.shelf_lab.edits import apply_edits
from store_emulator.engine.shelf_lab.sim2real import _shelf_crop, build_views  # pyright: ignore[reportPrivateUsage]


def by_name(result: CaptureResult, name: str) -> str:
    return next(i.id for i in result.items if i.name == name)


def main(photo_path: str, result_path: str, package_path: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    photo = Image.open(photo_path).convert("RGB")
    result = CaptureResult.model_validate(json.loads(Path(result_path).read_text()))
    package = Image.open(package_path).convert("RGBA")
    package = package.crop(package.getbbox())
    edits = [
        PhotoEdit(kind="swap", item_id=by_name(result, "Fizzo Zero Cola 20oz"), other_id=by_name(result, "Spritz Lemon-Lime Soda 20oz")),
        # the stock-out sits on the shelf that already has a gap, so the engine refills it with real empty shelf
        PhotoEdit(kind="remove", item_id=by_name(result, "Purple Grape Soda 12oz can")),
        PhotoEdit(kind="replace", item_id=by_name(result, "Leafy Peach Iced Tea 16.9oz"), name="Volt Lime Cola", brand="TwinStore Labs",
                  price=199, asset_id="volt"),
        PhotoEdit(kind="price", item_id=by_name(result, "Fizzo Cola 2 Liter"), price=199),
        PhotoEdit(kind="promo", item_id=by_name(result, "Clara Sparkling Water 1 Liter"), promo="1+1"),
    ]
    outcome = apply_edits(photo, result, edits, packages={"volt": package}, seed="studio")
    photo.save(out / "shelf-photo.jpg", quality=92)
    outcome.image.save(out / "shelf-photo-edited.jpg", quality=92)
    mask = Image.new("L", photo.size, 0)
    d = ImageDraw.Draw(mask)
    for change in outcome.changes:
        d.rectangle((change.box.x1, change.box.y1, change.box.x2, change.box.y2), fill=255)
    mask.save(out / "shelf-photo-mask.png")
    (out / "changes.json").write_text(json.dumps([c.model_dump() for c in outcome.changes], indent=1))
    width = 1200
    tagged = build_views(photo, result, width=width).views["photo"]
    (out / "shelf-photo-tagged.png").write_bytes(tagged.png)
    Image.open(out / "shelf-photo-tagged.png").convert("RGB").save(out / "shelf-photo-tagged.jpg", quality=90)

    w, h = photo.size
    merged: dict[tuple[str, str], list[float]] = {}
    for c in outcome.changes:
        b = merged.setdefault((c.kind, c.item_id), [c.box.x1, c.box.y1, c.box.x2, c.box.y2])
        b[:] = [min(b[0], c.box.x1), min(b[1], c.box.y1), max(b[2], c.box.x2), max(b[3], c.box.y2)]
    crop, (ox, oy) = _shelf_crop(photo, result)
    scale = width / crop.width
    marks = {m.item.sku: m.mark for m in tagged.items}
    tags = [{"name": i.name, "mark": marks[i.sku],
             "box": [(i.boxes[0].x1 - ox) * scale / tagged.size[0], (i.boxes[0].y1 - oy) * scale / tagged.size[1],
                     (i.boxes[0].x2 - ox) * scale / tagged.size[0], (i.boxes[0].y2 - oy) * scale / tagged.size[1]]}
            for i in result.items if i.sku in marks and i.boxes]
    overlay = {
        "edits": [{"kind": k, "item": next(i.name for i in result.items if i.id == item_id),
                   "box": [b[0] / w, b[1] / h, b[2] / w, b[3] / h]} for (k, item_id), b in merged.items()],
        "tags": tags,
    }
    (out / "overlay.json").write_text(json.dumps(overlay, indent=1))
    print(f"{len(outcome.changes)} changed boxes; tagged view {tagged.size}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
