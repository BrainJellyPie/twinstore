"""Shelf Lab use cases on a capture: counterfactual photo edits, sim2real panels, compliance audits.

Files per capture (`.data/<pid>/captures/<cid>/lab/`):
- edits/<eid>/image.jpg   the edited photo
- edits/<eid>/mask.png    ground truth: white where pixels were rewritten
- edits/<eid>/edit.json   EditedShelf (edits, changed boxes, the planogram the photo now shows)
- jobs/<jid>/status.json  LabJobStatus (polled by the UI)
- jobs/<jid>/report.json  Sim2RealReport or AuditReport
Package images for "replace" edits live per project in `.data/<pid>/lab_assets/<aid>.png`.
"""

import asyncio
import io
import json
import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Literal, cast

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator

from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.shelf_lab import (
    AuditReport,
    EditedShelf,
    LabJobStatus,
    PhotoEdit,
    Sim2RealCondition,
    Sim2RealReport,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face, RESOURCE_ID_PATTERN, ResourceId
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.shelf_lab import (
    apply_edits,
    build_views,
    glance_panel,
    summarize,
)
from store_emulator.engine.shelf_lab.audit import diff_face, match_field, price_findings
from store_emulator.engine.shelf_lab.edits import cut_out
from store_emulator.engine.shelf_lab.rival import RivalComparison, compare_rival

from .async_executor import executor
from .capture import capture_image_path, capture_llm_config, get_capture
from .currencies import project_currency, simulation_currency
from .errors import AppError
from .presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from .storage.io import DATA_DIR, now_iso, read_json, write_json
from .storage.setups import metadata_path, personas_path, read_setup
from .town import get_town, save_town

logger = logging.getLogger(__name__)

_SAFE_ID = re.compile(RESOURCE_ID_PATTERN)
MAX_PACKAGE_BYTES = 10 * 1024 * 1024


class Sim2RealRequest(BaseModel):
    conditions: list[Sim2RealCondition] = Field(default_factory=lambda: cast(list[Sim2RealCondition], ["render", "photo", "photo_raw"]))
    personas: int = Field(default=24, ge=2, le=400, description="shoppers in the panel (a deterministic sample of the project's personas)")
    model: str = Field(default="", description='model reference; "" = the app vision model')
    edit_id: str = Field(default="", description="run on an edited photo instead of the original")
    seed: int = 0
    situation: str = Field(default="", max_length=200, description='today\'s context, e.g. "heatwave, 34°C"')

    @field_validator("conditions")
    @classmethod
    def _requires_photo(cls, conditions: list[Sim2RealCondition]) -> list[Sim2RealCondition]:
        if not any(c != "render" for c in conditions):
            raise ValueError("sim2real needs at least one photo condition to compare with the render")
        return conditions


class AuditRequest(BaseModel):
    setup_id: ResourceId = Field(description="layout holding the reference planogram")
    rack_id: str = Field(description="the rack the photo shows")
    face: Literal["N", "S", "E", "W"] | None = Field(default=None, description="default: the face holding most products")
    edit_id: str = Field(default="", description="audit an edited photo instead of the original")
    panel: int = Field(default=300, ge=20, le=3000, description="shoppers per paired simulation")
    max_stockouts: int = Field(default=8, ge=0, le=30, description="missing products priced one by one")
    seed: int = 1


class PackageAsset(BaseModel):
    """A product image: a package for Shelf Lab's "new package" edit, a marketing test or a survey."""
    asset_id: str
    name: str
    width: int
    height: int
    brand: str = ""
    sku: str = ""                     # the store product it shows, if any
    cut_out: bool = False             # the background was removed on upload
    created_at: str = ""


class PackageUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=40)
    sku: str | None = Field(default=None, max_length=80)


