"""Counterfactual shelf benchmark: many single-change counterfactuals with exact ground truth.

Sources are rendered shelves (every store template's racks, degraded like phone photos, with a
perfect planogram) and real captures (their corrected planograms). For each shelf a seeded plan
draws a few edits of every kind on random products; each counterfactual changes exactly one thing.

Layout of the output directory:

    index.jsonl                         one line per counterfactual (shelf, edit, changed boxes, files)
    shelves/<shelf>/original.png        the shelf photo
    shelves/<shelf>/planogram.json      its CaptureResult
    shelves/<shelf>/<cf>.png            the counterfactual photo
    shelves/<shelf>/<cf>_mask.png       white where pixels were rewritten
    shelves/<shelf>/<cf>.json           the edit, its changes and the counterfactual planogram
"""

import json
import random
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from store_emulator.domain.capture import Box, CaptureGap, CaptureItem, CaptureResult
from store_emulator.domain.shelf_lab import EditKind, PhotoEdit
from store_emulator.domain.types import Face
from store_emulator.engine.capture.planogram import sku_for
from store_emulator.engine.capture.synthetic import Severity, SyntheticShelf, make_scene
from store_emulator.engine.layout_gen.templates import TEMPLATES, generate_store

from .edits import apply_edits

ALL_KINDS: tuple[EditKind, ...] = ("swap", "remove", "replace", "price", "promo", "duplicate")
NEW_PRODUCTS = ("Volt Cola", "Aurora Sparkling Water", "Nebula Energy", "Prism Iced Tea", "Orbit Chips", "Halo Protein Bar")
PROMO_TEXTS = ("1+1", "2+1", "SALE", "-30%")


@dataclass
class BenchShelf:
    shelf_id: str
    source: str
    image: Image.Image
    result: CaptureResult


def scene_capture(scene: SyntheticShelf) -> CaptureResult:
    """A perfect capture of a rendered shelf: one item per ground-truth run of identical facings."""
    runs: dict[tuple[int, int], list[Box]] = {}
    first: dict[tuple[int, int], tuple[str, int, int]] = {}
    for f in scene.facings:
        key = (f.row, f.run)
        runs.setdefault(key, []).append(Box(x1=f.box[0], y1=f.box[1], x2=f.box[2], y2=f.box[3]))
        first.setdefault(key, (f.item.name, f.item.price, f.level))
    items: list[CaptureItem] = []
    order: dict[int, int] = {}
    for key in sorted(runs):
        row = key[0]
        name, price, level = first[key]
        items.append(CaptureItem(
            id=f"i{len(items) + 1:02d}", band=row, level=level, order=order.get(row, 0), facings=len(runs[key]),
            boxes=runs[key], sku=sku_for(name, "", ""), name=name, price=price, labeled=True, confidence=10,
        ))
        order[row] = order.get(row, 0) + 1
    gaps = [CaptureGap(band=g.row, level=g.level, box=Box(x1=g.box[0], y1=g.box[1], x2=g.box[2], y2=g.box[3])) for g in scene.gaps]
    return CaptureResult(image_size=scene.image.size, currency=scene.currency, rack_type="fridge" if scene.rack.type.value == "fridge" else "shelf",
                         items=items, gaps=gaps, detector="ground_truth")


def synthetic_shelves(
    *, templates: list[str] | None = None, per_template: int = 4, severities: list[Severity] | None = None,
    currency: str = "USD", seed: int = 0,
) -> Iterator[BenchShelf]:
    """Rendered shelves from every template's stocked racks, cycling through degradation severities."""
    severities = severities or ["clean", "mild", "strong"]
    ids = templates or [t.id for t in TEMPLATES]
    for tid in ids:
        store = generate_store(tid, seed=seed, currency=currency)
        racks = [r for r in store.racks if r.slots]
        for k in range(min(per_template, len(racks) * 3)):
            rack = racks[k % len(racks)]
            face = rack.slots[0].face if rack.slots else Face.S
            severity = severities[k % len(severities)]
            scene = make_scene(rack, face, currency=currency, seed=seed * 1000 + k, severity=severity)
            yield BenchShelf(shelf_id=f"syn_{tid}_{k:02d}", source=f"synthetic:{tid}:{rack.id}:{face.value}:{severity}",
                             image=scene.image, result=scene_capture(scene))


