"""Shelf Lab, offline: counterfactual edits with exact ground truth, sim2real panels with a fake VLM,
and the compliance audit priced by paired rule-based simulation."""

import asyncio
import base64
import io
import json
import random
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pydantic import BaseModel

from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.capture import Box, CaptureGap, CaptureItem, CaptureResult
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.shelf_lab import PhotoEdit
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.capture import ClassicDetector, capture_shelf, sku_for
from store_emulator.engine.capture.synthetic import GTFacing, SyntheticShelf, make_scene
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.shelf_lab import (
    apply_edits,
    build_views,
    glance_panel,
    summarize,
)
from store_emulator.engine.shelf_lab.audit import diff_face, match_field, price_findings
from store_emulator.engine.shelf_lab.edits import synth_package
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"
DRINK_1 = "r_b5cf7836"  # fridge, stocked face S


@pytest.fixture(scope="module")
def store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


@pytest.fixture(scope="module")
def personas() -> list[Persona]:
    return [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]


def _labeled(scene: SyntheticShelf, result: CaptureResult) -> CaptureResult:
    """The capture with every product named and priced from the scene's ground truth."""
    items = []
    for item in result.items:
        b = item.boxes[0]
        f = min(scene.facings, key=lambda f: ((f.box[0] + f.box[2]) / 2 - b.cx) ** 2 + ((f.box[1] + f.box[3]) / 2 - b.cy) ** 2)
        items.append(item.model_copy(update={"name": f.item.name, "price": f.item.price, "price_estimated": False,
                                             "sku": sku_for(f.item.name, "", ""), "labeled": True, "confidence": 9}))
    return result.model_copy(update={"items": items})


def _gt_capture(scene: SyntheticShelf) -> CaptureResult:
    """A perfect capture of the scene: one item per ground-truth run of identical facings."""
    runs: dict[tuple[int, int], list[GTFacing]] = {}
    for f in scene.facings:
        runs.setdefault((f.row, f.run), []).append(f)
    items: list[CaptureItem] = []
    order: dict[int, int] = {}
    for (row, _), facings in sorted(runs.items()):
        f0 = facings[0]
        items.append(CaptureItem(
            id=f"i{len(items) + 1:02d}", band=row, level=f0.level, order=order.setdefault(row, 0), facings=len(facings),
            boxes=[Box(x1=f.box[0], y1=f.box[1], x2=f.box[2], y2=f.box[3]) for f in facings],
            sku=sku_for(f0.item.name, "", ""), name=f0.item.name, price=f0.item.price, labeled=True, confidence=9,
        ))
        order[row] += 1
    gaps = [CaptureGap(band=g.row, level=g.level, box=Box(x1=g.box[0], y1=g.box[1], x2=g.box[2], y2=g.box[3])) for g in scene.gaps]
    return CaptureResult(image_size=scene.image.size, currency="USD", rack_type="fridge", items=items, gaps=gaps)


def _scene_and_capture(store: Store, *, gap_rate: float = 0.12, seed: int = 21) -> tuple[SyntheticShelf, CaptureResult]:
    rack = next(r for r in store.racks if r.id == DRINK_1)
    scene = make_scene(rack, Face.S, currency="USD", seed=seed, severity="clean", gap_rate=gap_rate)
    result = asyncio.run(capture_shelf(scene.image, detector=ClassicDetector(), currency="USD", rack_type="fridge")).result
    return scene, _labeled(scene, result)


def _reference_store(store: Store, scene: SyntheticShelf) -> Store:
    """The sample store whose drinks fridge holds exactly the scene's ground-truth planogram on face S."""
    new = store.model_copy(deep=True)
    rack = next(r for r in new.racks if r.id == DRINK_1)
    rack.slots = [s for s in rack.slots if s.face != Face.S] + [s for s in scene.rack.slots if s.face == Face.S]
    return new