def _check_id(value: str, what: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise AppError(f"invalid {what}: {value}", 400)


def _lab_dir(pid: str, cid: str) -> Path:
    _check_id(pid, "project id")
    _check_id(cid, "capture id")
    return Path(DATA_DIR) / pid / "captures" / cid / "lab"


def _assets_dir(pid: str) -> Path:
    _check_id(pid, "project id")
    return Path(DATA_DIR) / pid / "lab_assets"


def _capture(pid: str, cid: str) -> tuple[Image.Image, CaptureResult]:
    view = get_capture(pid, cid)
    if view.result is None:
        raise AppError("this capture has no planogram yet", 409)
    photo = Image.open(capture_image_path(pid, cid, overlay=False))
    photo.load()
    return photo.convert("RGB"), view.result


# ── package images ──────────────────────────────────────────────────────────────

def _asset(png: Path) -> PackageAsset:
    meta = cast(dict[str, Any], read_json(png.with_suffix(".json"))) if png.with_suffix(".json").exists() else {}
    with Image.open(png) as im:
        return PackageAsset(
            asset_id=png.stem, name=str(meta.get("name", png.stem)), width=im.width, height=im.height,
            brand=str(meta.get("brand", "")), sku=str(meta.get("sku", "")), cut_out=bool(meta.get("cut_out", False)),
            created_at=str(meta.get("created_at", "")),
        )


def upload_package(
    pid: str, data: bytes, filename: str, *, name: str = "", brand: str = "", sku: str = "", remove_background: bool = True,
) -> PackageAsset:
    """Store a product image. Photos on a plain background get it removed (a transparent PNG is kept as is)."""
    if not metadata_path(pid).exists():
        raise AppError(f"project not found: {pid}", 404)
    if len(data) > MAX_PACKAGE_BYTES:
        raise AppError("package image too large (max 10 MB)", 413)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        img = ImageOps.exif_transpose(img)
    except Image.DecompressionBombError as e:
        raise AppError("Image dimensions are too large; reduce the resolution and try again.", 413) from e
    except (UnidentifiedImageError, OSError) as e:
        raise AppError("not an image the server can read (use PNG, JPEG or WebP)", 400) from e
    img.thumbnail((1200, 1200))
    aid = f"pkg_{uuid.uuid4().hex[:8]}"
    folder = _assets_dir(pid)
    folder.mkdir(parents=True, exist_ok=True)
    rgba = img.convert("RGBA")
    transparent = img.mode in ("RGBA", "LA", "P") and cast(tuple[int, int], rgba.getchannel("A").getextrema())[0] < 250
    cut = remove_background and not transparent
    out = cut_out(img.convert("RGB")) if cut else (rgba if transparent else img.convert("RGB"))
    out.save(folder / f"{aid}.png", format="PNG")
    meta = {"name": (name.strip() or Path(filename).stem)[:80] or aid, "brand": brand.strip()[:40], "sku": sku.strip()[:80],
            "cut_out": cut, "created_at": now_iso()}
    write_json(folder / f"{aid}.json", meta)
    return _asset(folder / f"{aid}.png")


def list_packages(pid: str) -> list[PackageAsset]:
    folder = _assets_dir(pid)
    assets = [_asset(png) for png in folder.glob("pkg_*.png")] if folder.exists() else []
    return sorted(assets, key=lambda a: a.created_at, reverse=True)


def update_package(pid: str, aid: str, upd: PackageUpdate) -> PackageAsset:
    png = package_path(pid, aid)
    meta = cast(dict[str, Any], read_json(png.with_suffix(".json"))) if png.with_suffix(".json").exists() else {}
    for key, value in upd.model_dump(exclude_none=True).items():
        meta[key] = str(value).strip()
    write_json(png.with_suffix(".json"), meta)
    return _asset(png)


def delete_package(pid: str, aid: str) -> None:
    png = package_path(pid, aid)
    png.unlink()
    png.with_suffix(".json").unlink(missing_ok=True)


def package_path(pid: str, aid: str) -> Path:
    _check_id(aid, "package id")
    path = _assets_dir(pid) / f"{aid}.png"
    if not path.exists():
        raise AppError(f"package image not found: {aid}", 404)
    return path


# ── counterfactual edits ────────────────────────────────────────────────────────

def _edit_dir(pid: str, cid: str, eid: str) -> Path:
    _check_id(eid, "edit id")
    return _lab_dir(pid, cid) / "edits" / eid


def _mask(size: tuple[int, int], shelf: EditedShelf) -> Image.Image:
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    for c in shelf.changes:
        d.rectangle((c.box.x1, c.box.y1, c.box.x2 - 1, c.box.y2 - 1), fill=255)
    return mask


def create_edit(pid: str, cid: str, edits: list[PhotoEdit]) -> EditedShelf:
    if not edits:
        raise AppError("no edits given", 400)
    photo, result = _capture(pid, cid)
    packages: dict[str, Image.Image] = {}
    for e in edits:
        if e.kind == "replace" and e.asset_id:
            img = Image.open(package_path(pid, e.asset_id))
            img.load()
            packages[e.asset_id] = img
    try:
        out = apply_edits(photo, result, edits, packages=packages, seed=cid)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    eid = f"edit_{uuid.uuid4().hex[:6]}"
    shelf = EditedShelf(edit_id=eid, capture_id=cid, edits=edits, changes=out.changes, result=out.result,
                        promos=out.promos, image_size=out.image.size, created_at=now_iso())
    folder = _edit_dir(pid, cid, eid)
    folder.mkdir(parents=True, exist_ok=True)
    out.image.save(folder / "image.jpg", format="JPEG", quality=93)
    _mask(out.image.size, shelf).save(folder / "mask.png", format="PNG")
    write_json(folder / "edit.json", json.loads(shelf.model_dump_json()))
    return shelf


def list_edits(pid: str, cid: str) -> list[EditedShelf]:
    folder = _lab_dir(pid, cid) / "edits"
    shelves = [EditedShelf.model_validate(read_json(p)) for p in folder.glob("*/edit.json")] if folder.exists() else []
    return sorted(shelves, key=lambda s: s.created_at, reverse=True)


def get_edit(pid: str, cid: str, eid: str) -> EditedShelf:
    path = _edit_dir(pid, cid, eid) / "edit.json"
    if not path.exists():
        raise AppError(f"edit not found: {eid}", 404)
    return EditedShelf.model_validate(read_json(path))


def edit_file(pid: str, cid: str, eid: str, kind: Literal["image", "mask"]) -> Path:
    path = _edit_dir(pid, cid, eid) / ("image.jpg" if kind == "image" else "mask.png")
    if not path.exists():
        raise AppError(f"edit not found: {eid}", 404)
    return path


def delete_edit(pid: str, cid: str, eid: str) -> None:
    folder = _edit_dir(pid, cid, eid)
    if not folder.exists():
        raise AppError(f"edit not found: {eid}", 404)
    shutil.rmtree(folder)


def _photo_and_result(pid: str, cid: str, edit_id: str) -> tuple[Image.Image, CaptureResult]:
    if not edit_id:
        return _capture(pid, cid)
    shelf = get_edit(pid, cid, edit_id)
    img = Image.open(edit_file(pid, cid, edit_id, "image"))
    img.load()
    return img.convert("RGB"), shelf.result


# ── background jobs ─────────────────────────────────────────────────────────────

def _job_dir(pid: str, cid: str, jid: str) -> Path:
    _check_id(jid, "job id")
    return _lab_dir(pid, cid) / "jobs" / jid


def _write_status(pid: str, status: LabJobStatus) -> None:
    write_json(_job_dir(pid, status.capture_id, status.job_id) / "status.json", status.model_dump(mode="json"))


class LabJobView(BaseModel):
    status: LabJobStatus
    sim2real: Sim2RealReport | None = None
    audit: AuditReport | None = None


def get_job(pid: str, cid: str, jid: str) -> LabJobView:
    folder = _job_dir(pid, cid, jid)
    if not (folder / "status.json").exists():
        raise AppError(f"lab job not found: {jid}", 404)
    status = LabJobStatus.model_validate(read_json(folder / "status.json"))
    view = LabJobView(status=status)
    report = folder / "report.json"
    if report.exists():
        data = read_json(report)
        if status.kind == "sim2real":
            view.sim2real = Sim2RealReport.model_validate(data)
        else:
            view.audit = AuditReport.model_validate(data)
    return view


def list_jobs(pid: str, cid: str) -> list[LabJobStatus]:
    folder = _lab_dir(pid, cid) / "jobs"
    jobs = [LabJobStatus.model_validate(read_json(p)) for p in folder.glob("*/status.json")] if folder.exists() else []
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)


