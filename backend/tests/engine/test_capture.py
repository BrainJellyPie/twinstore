"""Shelf capture pipeline, offline: rendered shelves with exact ground truth and a fake VLM."""

import asyncio
import base64
import io
import os

import numpy as np
import pytest
from PIL import Image
from pydantic import BaseModel

from store_emulator.domain.capture import (
    Box,
    CaptureItem,
    CaptureResult,
    ShelfItemLabel,
)
from store_emulator.domain.rack import RACK_LEVELS
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.capture import (
    ClassicDetector,
    GroundingDinoDetector,
    VLMLabeler,
    add_capture_racks,
    capture_shelf,
    gdino_available,
    render_overlay,
    replace_rack_face,
    sku_for,
)
from store_emulator.engine.capture.bands import (
    band_levels,
    deskewed_frame,
    detect_bands,
)
from store_emulator.engine.capture.catalog_match import (
    match_category,
    price_minor_units,
    typical_price,
)
from store_emulator.engine.capture.detect import (
    Detection,
    classic_detect,
    normalize_boxes,
    refine_detections,
)
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.planogram import fit_row
from store_emulator.engine.capture.synthetic import SyntheticShelf, make_scene
from store_emulator.engine.layout_gen.catalog import CATEGORY_LABELS
from store_emulator.engine.layout_gen.templates import generate_store
from store_emulator.engine.prompting import display_price
from store_emulator.engine.validation import list_blocked_faces, validate


def _scene(template: str = "urban_cvs", rack_index: int = 2, *, seed: int = 7, severity: str = "mild",
           currency: str = "USD", blocks: int = 1, width: int | None = None) -> SyntheticShelf:
    store = generate_store(template, seed=1, currency=currency)
    racks = [r for r in store.racks if r.slots]
    rack = racks[rack_index]
    return make_scene(rack, rack.slots[0].face, currency=currency, seed=seed, severity=severity,  # type: ignore[arg-type]
                      blocks=blocks, columns=4 * blocks, width=width or (768 if blocks == 1 else 1280))


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _matches(preds: list[tuple[float, float, float, float]], gts: list[tuple[float, float, float, float]]) -> int:
    pairs = sorted(((_iou(p, g), i, j) for i, p in enumerate(preds) for j, g in enumerate(gts)), reverse=True)
    used_p: set[int] = set()
    used_g: set[int] = set()
    for v, i, j in pairs:
        if v < 0.5:
            break
        if i not in used_p and j not in used_g:
            used_p.add(i)
            used_g.add(j)
    return len(used_p)