def capture_shelves(captures_dir: Path) -> Iterator[BenchShelf]:
    """Real captures of a project (`.data/<pid>/captures`) whose planogram exists."""
    for folder in sorted(p for p in captures_dir.iterdir() if p.is_dir()):
        result_path, image_path = folder / "result.json", folder / "image.jpg"
        if not result_path.exists() or not image_path.exists():
            continue
        result = CaptureResult.model_validate(json.loads(result_path.read_text(encoding="utf-8")))
        if not result.items:
            continue
        img = Image.open(image_path)
        img.load()
        yield BenchShelf(shelf_id=f"cap_{folder.name}", source=f"capture:{captures_dir.parent.name}/{folder.name}",
                         image=img.convert("RGB"), result=result)


def plan_edits(result: CaptureResult, rng: random.Random, kinds: list[EditKind], per_kind: int) -> list[PhotoEdit]:
    """Single-change counterfactuals on random products (each list entry is one counterfactual)."""
    items = [i for i in result.items if i.boxes]
    plans: list[PhotoEdit] = []
    if not items:
        return plans
    by_band: dict[int, list[CaptureItem]] = {}
    for it in sorted(items, key=lambda i: (i.band, i.order)):
        by_band.setdefault(it.band, []).append(it)
    for kind in kinds:
        for _ in range(per_kind):
            target = rng.choice(items)
            match kind:
                case "swap":
                    others = [i for i in items if i.id != target.id and i.sku != target.sku]
                    if others:
                        plans.append(PhotoEdit(kind="swap", item_id=target.id, other_id=rng.choice(others).id))
                case "duplicate":
                    row = by_band[target.band]
                    k = row.index(target)
                    neighbours = [row[j] for j in (k - 1, k + 1) if 0 <= j < len(row) and row[j].sku != target.sku]
                    if neighbours:
                        plans.append(PhotoEdit(kind="duplicate", item_id=target.id, other_id=rng.choice(neighbours).id))
                case "remove":
                    plans.append(PhotoEdit(kind="remove", item_id=target.id))
                case "replace":
                    plans.append(PhotoEdit(kind="replace", item_id=target.id, name=rng.choice(NEW_PRODUCTS), brand="TwinStore Labs",
                                           price=target.price))
                case "price":
                    if target.price:
                        plans.append(PhotoEdit(kind="price", item_id=target.id, price=max(1, round(target.price * rng.uniform(0.6, 0.85)))))
                case "promo":
                    plans.append(PhotoEdit(kind="promo", item_id=target.id, promo=rng.choice(PROMO_TEXTS)))
    return plans


def write_bench(
    out_dir: Path, shelves: Iterator[BenchShelf], *, kinds: list[EditKind] | None = None, per_kind: int = 2, seed: int = 0,
) -> dict[str, int]:
    """Write the benchmark; returns counts per edit kind (and shelves)."""
    kinds = kinds or list(ALL_KINDS)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {"shelves": 0}
    with (out_dir / "index.jsonl").open("w") as index:
        for shelf in shelves:
            folder = out_dir / "shelves" / shelf.shelf_id
            folder.mkdir(parents=True, exist_ok=True)
            shelf.image.save(folder / "original.png")
            (folder / "planogram.json").write_text(shelf.result.model_dump_json(indent=1), encoding="utf-8")
            counts["shelves"] += 1
            rng = random.Random(f"{seed}|{shelf.shelf_id}")
            for n, edit in enumerate(plan_edits(shelf.result, rng, kinds, per_kind)):
                cf = f"cf{n:02d}_{edit.kind}"
                out = apply_edits(shelf.image, shelf.result, [edit], seed=f"{seed}|{shelf.shelf_id}|{n}")
                out.image.save(folder / f"{cf}.png")
                mask = Image.new("L", out.image.size, 0)
                d = ImageDraw.Draw(mask)
                for c in out.changes:
                    d.rectangle((c.box.x1, c.box.y1, c.box.x2 - 1, c.box.y2 - 1), fill=255)
                mask.save(folder / f"{cf}_mask.png")
                record = {
                    "id": f"{shelf.shelf_id}/{cf}", "shelf": shelf.shelf_id, "source": shelf.source, "kind": edit.kind,
                    "edit": edit.model_dump(), "changes": [c.model_dump() for c in out.changes], "promos": out.promos,
                    "files": {"original": f"shelves/{shelf.shelf_id}/original.png", "counterfactual": f"shelves/{shelf.shelf_id}/{cf}.png",
                              "mask": f"shelves/{shelf.shelf_id}/{cf}_mask.png", "planogram": f"shelves/{shelf.shelf_id}/planogram.json"},
                }
                (folder / f"{cf}.json").write_text(json.dumps({**record, "result": json.loads(out.result.model_dump_json())}, indent=1), encoding="utf-8")
                index.write(json.dumps(record) + "\n")
                counts[edit.kind] = counts.get(edit.kind, 0) + 1
    return counts