def _personas(pid: str) -> list[Persona]:
    path = personas_path(pid)
    personas = [Persona.model_validate(p) for p in cast(list[dict[str, Any]], read_json(path))] if path.exists() else []
    if not personas:
        raise AppError("the project has no personas yet", 400)
    return personas


def _store_type(pid: str) -> str:
    meta = cast(dict[str, Any], read_json(metadata_path(pid))) if metadata_path(pid).exists() else {}
    return str(meta.get("store_type", "convenience") or "convenience")


def _new_job(pid: str, cid: str, kind: Literal["sim2real", "audit"]) -> LabJobStatus:
    jid = f"{'s2r' if kind == 'sim2real' else 'aud'}_{uuid.uuid4().hex[:6]}"
    status = LabJobStatus(job_id=jid, kind=kind, capture_id=cid, status="pending", stage="queued", created_at=now_iso())
    _job_dir(pid, cid, jid).mkdir(parents=True, exist_ok=True)
    _write_status(pid, status)
    return status


def _finish(pid: str, status: LabJobStatus, report: BaseModel | None, error: str = "") -> None:
    if report is not None:
        write_json(_job_dir(pid, status.capture_id, status.job_id) / "report.json", json.loads(report.model_dump_json()))
        status.status, status.stage, status.progress = "completed", "done", 1.0
    else:
        status.status, status.error = "failed", error[:500]
    status.finished_at = now_iso()
    _write_status(pid, status)