def _unchanged_outside(before: Image.Image, after: Image.Image, boxes: list[tuple[float, float, float, float]]) -> bool:
    a = np.asarray(before.convert("RGB"), dtype=np.int16)
    b = np.asarray(after.convert("RGB"), dtype=np.int16)
    keep = np.ones(a.shape[:2], dtype=bool)
    for x1, y1, x2, y2 in boxes:
        keep[int(y1):int(np.ceil(y2)), int(x1):int(np.ceil(x2))] = False
    return bool(np.all(a[keep] == b[keep]))


# ── edits ──────────────────────────────────────────────────────────────────────

def test_each_edit_changes_only_its_boxes_and_the_planogram(store: Store) -> None:
    scene, result = _scene_and_capture(store)
    items = sorted(result.items, key=lambda i: (i.band, i.order))
    a, b, c, d = items[0], items[-1], items[1], items[2]
    edits = [
        PhotoEdit(kind="swap", item_id=a.id, other_id=b.id),
        PhotoEdit(kind="remove", item_id=c.id),
        PhotoEdit(kind="replace", item_id=d.id, name="Volt Cola", brand="Parastore", price=199),
        PhotoEdit(kind="price", item_id=b.id, price=99),
        PhotoEdit(kind="promo", item_id=a.id, promo="1+1"),
    ]
    out = apply_edits(scene.image, result, edits, seed="t")
    boxes = [(ch.box.x1, ch.box.y1, ch.box.x2, ch.box.y2) for ch in out.changes]
    assert _unchanged_outside(scene.image, out.image, boxes)
    assert not _unchanged_outside(scene.image, out.image, [])  # something did change

    after = {i.id: i for i in out.result.items}
    assert after[a.id].name == b.name and after[b.id].sku == a.sku  # swapped identities, positions kept
    assert after[a.id].facings == a.facings and after[a.id].boxes == a.boxes
    assert c.id not in after and len(out.result.gaps) == len(result.gaps) + c.facings
    assert after[d.id].name == "Volt Cola" and after[d.id].price == 199 and after[d.id].sku == sku_for("Volt Cola", "Parastore", "")
    assert after[b.id].price == 99 and not after[b.id].price_estimated
    assert out.promos == {a.id: "1+1"}
    assert {ch.kind for ch in out.changes} == {"swap", "remove", "replace", "price", "promo"}
    assert sum(1 for ch in out.changes if ch.kind == "swap") == a.facings + b.facings


def test_edits_are_deterministic_and_validate_ids(store: Store) -> None:
    scene, result = _scene_and_capture(store)
    item = result.items[0]
    edit = [PhotoEdit(kind="remove", item_id=item.id)]
    one = apply_edits(scene.image, result, edit, seed="s")
    two = apply_edits(scene.image, result, edit, seed="s")
    assert np.array_equal(np.asarray(one.image), np.asarray(two.image))
    with pytest.raises(ValueError, match="not found"):
        apply_edits(scene.image, result, [PhotoEdit(kind="remove", item_id="nope")])
    with pytest.raises(ValueError, match="itself"):
        apply_edits(scene.image, result, [PhotoEdit(kind="swap", item_id=item.id, other_id=item.id)])


def test_uploaded_package_without_alpha_is_cut_out(store: Store) -> None:
    scene, result = _scene_and_capture(store)
    pkg = Image.new("RGB", (200, 300), (255, 255, 255))
    pkg.paste(synth_package("Volt Cola").convert("RGB"), (0, 0), synth_package("Volt Cola").getchannel("A"))
    item = result.items[0]
    out = apply_edits(scene.image, result, [PhotoEdit(kind="replace", item_id=item.id, name="Volt Cola", asset_id="p1")],
                      packages={"p1": pkg})
    assert any(ch.kind == "replace" for ch in out.changes)
    with pytest.raises(ValueError, match="package image not found"):
        apply_edits(scene.image, result, [PhotoEdit(kind="replace", item_id=item.id, asset_id="missing")])


# ── sim2real ───────────────────────────────────────────────────────────────────