@pytest.mark.parametrize("blocks,width", [(1, 128), (1, 768), (2, 768), (2, 1280), (4, 768)])
def test_synthetic_geometry_matches_renderer(blocks: int, width: int) -> None:
    """Ground-truth boxes sit exactly on the rendered packages (dark outline on the left edge)."""
    scene = _scene(severity="clean", blocks=blocks, width=width)
    px = scene.image.load()
    assert px is not None
    for f in scene.facings:
        x1, y1, _, y2 = (round(v) for v in f.box)
        edge = px[x1, (y1 + y2) // 2]
        assert isinstance(edge, tuple)
        assert max(edge[:3]) < 90, f"no package outline at {f.box} ({edge})"


def test_frame_point_mapping_round_trip() -> None:
    photo = Image.new("RGB", (900, 700), (200, 200, 200))
    frame = make_frame(photo, angle=7.5)
    pts = [(10.0, 20.0), (450.0, 350.0), (880.0, 690.0)]
    back = frame.to_image_points(frame.to_work_points(pts))
    assert np.allclose(np.array(back), np.array(pts), atol=1e-6)


@pytest.mark.parametrize("severity", ["clean", "mild"])
def test_bands_follow_shelves(severity: str) -> None:
    scene = _scene(severity=severity)
    frame = deskewed_frame(scene.image)
    bands = detect_bands(frame)
    assert len(bands) == RACK_LEVELS
    assert band_levels(len(bands)) == [4, 3, 2, 1]
    for f in scene.facings:
        (cx, cy), = frame.to_work_points([((f.box[0] + f.box[2]) / 2, (f.box[1] + f.box[3]) / 2)])
        band = bands[f.row]
        assert band.top_at(cx) <= cy <= band.bottom_at(cx)


def test_band_level_mapping() -> None:
    assert band_levels(1) == [3]
    assert band_levels(3) == [4, 3, 1]
    assert band_levels(4) == [4, 3, 2, 1]
    assert band_levels(6) == [4, 4, 3, 2, 2, 1]


def test_classic_detector_facings_and_gaps() -> None:
    scene = _scene(seed=11, blocks=2)
    frame = deskewed_frame(scene.image)
    dets = classic_detect(frame, detect_bands(frame))
    facings = [frame.to_image_box(d.x1, d.y1, d.x2, d.y2) for d in dets if d.kind == "facing"]
    gaps = [frame.to_image_box(d.x1, d.y1, d.x2, d.y2) for d in dets if d.kind == "gap"]
    preds = [(b.x1, b.y1, b.x2, b.y2) for b in facings]
    tp = _matches(preds, [f.box for f in scene.facings])
    assert tp / len(preds) >= 0.9 and tp / len(scene.facings) >= 0.9
    if scene.gaps:
        found = _matches([(b.x1, b.y1, b.x2, b.y2) for b in gaps], [g.box for g in scene.gaps])
        assert found / len(scene.gaps) >= 0.5


def test_refine_drops_container_multishelf_and_tag_boxes() -> None:
    scene = _scene(severity="clean")
    frame = deskewed_frame(scene.image)
    bands = detect_bands(frame)
    gt = [Detection(*f.box, score=0.9, source="test") for f in scene.facings]
    w, h = frame.size
    junk = [
        Detection(5, 5, w - 5, h - 5, score=0.95, source="test"),                       # whole rack
        Detection(gt[0].x1, gt[0].y1, gt[0].x2, gt[0].y2 + 1.5 * bands[0].height, score=0.9, source="test"),
        Detection(gt[0].x1, gt[0].y2 + 2, gt[0].x1 + 40, gt[0].y2 + 22, score=0.9, source="test"),  # price tag
    ]
    kept, kept_bands = refine_detections(frame, bands, gt + junk, fill=False)
    assert kept_bands == bands
    assert len(kept) == len(gt)
    assert all(d.band >= 0 for d in kept)


def test_vlm_box_conventions() -> None:
    size = (800, 600)
    assert normalize_boxes([[100, 50, 300, 250]], size, model="qwen2.5-vl") == [(100, 50, 300, 250)]
    assert normalize_boxes([[500, 500, 1000, 1000]], size, model="qwen3-vl") == [(400, 300, 800, 600)]
    # Gemini answers [ymin, xmin, ymax, xmax] on 0–1000.
    assert normalize_boxes([[0, 250, 500, 500]], size, model="gemini-3.8-flash") == [(200, 0, 400, 300)]
    assert normalize_boxes([[0.1, 0.1, 0.5, 0.5]], size) == [(80, 60, 400, 300)]
    # Values that overflow the image cannot be pixels → 0–1000.
    assert normalize_boxes([[100, 100, 900, 950]], size)[0] == pytest.approx((80, 60, 720, 570))


class _ColorOracleVLM:
    """Fake VLM: identifies the product from the package colour of the crop (renderer colours are
    unique per product name) and answers with the ground-truth label."""

    def __init__(self, scene: SyntheticShelf, *, with_price: bool = True) -> None:
        self.with_price = with_price
        self.palette: list[tuple[np.ndarray, str, int]] = []
        arr = np.asarray(scene.image, dtype=np.float32)
        for f in scene.facings:
            x1, y1, x2, _ = (round(v) for v in f.box)
            patch = arr[y1 + 4:y1 + 14, x1 + (x2 - x1) // 2 - 10:x1 + (x2 - x1) // 2 + 10].reshape(-1, 3)
            self.palette.append((np.median(patch, axis=0), f.item.name, f.item.price))
        self.currency = scene.currency
        self.calls = 0

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        self.calls += 1
        img = Image.open(io.BytesIO(base64.b64decode(image_url.split(",", 1)[1]))).convert("RGB")
        arr = np.asarray(img, dtype=np.float32)
        h, w = arr.shape[:2]
        patch = arr[int(0.08 * h):int(0.16 * h), w // 2 - 10:w // 2 + 10].reshape(-1, 3)
        color = np.median(patch, axis=0)
        _, name, price = min(self.palette, key=lambda p: float(np.linalg.norm(p[0] - color)))
        label = ShelfItemLabel(
            name=name, category="soft drink", confidence=9,
            price_text=display_price(price, self.currency) if self.with_price else "",
        )
        return response_model.model_validate(label.model_dump())


def _gt_runs(scene: SyntheticShelf) -> list[tuple[int, str, int, int]]:
    runs: dict[tuple[int, int], list[str | int]] = {}
    for f in scene.facings:
        key = (f.row, f.run)
        if key in runs:
            runs[key][2] = int(runs[key][2]) + 1
        else:
            runs[key] = [f.item.name, f.item.price, 1]
    return [(row, str(v[0]), int(v[1]), int(v[2])) for (row, _), v in sorted(runs.items())]


def test_capture_with_fake_vlm_builds_planogram() -> None:
    scene = _scene(severity="clean", seed=21)
    fake = _ColorOracleVLM(scene)
    run = asyncio.run(capture_shelf(scene.image, detector=ClassicDetector(), labeler=VLMLabeler(fake, currency="USD"),
                                    currency="USD", rack_type="fridge"))
    result = run.result
    assert [b.level for b in result.bands] == [4, 3, 2, 1]
    expected = _gt_runs(scene)
    got = [(i.band, i.name, i.price, i.facings) for i in sorted(result.items, key=lambda i: (i.band, i.order))]
    assert got == expected
    assert fake.calls == len(result.items)  # one VLM call per product, not per facing
    assert result.vlm_calls == len(result.items)
    for item in result.items:
        assert item.sku == sku_for(item.name, item.brand, item.size)
        assert item.category == "soft_drinks" and not item.price_estimated
    assert result.dominant_category == "soft_drinks"
    assert len(result.gaps) == len(scene.gaps)
    png = render_overlay(scene.image, result)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_unreadable_tags_fall_back_to_typical_prices() -> None:
    scene = _scene(severity="clean", seed=21)
    run = asyncio.run(capture_shelf(scene.image, detector=ClassicDetector(),
                                    labeler=VLMLabeler(_ColorOracleVLM(scene, with_price=False), currency="USD")))
    for item in run.result.items:
        assert item.price_estimated and item.price is not None and item.price > 0
        expected, _ = typical_price(item.category, item.name, "USD")
        assert item.price == expected


def test_unlabeled_capture_counts_products() -> None:
    scene = _scene(severity="mild", seed=5)
    run = asyncio.run(capture_shelf(scene.image, detector=ClassicDetector()))
    result = run.result
    assert len(result.items) >= len(_gt_runs(scene)) - 2
    assert abs(result.facings - len(scene.facings)) <= 2
    assert all(i.name.startswith("Product ") and not i.labeled for i in result.items)
    assert len({i.sku for i in result.items}) == len(result.items)


def test_price_units_and_categories() -> None:
    assert price_minor_units(ShelfItemLabel(price_text="$2.49"), "USD", 229) == 249
    assert price_minor_units(ShelfItemLabel(price=249), "USD", 229) == 249       # cents without the point
    assert price_minor_units(ShelfItemLabel(price=3), "USD", 229) == 300
    assert price_minor_units(ShelfItemLabel(price_text="1,800원"), "KRW", 2000) == 1800
    assert price_minor_units(ShelfItemLabel(price=1.8), "KRW", 2000) == 1800     # read as thousands
    assert price_minor_units(ShelfItemLabel(price_text="12,50 €"), "EUR", 1000) == 1250
    assert price_minor_units(ShelfItemLabel(), "USD", 229) is None
    assert match_category("beer", "Cass Fresh 500ml") == "beer_alcohol"
    assert match_category("instant noodles", "Shin Ramyun") == "instant_food"
    assert match_category("", "캔커피 175ml") == "energy_coffee"
    assert match_category("shampoo", "Intense Repair") == "health_beauty"


def test_catalog_names_without_pack_sizes_keep_their_category_and_price() -> None:
    assert match_category("", "Ginger Ale", rack_type="fridge") == "soft_drinks"
    assert typical_price("soft_drinks", "Ginger Ale", "USD")[0] == 189
    assert match_category("", "Carrot Ginger Juice 350ml", rack_type="fridge") == "juice_menu"
    assert typical_price("juice_menu", "Carrot Ginger Juice", "USD")[0] == 599
    assert typical_price("soft_drinks", "Cola 500ml", "USD")[0] == 229
    assert typical_price("soft_drinks", "Cola 1.5L", "USD")[0] == 349
    assert match_category("", "Salmon Nigiri 2pc", rack_type="fridge") == "sushi_menu"


def _item(i: int, level: int, facings: int, name: str, x: float, price: int = 199) -> CaptureItem:
    return CaptureItem(
        id=f"i{i:02d}", band=RACK_LEVELS - level, level=level, order=i, facings=facings, name=name, price=price,
        sku=sku_for(name, "", ""), boxes=[Box(x1=x + k * 50, y1=0, x2=x + (k + 1) * 50, y2=40) for k in range(facings)],
        labeled=True, category="chips",
    )


def test_fit_row_keeps_most_faced_products() -> None:
    items = [_item(0, 3, 1, "A", 0), _item(1, 3, 4, "B", 60), _item(2, 3, 2, "C", 300), _item(3, 3, 1, "D", 420),
             _item(4, 3, 3, "E", 480)]
    fitted, dropped = fit_row(items, 4)
    assert [it.name for it, _ in fitted] == ["A", "B", "C", "E"]   # shelf order kept
    assert [d.name for d in dropped] == ["D"]
    assert sum(n for _, n in fitted) == 4 and all(n >= 1 for _, n in fitted)
    fitted, _ = fit_row([_item(0, 3, 2, "A", 0), _item(1, 3, 1, "B", 120)], 4)
    assert [(it.name, n) for it, n in fitted] == [("A", 2), ("B", 1)]


def _result(rows: dict[int, list[tuple[str, int]]]) -> CaptureResult:
    items: list[CaptureItem] = []
    for level, products in rows.items():
        x = 0.0
        for name, facings in products:
            items.append(_item(len(items), level, facings, name, x))
            x += 50 * facings + 5
    return CaptureResult(image_size=(1000, 800), items=items, currency="USD", dominant_category="chips")


def test_replace_rack_face_keeps_other_faces() -> None:
    store = generate_store("urban_cvs", seed=0)
    gondola = next(r for r in store.racks if {s.face for s in r.slots} == {Face.N, Face.S})
    result = _result({4: [("A", 2), ("B", 1)], 3: [("C", 3), ("D", 2), ("E", 1), ("F", 1), ("G", 1)], 1: [("H", 1)]})
    new, report = replace_rack_face(store, result, gondola.id, Face.N)
    rack = next(r for r in new.racks if r.id == gondola.id)
    north = {s.level: [i.name for i in s.items] for s in rack.slots if s.face == Face.N}
    assert north == {4: ["A", "A", "B"], 3: ["C", "D", "E", "F"], 1: ["H"]}
    assert report.dropped == ["G"] and report.notes
    south_before = [s for s in gondola.slots if s.face == Face.S]
    assert [s for s in rack.slots if s.face == Face.S] == south_before
    assert store.racks == generate_store("urban_cvs", seed=0).racks  # input untouched
    with pytest.raises(ValueError):
        replace_rack_face(store, result, "nope")


def test_known_products_keep_their_store_sku() -> None:
    store = generate_store("urban_cvs", seed=0)
    existing = next(i for _, s in store.all_slots for i in s.items)
    rack = next(r for r in store.racks if r.slots)
    result = _result({3: [(existing.name, 2), ("Brand-new Gadget", 1)]})
    new, report = replace_rack_face(store, result, rack.id, rack.slots[0].face)
    level3 = next(s for r in new.racks if r.id == rack.id for s in r.slots if s.face == rack.slots[0].face and s.level == 3)
    assert [i.sku for i in level3.items[:2]] == [existing.sku, existing.sku]
    assert level3.items[2].sku == sku_for("Brand-new Gadget", "", "")
    assert any("keep their SKU" in n for n in report.notes)


def test_new_racks_on_free_floor() -> None:
    store = generate_store("mini_mart", seed=0)
    result = _result({4: [("A", 3), ("B", 3), ("C", 3)], 3: [("D", 2), ("E", 2)], 2: [("F", 5)]})
    new, report = add_capture_racks(store, [result])
    assert len(report.rack_ids) == 3                       # 9 facings on the widest level → 3 racks
    added = [r for r in new.racks if r.id in report.rack_ids]
    assert all(r.rack_desc == "chips" and r.rack_name.endswith("(photo)") for r in added)
    xs = sorted(r.position for r in added)
    assert len({p[0] for p in xs}) == 1 or len({p[1] for p in xs}) == 1   # one straight run
    assert not [i for i in validate(new) if i.severity == "error"]
    blocked = {(b.rack_id, b.face) for b in list_blocked_faces(new)}
    assert all((rid, report.face) not in blocked for rid in report.rack_ids)
    names = [i.name for r in added for s in r.slots for i in s.items]
    assert {"A", "B", "C", "D", "E", "F"} <= set(names)
    assert sum(1 for n in names if n == "A") == 3


def test_new_rack_needs_free_floor() -> None:
    store = Store(id="s", name="tiny", type="convenience", grid_size=(1, 1))
    with pytest.raises(ValueError):
        add_capture_racks(store, [_result({3: [("A", 1)]})])


def test_category_labels_cover_capture_categories() -> None:
    assert {"soft_drinks", "chips", "beer_alcohol"} <= set(CATEGORY_LABELS)


@pytest.mark.skipif(not gdino_available() or os.environ.get("PARASTORE_TEST_GDINO") != "1",
                    reason="needs the capture extra (torch, transformers) and PARASTORE_TEST_GDINO=1 (downloads ~700 MB)")
def test_grounding_dino_detects_rendered_facings() -> None:
    scene = _scene(severity="mild", seed=31)
    detector = GroundingDinoDetector()
    try:
        run = asyncio.run(capture_shelf(scene.image, detector=detector))
    finally:
        detector.close()
    preds = [(b.x1, b.y1, b.x2, b.y2) for i in run.result.items for b in i.boxes]
    assert _matches(preds, [f.box for f in scene.facings]) >= 0.7 * len(scene.facings)


def test_a_model_that_answers_no_product_fails_the_capture() -> None:
    from store_emulator.engine.capture.pipeline import CaptureModelFailed

    class _Unreachable:
        async def generate_structured_with_image_async(self, *a, **k):
            raise ConnectionError("APIConnectionError: Connection error.")

    scene = _scene(severity="clean", seed=21)
    with pytest.raises(CaptureModelFailed, match="Connection error"):
        asyncio.run(capture_shelf(scene.image, detector=ClassicDetector(), labeler=VLMLabeler(_Unreachable(), currency="USD")))  # type: ignore[arg-type]