def start_sim2real(pid: str, cid: str, req: Sim2RealRequest, config: SimulationConfig) -> LabJobStatus:
    photo, result = _photo_and_result(pid, cid, req.edit_id)
    if not any(i.labeled for i in result.items):
        raise AppError("sim2real needs a capture whose products were read (run the capture with a vision model)", 409)
    currency = project_currency(pid, config.currency)
    if result.currency != currency:
        raise AppError(f"Capture currency must match project shopper budgets ({currency}); budgets are not converted automatically.", 422)
    llm_config = capture_llm_config(config, req.model)
    if llm_config is None:
        raise AppError("sim2real needs a vision model", 400)
    personas = select_personas(_personas(pid), req.personas, seed=req.seed)
    conditions = list(dict.fromkeys(req.conditions))
    if "render" not in conditions:
        conditions.insert(0, "render")
    status = _new_job(pid, cid, "sim2real")
    store_type = _store_type(pid)

    def run() -> None:
        t0 = time.perf_counter()
        status.status, status.stage = "running", "glancing"
        _write_status(pid, status)
        last = 0.0

        def on_progress(done: int, total: int) -> None:
            nonlocal last
            status.progress = round(done / max(1, total), 3)
            if time.monotonic() - last > 0.5 or done == total:
                last = time.monotonic()
                _write_status(pid, status)

        try:
            views = build_views(photo, result, seed=req.seed)
            llm = LiteLLMClient(llm_config)
            answers = asyncio.run(glance_panel(
                llm, views, personas, conditions=conditions, cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS,
                store_type=store_type, currency=result.currency, situation=req.situation, seed=req.seed,
                on_progress=on_progress,
            ))
            stats, agreement = summarize(answers, conditions)
            if not agreement:
                raise ValueError("No successful render/photo response pairs; check the vision model and retry.")
            notes: list[str] = []
            failed = sum(bool(a.error) for a in answers)
            if failed:
                notes.append(f"{failed} of {len(answers)} model responses failed; comparisons use successful response pairs only")
            compared = {a.condition for a in agreement}
            for condition in conditions:
                if condition != "render" and condition not in compared:
                    notes.append(f"No complete response pairs for {condition}; comparison omitted")
            dropped = sum(1 for i in result.items if i.sku not in views.products)
            if dropped:
                notes.append(f"{dropped} product(s) of the photo did not fit the rendered twin and carry no tag")
            if result.gaps:
                notes.append(f"the photo shows {len(result.gaps)} empty stretch(es); the render leaves them out")
            report = Sim2RealReport(
                job_id=status.job_id, capture_id=cid, edit_id=req.edit_id, model=llm_config.model,
                personas=len(personas), conditions=conditions, products=views.products, stats=stats,
                agreement=agreement, answers=answers, notes=notes, seconds=round(time.perf_counter() - t0, 1),
            )
            _finish(pid, status, report)
        except Exception as e:
            logger.exception(f"[shelf_lab] sim2real {status.job_id} failed")
            _finish(pid, status, None, f"{type(e).__name__}: {e}")

    executor.submit(run)
    return status