class _FavouriteVLM:
    """Fake VLM: every shopper names the same product, whatever the view."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[int, int]] = []

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        img = Image.open(io.BytesIO(base64.b64decode(image_url.split(",", 1)[1])))
        self.calls.append(img.size)
        return response_model.model_validate(ShelfGlance(product=self.name, number=3, interest=7, reason="likes it").model_dump())


def _cue(rng: random.Random) -> BehaviorCue:
    return BehaviorCue(state="목마름", emotion="", purse="", company="")


def test_sim2real_views_share_marks_and_products(store: Store, personas: list[Persona]) -> None:
    from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS

    scene, result = _scene_and_capture(store, gap_rate=0.0)
    views = build_views(scene.image, result, seed=3)
    render, photo = views.views["render"], views.views["photo"]
    assert set(views.products) == {i.sku for i in result.items}
    first_mark: dict[str, int] = {}
    for m in render.items:
        first_mark.setdefault(m.item.sku, m.mark)
    assert {m.item.sku: m.mark for m in photo.items} == first_mark  # the photo's tags carry the render's numbers
    assert Image.open(io.BytesIO(photo.png)).size[0] == 768

    favourite = result.items[0].name
    llm = _FavouriteVLM(favourite)
    panel = select_personas(personas, 6, seed=0)
    answers = asyncio.run(glance_panel(llm, views, panel, conditions=["render", "photo", "photo_raw"], cue_sampler=_cue,
                                       patterns=BEHAVIOR_PATTERNS, seed=1))
    assert len(answers) == 18 and len(llm.calls) == 18
    stats, agreement = summarize(answers, ["render", "photo", "photo_raw"])
    assert all(s.answers == 6 and s.none_rate == 0.0 for s in stats)
    assert [a.condition for a in agreement] == ["photo", "photo_raw"]
    assert all(a.same_pick == 1.0 and a.pairs == 6 for a in agreement)
    assert {a.sku for a in answers} == {result.items[0].sku}


# ── audit ──────────────────────────────────────────────────────────────────────

def test_audit_finds_stockouts_and_prices_them(store: Store, personas: list[Persona]) -> None:
    rack0 = next(r for r in store.racks if r.id == DRINK_1)
    scene = make_scene(rack0, Face.S, currency="USD", seed=21, severity="clean", gap_rate=0.0)
    result = _gt_capture(scene)
    reference = _reference_store(store, scene)
    rack = next(r for r in reference.racks if r.id == DRINK_1)

    field = match_field(reference, result)
    levels, findings = diff_face(rack, Face.S, field, "USD")
    assert sum(lv.matched_facings for lv in levels) == sum(lv.expected_facings for lv in levels)
    assert not [f for f in findings if f.kind in ("missing", "unexpected")]

    target = min(result.items, key=lambda i: (i.band, i.order))
    edited = apply_edits(scene.image, result, [PhotoEdit(kind="remove", item_id=target.id)]).result
    field = match_field(reference, edited)
    levels, findings = diff_face(rack, Face.S, field, "USD")
    missing = [f for f in findings if f.kind == "missing"]
    assert [f.name for f in missing] == [target.name] and missing[0].box is not None
    assert sum(lv.matched_facings for lv in levels) < sum(lv.expected_facings for lv in levels)

    panel = select_personas(personas, 120, seed=0)
    evaluator = _evaluator(panel)
    impact, as_photographed = asyncio.run(price_findings(evaluator, reference, field, DRINK_1, Face.S, panel,
                                                         missing=[missing[0].sku], visitors_per_day=100.0))
    assert impact.whole is not None and missing[0].sku in impact.losses
    loss, lo, hi = impact.losses[missing[0].sku]
    assert lo <= loss <= hi
    shown = next(r for r in as_photographed.racks if r.id == DRINK_1)
    assert missing[0].sku not in {i.sku for s in shown.slots if s.face == Face.S for i in s.items}


def _evaluator(panel: list[Persona]) -> LayoutEvaluator:
    from store_emulator.application.presets.behavior import (
        BEHAVIOR_PATTERNS,
        sample_cue,
    )

    return LayoutEvaluator(SimulationConfig(seed=5), panel, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(),
                           OptimizeObjective.REVENUE_PER_VISITOR)


# ── benchmark ──────────────────────────────────────────────────────────────────

def test_benchmark_writes_triples_with_exact_masks(tmp_path: Path) -> None:
    from store_emulator.engine.shelf_lab.bench import synthetic_shelves, write_bench

    counts = write_bench(tmp_path, synthetic_shelves(templates=["urban_cvs"], per_template=2, severities=["mild"]),
                         kinds=["swap", "remove", "price"], per_kind=1, seed=3)
    assert counts["shelves"] == 2 and counts["swap"] == counts["remove"] == counts["price"] == 2
    records = [json.loads(line) for line in (tmp_path / "index.jsonl").read_text().splitlines()]
    assert len(records) == 6
    for rec in records:
        files = {k: tmp_path / v for k, v in rec["files"].items()}
        original = Image.open(files["original"])
        edited = Image.open(files["counterfactual"])
        mask = np.asarray(Image.open(files["mask"])) > 0
        diff = np.any(np.asarray(original.convert("RGB"), dtype=np.int16) != np.asarray(edited.convert("RGB"), dtype=np.int16), axis=2)
        assert diff.any() and not (diff & ~mask).any()  # every changed pixel is inside the ground-truth mask


def test_levers_measure_the_pick_shift(tmp_path: Path, personas: list[Persona]) -> None:
    from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
    from store_emulator.engine.shelf_lab.bench import synthetic_shelves, write_bench
    from store_emulator.engine.shelf_lab.levers import (
        load_counterfactuals,
        run_lever,
        summarize_levers,
    )

    write_bench(tmp_path, synthetic_shelves(templates=["urban_cvs"], per_template=1, severities=["clean"]),
                kinds=["remove", "price"], per_kind=1, seed=5)
    cfs = load_counterfactuals(tmp_path)
    panel = select_personas(personas, 4, seed=0)
    outcomes = []
    for cf in cfs:
        target = next(i for i in cf.before.items if i.id == cf.edit.item_id)
        outcomes.append(asyncio.run(run_lever(_FavouriteVLM(target.name), cf, panel, cue_sampler=_cue, patterns=BEHAVIOR_PATTERNS)))
    by_kind = {o.kind: o for o in outcomes}
    assert by_kind["price"].picked_before == by_kind["price"].picked_after == 1.0
    assert by_kind["remove"].picked_before == 1.0 and by_kind["remove"].picked_after == 0.0  # the product is gone
    summary = {s.kind: s for s in summarize_levers(outcomes)}
    assert summary["remove"].delta_picked == -1.0 and summary["price"].delta_picked == 0.0


# ── rival shelf ────────────────────────────────────────────────────────────────

def test_rival_shelf_price_index_and_overlap(store: Store) -> None:
    from store_emulator.engine.shelf_lab.rival import compare_rival

    rack = next(r for r in store.racks if r.id == DRINK_1)
    scene = make_scene(rack, Face.S, currency="USD", seed=21, severity="clean", gap_rate=0.0)
    reference = _reference_store(store, scene)
    rival = _gt_capture(scene)
    cheaper = rival.model_copy(update={"items": [i.model_copy(update={"price": round((i.price or 0) * 0.9)}) for i in rival.items]})
    report = compare_rival(reference, cheaper)
    assert report.matched == len({i.name for i in rival.items}) and report.only_rival == []
    assert report.price_index == pytest.approx(0.9, abs=0.01)
    assert report.suggested_pull_factor == pytest.approx(1 / 0.9, abs=0.02)
    assert 0 < report.overlap <= 1
    newcomer = cheaper.model_copy(update={"items": [*cheaper.items, cheaper.items[0].model_copy(update={"id": "x1", "name": "Rival Own Brand Cola", "sku": "x"})]})
    assert compare_rival(reference, newcomer).only_rival == ["Rival Own Brand Cola"]