def _load_store(pid: str, setup_id: str) -> Store:
    if not re.fullmatch(RESOURCE_ID_PATTERN, pid) or not re.fullmatch(RESOURCE_ID_PATTERN, setup_id):
        raise AppError("invalid project or setup id", 400)
    try:
        setup = read_setup(pid, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404) from None
    data = setup.get("store")
    if not data:
        raise AppError("this layout has no store yet", 400)
    return Store.model_validate(data)


def _face_of(store: Store, rack_id: str, face: str | None) -> Face:
    rack = next((r for r in store.racks if r.id == rack_id), None)
    if rack is None:
        raise AppError(f"rack not found: {rack_id}", 404)
    if face:
        return Face(face)
    counts: dict[Face, int] = {}
    for s in rack.slots:
        counts[s.face] = counts.get(s.face, 0) + len(s.items)
    if not counts:
        raise AppError(f"rack {rack_id} holds no products to audit against", 400)
    return max(counts, key=lambda f: counts[f])


def start_audit(pid: str, cid: str, req: AuditRequest, config: SimulationConfig) -> LabJobStatus:
    _, result = _photo_and_result(pid, cid, req.edit_id)
    store = _load_store(pid, req.setup_id)
    currency = simulation_currency(pid, store, config.currency)
    if result.currency != currency:
        raise AppError(f"Capture currency must match layout prices and project shopper budgets ({currency}); prices are not converted automatically.", 422)
    face = _face_of(store, req.rack_id, req.face)
    personas = _personas(pid)
    status = _new_job(pid, cid, "audit")

    def run() -> None:
        t0 = time.perf_counter()
        status.status, status.stage = "running", "comparing"
        _write_status(pid, status)
        try:
            rack = next(r for r in store.racks if r.id == req.rack_id)
            field = match_field(store, result)
            levels, findings = diff_face(rack, face, field, result.currency)
            expected = sum(lv.expected_facings for lv in levels)
            compliance = round(sum(lv.matched_facings for lv in levels) / expected, 4) if expected else 1.0
            days = max(1, len({p.day for p in personas}))
            visitors_per_day = round(len(personas) / days, 1)
            panel = select_personas(personas, req.panel, seed=req.seed)
            status.stage, status.progress = "simulating", 0.2
            _write_status(pid, status)
            run_config = config.model_copy(update={"engine_type": EngineType.RULE_BASED, "seed": req.seed, "currency": currency})
            evaluator = LayoutEvaluator(run_config, panel, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(),
                                        OptimizeObjective.REVENUE_PER_VISITOR)
            missing = list(dict.fromkeys(f.sku for f in findings if f.kind == "missing" and f.sku))
            impact, _ = asyncio.run(price_findings(evaluator, store, field, req.rack_id, face, panel, missing=missing,
                                                   visitors_per_day=visitors_per_day, max_stockouts=req.max_stockouts))
            for f in findings:
                loss = impact.losses.get(f.sku) if f.kind == "missing" else None
                if loss is not None:
                    f.loss_per_day, f.loss_ci = loss[0], (loss[1], loss[2])
            whole = impact.whole
            notes: list[str] = []
            if len(missing) > req.max_stockouts:
                notes.append(f"{len(missing) - req.max_stockouts} more missing product(s) were not priced one by one")
            report = AuditReport(
                job_id=status.job_id, capture_id=cid, setup_id=req.setup_id, rack_id=req.rack_id, face=face.value,
                currency=result.currency, compliance=compliance, levels=levels, findings=findings, impact=whole,
                visitors_per_day=visitors_per_day,
                revenue_delta_per_day=round(whole.diff * visitors_per_day, 1) if whole else None,
                revenue_delta_ci=(round(whole.ci_low * visitors_per_day, 1), round(whole.ci_high * visitors_per_day, 1)) if whole else None,
                panel_size=len(panel), notes=notes, seconds=round(time.perf_counter() - t0, 1),
            )
            _finish(pid, status, report)
        except Exception as e:
            logger.exception(f"[shelf_lab] audit {status.job_id} failed")
            _finish(pid, status, None, f"{type(e).__name__}: {e}")

    executor.submit(run)
    return status


# ── rival shelf ─────────────────────────────────────────────────────────────────

class RivalRequest(BaseModel):
    setup_id: ResourceId = Field(description="our layout, whose products and prices the rival's shelf is compared with")
    venue_id: str = Field(default="", description="the rival's venue in the neighborhood (optional)")
    apply: bool = Field(default=False, description="scale the venue's pull by the price-adjusted factor")
    elasticity: float = Field(default=1.0, ge=0.0, le=3.0)


class RivalReport(BaseModel):
    comparison: RivalComparison
    venue_id: str = ""
    previous_attractiveness: float | None = None
    attractiveness: float | None = None


def compare_rival_capture(pid: str, cid: str, req: RivalRequest, *, default_currency: str = "USD") -> RivalReport:
    _, result = _capture(pid, cid)
    if not any(i.labeled for i in result.items):
        raise AppError("the rival's products have not been read (run the capture with a vision model or name them)", 409)
    store = _load_store(pid, req.setup_id)
    currency = store.currency or project_currency(pid, default_currency)
    if result.currency != currency:
        raise AppError(f"Capture currency must match layout prices ({currency}); prices are not converted automatically.", 422)
    comparison = compare_rival(store, result, elasticity=req.elasticity)
    report = RivalReport(comparison=comparison, venue_id=req.venue_id)
    if req.venue_id:
        town = get_town(pid)
        venue = town.get_venue(req.venue_id) if town else None
        if town is None or venue is None:
            raise AppError(f"venue not found: {req.venue_id}", 404)
        report.previous_attractiveness = venue.attractiveness
        report.attractiveness = venue.attractiveness
        if req.apply and comparison.suggested_pull_factor is not None:
            new = round(min(3.0, max(0.2, venue.attractiveness * comparison.suggested_pull_factor)), 3)
            save_town(pid, town.model_copy(update={"venues": [
                v.model_copy(update={"attractiveness": new}) if v.id == venue.id else v for v in town.venues]}))
            report.attractiveness = new
    return report
