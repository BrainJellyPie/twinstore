"""Marketing studio use cases: the product image library, A/B experiments on a layout, and survey panels.

Files per project (`.data/<pid>/`):
- lab_assets/<aid>.png, <aid>.json        product images (shared with Shelf Lab's "new package" edits)
- marketing/experiments/<eid>/            request.json, status.json, report.json
- marketing/surveys/<sid>/                request.json, status.json, report.json, board.jpg
- marketing/conjoints/<cid>/              request.json, status.json, report.json
"""
# (reuses Shelf Lab's private store and persona helpers)

import asyncio
import base64
import csv
import io
import json
import logging
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

from PIL import Image
from pydantic import BaseModel

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.marketing import (
    ConjointReport,
    ConjointRequest,
    ConjointRespondent,
    ExperimentReport,
    ExperimentRequest,
    JobStatus,
    ScaleSummary,
    SegmentRow,
    SurveyAnswer,
    ShelfPreview,
    ShelfPreviewRequest,
    ShelfTestReport,
    ShelfTestRequest,
    SurveyReport,
    SurveyRequest,
)
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing import (
    apply_changes,
    likert_summary,
    preference_shares,
    price_response,
    run_experiment,
    survey_panel,
    van_westendorp,
)
from store_emulator.engine.marketing.conjoint import conjoint_panel, estimate, none_share
from store_emulator.engine.marketing.factorial import capture_paired_outcomes
from store_emulator.engine.marketing.reading import StudyReading
from store_emulator.engine.marketing.report import (
    ReportNarrative,
    conjoint_report_html,
    report_html,
    report_markdown,
    shelf_report_html,
    survey_report_html,
    write_narrative,
)
from store_emulator.engine.marketing.shelf_test import compare_shelves, pick_shares, shelf_panel
from store_emulator.engine.perception.shelf_render import render_face
from store_emulator.engine.marketing.survey import LETTERS, SCALES, stimulus_board
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.prompting import display_price
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.application.product_images import project_image_loader
from store_emulator.engine.files import remove_tree

from .async_executor import executor
from .capture import capture_llm_config
from .errors import AppError, job_failure, model_failure
from .currencies import project_currency, simulation_currency
from .presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from .providers import answered_by, assistive_client, assistive_model, build_client, ensure_resolvable
from .shelf_lab import (
    _check_id,  # pyright: ignore[reportPrivateUsage]
    _load_store,  # pyright: ignore[reportPrivateUsage]
    _personas,  # pyright: ignore[reportPrivateUsage]
    package_path,
)
from .simulation import with_engine_model
from .storage.io import DATA_DIR, now_iso, read_json, write_json
from .storage.setups import read_setup

logger = logging.getLogger(__name__)

Kind = Literal["experiment", "survey", "pitch", "shelf", "conjoint"]


def _root(pid: str, kind: Kind) -> Path:
    _check_id(pid, "project id")
    return Path(DATA_DIR) / pid / "marketing" / {"pitch": "pitches", "shelf": "shelf_tests"}.get(kind, f"{kind}s")


def _job_dir(pid: str, kind: Kind, jid: str) -> Path:
    _check_id(jid, f"{kind} id")
    return _root(pid, kind) / jid


def _write_status(pid: str, status: JobStatus) -> None:
    write_json(_job_dir(pid, status.kind, status.job_id) / "status.json", status.model_dump(mode="json"))


def _new_job(pid: str, kind: Kind, name: str, request: BaseModel) -> JobStatus:
    prefix = {"experiment": "exp", "survey": "srv", "pitch": "pit", "shelf": "slf", "conjoint": "cjt"}[kind]
    jid = f"{prefix}_{uuid.uuid4().hex[:12]}"
    status = JobStatus(job_id=jid, kind=kind, name=name, status="pending", stage="queued", created_at=now_iso())
    folder = _job_dir(pid, kind, jid)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "request.json", request.model_dump(mode="json"))
    _write_status(pid, status)
    return status


def _finish(pid: str, status: JobStatus, report: BaseModel | None, error: str = "") -> None:
    if report is not None:
        write_json(_job_dir(pid, status.kind, status.job_id) / "report.json", json.loads(report.model_dump_json()))
        status.status, status.stage, status.progress = "completed", "done", 1.0
    else:
        status.status, status.error = "failed", error[:500]
    status.finished_at = now_iso()
    _write_status(pid, status)


def list_jobs(pid: str, kind: Kind) -> list[JobStatus]:
    folder = _root(pid, kind)
    jobs = [JobStatus.model_validate(read_json(p)) for p in folder.glob("*/status.json")] if folder.exists() else []
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)


def _status(pid: str, kind: Kind, jid: str) -> JobStatus:
    path = _job_dir(pid, kind, jid) / "status.json"
    if not path.exists():
        raise AppError(f"{kind} not found: {jid}", 404)
    return JobStatus.model_validate(read_json(path))


def delete_job(pid: str, kind: Kind, jid: str) -> None:
    status = _status(pid, kind, jid)
    if status.status in ("pending", "running"):
        raise AppError(f"{kind} is still {status.status}; wait until it finishes before deleting it", 409)
    folder = _job_dir(pid, kind, jid)
    if not folder.exists():
        raise AppError(f"{kind} not found: {jid}", 404)
    remove_tree(folder)


def recover_running_jobs() -> int:
    """Mark jobs left in flight by a previous server process as failed."""
    recovered = 0
    for folder in ("experiments", "surveys", "pitches", "shelf_tests", "conjoints"):
        for path in Path(DATA_DIR).glob(f"*/marketing/{folder}/*/status.json"):
            try:
                status = JobStatus.model_validate(read_json(path))
                if status.status in ("pending", "running"):
                    status.status = "failed"
                    status.stage = "interrupted"
                    status.error = "interrupted by server restart; start a new job to retry"
                    status.finished_at = now_iso()
                    write_json(path, status.model_dump(mode="json"))
                    recovered += 1
            except (OSError, ValueError) as e:
                logger.warning(f"[marketing] could not recover {path}: {e}")
    return recovered


_ZERO_DECIMAL = {"KRW", "JPY", "VND", "IDR", "CLP", "ISK", "HUF", "TWD"}


def _minor_per_major(currency: str) -> int:
    return 1 if currency.upper() in _ZERO_DECIMAL else 100


# ── experiments ─────────────────────────────────────────────────────────────────

def start_experiment(pid: str, req: ExperimentRequest, config: SimulationConfig) -> JobStatus:
    control = _load_store(pid, req.setup_id)
    personas = _personas(pid)
    currency = simulation_currency(pid, control, config.currency)
    config = config.model_copy(update={"currency": currency})
    uris: dict[str, str] = {}
    for v in req.variants:
        for c in v.changes:
            if c.kind == "package" and c.asset_id:
                uris[c.asset_id] = "file://" + str(package_path(pid, c.asset_id).resolve())
    built: list[tuple[str, Store, list[str], list[str]]] = []
    for v in req.variants:
        store, applied, warnings = apply_changes(control, v.changes, package_uris=uris, minor_per_major=_minor_per_major(currency))
        if not applied:
            raise AppError(f"variant '{v.name}' changes nothing: {'; '.join(warnings) or 'no changes'}", 400)
        built.append((v.name, store, applied, warnings))
    if req.engine == "rule" and any(c.kind == "package" for v in req.variants for c in v.changes):
        raise AppError("packaging is only visible to vision shoppers: choose the vision engine", 400)
    if req.engine == "vlm":
        # Vision shoppers whose every call fails fall back to rule-based decisions: a model that cannot answer would
        # give a report that looks fine and says "no winner".
        vision = config.model_copy(update={"engine_type": EngineType.VLM_GLANCE})
        try:
            ensure_resolvable(with_engine_model(vision, req.model) if req.model else vision)
        except ValueError as e:
            raise AppError(str(e), 400) from e
    name = req.name.strip() or " vs ".join(["Control", *[v.name for v in req.variants]])
    status = _new_job(pid, "experiment", name, req)

    def run() -> None:
        t0 = time.perf_counter()
        status.status, status.stage = "running", "simulating"
        _write_status(pid, status)
        try:
            panel = select_personas(personas, req.panel, seed=req.seed)
            run_config = config.model_copy(update={"seed": req.seed})
            pathfinder = AStarPathFinder(diagonal=run_config.diagonal_moves)
            engine = None
            model = ""
            if req.engine == "vlm":
                run_config = run_config.model_copy(update={"engine_type": EngineType.VLM_GLANCE})
                if req.model:
                    run_config = with_engine_model(run_config, req.model)
                llm = build_client(run_config.llm_for(EngineType.VLM_GLANCE), run_config.ensemble)
                engine = build_engine(run_config, llm=llm, pathfinder=pathfinder, image_loader=project_image_loader(pid))
                model = req.model or run_config.llm_for(EngineType.VLM_GLANCE).model
            evaluator = LayoutEvaluator(run_config, panel, sample_cue, BEHAVIOR_PATTERNS, pathfinder,
                                        OptimizeObjective.REVENUE_PER_VISITOR, engine=engine)

            def progress(p: float, stage: str) -> None:
                status.progress, status.stage = round(p, 3), stage
                _write_status(pid, status)

            def retain_outcomes(base: list[CustomerResult], runs: list[list[CustomerResult]]) -> None:
                try:
                    snapshot = capture_paired_outcomes(status.job_id, currency, req, [p.id for p in panel],
                        [("Control", control, []), *[(name, store, warnings) for name, store, _, warnings in built]], [base, *runs])
                except ValueError:
                    logger.warning("Paired outcomes not retained for %s: invalid identities, inconsistent purchases or unsupported numeric limits", status.job_id)
                    return
                write_json(_job_dir(pid, "experiment", status.job_id) / "paired-outcomes.json", snapshot.model_dump(mode="json"))

            control_result, results, winner = asyncio.run(run_experiment(
                evaluator, control, built, panel, req.focus_skus, on_progress=progress, on_outcomes=retain_outcomes, seed=req.seed,
            ))
            days = max(1, len({p.day for p in personas}))
            panel_size = control_result.customers if control_result.customers is not None else len(panel)
            notes = list(control_result.warnings)
            if panel_size < 100:
                notes.append("Fewer than 100 shoppers per variant: differences under ~5 % are hard to tell from noise.")
            if req.engine == "rule" and any(c.kind == "price" and not c.keep_reference for v in req.variants for c in v.changes):
                notes.append("Rule shoppers react to a price relative to the usual one (and to their budget); a new everyday price "
                             "resets that reference. Keep the current price as the reference, or use vision shoppers, to measure price response.")
            if req.engine == "rule" and any(c.kind == "promo" for v in req.variants for c in v.changes):
                notes.append("The rule-based shoppers read promotion signs as a generic impulse boost; vision shoppers see the sign itself.")
            report = ExperimentReport(
                experiment_id=status.job_id, name=name, setup_id=req.setup_id, engine=req.engine, model=model,
                panel_size=panel_size, currency=currency, visitors_per_day=round(len(personas) / days, 1),
                focus_skus=req.focus_skus, control=control_result, variants=results, winner=winner, notes=notes,
                price_response=price_response(control_result, results),
                seconds=round(time.perf_counter() - t0, 1),
            )
            _finish(pid, status, report)
        except Exception as e:
            logger.exception(f"[marketing] experiment {status.job_id} failed")
            _finish(pid, status, None, job_failure(e, "The test failed"))

    executor.submit(run)
    return status


class ExperimentView(JobStatus):
    report: ExperimentReport | None = None
    request: ExperimentRequest | None = None   # what was asked, for "duplicate and edit"


def _request[T: BaseModel](pid: str, kind: Kind, jid: str, model: type[T]) -> T | None:
    path = _job_dir(pid, kind, jid) / "request.json"
    try:
        return model.model_validate(read_json(path)) if path.exists() else None
    except ValueError:
        return None  # written by an older version with a different schema


def get_experiment(pid: str, eid: str) -> ExperimentView:
    status = _status(pid, "experiment", eid)
    path = _job_dir(pid, "experiment", eid) / "report.json"
    report = ExperimentReport.model_validate(read_json(path)) if path.exists() else None
    return ExperimentView(**status.model_dump(), report=report, request=_request(pid, "experiment", eid, ExperimentRequest))


# ── experiment report ───────────────────────────────────────────────────────────

def _report_inputs(pid: str, eid: str) -> tuple[ExperimentReport, str, ReportNarrative | None]:
    view = get_experiment(pid, eid)
    if view.report is None:
        raise AppError("the A/B test has no results yet", 409)
    try:
        layout = str(read_setup(pid, view.report.setup_id).get("name") or "")
    except FileNotFoundError:
        layout = ""
    path = _job_dir(pid, "experiment", eid) / "narrative.json"
    narrative = ReportNarrative.model_validate(read_json(path)) if path.exists() else None
    return view.report, layout, narrative


def experiment_report_html(pid: str, eid: str) -> str:
    return report_html(*_report_inputs(pid, eid))


def experiment_report_markdown(pid: str, eid: str) -> str:
    return report_markdown(*_report_inputs(pid, eid))


def write_experiment_narrative(pid: str, eid: str, model: str, config: SimulationConfig) -> ReportNarrative:
    """A model's commentary on the report, kept with the experiment and added to the write-up."""
    report, layout, _ = _report_inputs(pid, eid)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.3, "max_tokens": 1500})
    try:
        model = assistive_model(model, llm_config)
        llm = assistive_client(model, llm_config)
        narrative = asyncio.run(write_narrative(llm, report, layout))
    except ValueError as e:
        raise AppError(str(e), 400) from e
    except Exception as e:  # provider errors reach the user as a message
        logger.warning(f"[marketing] narrative for {eid} failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The commentary could not be written"), 502) from e
    narrative.model = answered_by(llm, model)
    write_json(_job_dir(pid, "experiment", eid) / "narrative.json", narrative.model_dump(mode="json"))
    return narrative


def delete_experiment_narrative(pid: str, eid: str) -> None:
    (_job_dir(pid, "experiment", eid) / "narrative.json").unlink(missing_ok=True)


# ── surveys ─────────────────────────────────────────────────────────────────────

def _quota(personas: list[Persona], req: SurveyRequest | ShelfTestRequest | ConjointRequest) -> list[Persona]:
    out = [p for p in personas
           if (not req.age_groups or str(p.age_group) in req.age_groups) and (not req.genders or str(p.gender) in req.genders)]
    if not out:
        raise AppError("no personas match the quota", 400)
    return out


def start_survey(pid: str, req: SurveyRequest, config: SimulationConfig) -> JobStatus:
    _check_id(pid, "project id")
    currency = project_currency(pid, config.currency)
    if req.currency.upper() != currency:
        raise AppError(f"Survey currency must match project shopper budgets ({currency}); budgets are not converted automatically.", 422)
    req = req.model_copy(update={"currency": currency})
    images: list[Image.Image] = []
    for aid in req.stimuli:
        img = Image.open(package_path(pid, aid))
        img.load()
        images.append(img)
    names = [req.stimulus_names[i] if i < len(req.stimulus_names) and req.stimulus_names[i] else LETTERS[i]
             for i in range(len(images))]
    respondents = select_personas(_quota(_personas(pid), req), req.panel, seed=req.seed)
    llm_config = capture_llm_config(config, req.model)
    if llm_config is None:
        raise AppError("a survey needs a vision model", 400)
    # Respondents differ by persona; a little sampling temperature keeps answers from collapsing to one.
    llm_config = llm_config.model_copy(update={
        "max_tokens": 900, "temperature": 0.6, "cache_dir": str(Path(DATA_DIR) / "llm_cache" / "survey"),
    })
    board = stimulus_board(images, names)
    name = req.name.strip() or f"Concept test · {', '.join(names)}"
    status = _new_job(pid, "survey", name, req)
    board.save(_job_dir(pid, "survey", status.job_id) / "board.jpg", quality=90)

    def run() -> None:
        t0 = time.perf_counter()
        status.status, status.stage = "running", "asking"
        _write_status(pid, status)
        try:
            llm = LiteLLMClient(llm_config)
            minor = _minor_per_major(req.currency)
            reference = display_price(req.reference_price, req.currency) if req.reference_price is not None else ""
            answers = asyncio.run(survey_panel(
                llm, respondents, board, req.questions, len(images), context=req.context, currency=req.currency,
                reference_price=reference, minor_per_major=minor, seed=req.seed,
            ))
            _finish(pid, status, summarize_survey(status.job_id, name, llm_config.model, req, names, answers,
                                                   seconds=round(time.perf_counter() - t0, 1)))
        except Exception as e:
            logger.exception(f"[marketing] survey {status.job_id} failed")
            _finish(pid, status, None, job_failure(e, "The test failed"))

    executor.submit(run)
    return status


def summarize_survey(
    sid: str, name: str, model: str, req: SurveyRequest, names: list[str], answers: list[SurveyAnswer], *, seconds: float = 0.0,
) -> SurveyReport:
    ok = [a for a in answers if not a.error]
    if not ok:
        # A report of zero respondents (every scale 0 on a 1–5 scale) would read as a result.
        first = next((a.error for a in answers if a.error), "no answers")
        raise ValueError(f"No respondent could answer, so there is nothing to report. {first}")
    k = len(req.stimuli)
    scales: list[ScaleSummary] = []
    for q in SCALES:
        if q not in req.questions:
            continue
        for i in range(k):
            values = [cast(list[int], getattr(a, q))[i] for a in ok if len(getattr(a, q)) > i]
            scales.append(likert_summary(values, q, i))
    segments: list[SegmentRow] = []
    for field in ("age_group", "gender"):
        for value in sorted({getattr(a, field) for a in ok}):
            group = [a for a in ok if getattr(a, field) == value]
            vals: dict[str, float] = {}
            for q in SCALES:
                if q in req.questions:
                    for i in range(k):
                        xs = [cast(list[int], getattr(a, q))[i] for a in group if len(getattr(a, q)) > i]
                        if xs:
                            vals[f"{q}·{LETTERS[i]}"] = round(sum(xs) / len(xs), 2)
            if "preference" in req.questions and k > 1:
                for i in range(k):
                    vals[f"prefer·{LETTERS[i]}"] = round(sum(1 for a in group if a.preferred == i) / len(group), 3)
            segments.append(SegmentRow(segment=f"{'age' if field == 'age_group' else 'gender'} {value}", n=len(group), values=vals))
    notes = ["Synthetic respondents: use for screening and direction, and calibrate against a real panel before deciding."]
    errors = len(answers) - len(ok)
    if errors:
        notes.append(f"{errors} respondent(s) could not answer (model errors) and are left out.")
    return SurveyReport(
        survey_id=sid, name=name, model=model, stimuli=req.stimuli, stimulus_names=names, questions=req.questions,
        currency=req.currency, respondents=len(ok), errors=errors, scales=scales,
        segments=segments,
        price=van_westendorp(ok) if "price_vw" in req.questions else None,
        preference=preference_shares([a.preferred for a in ok if a.preferred is not None], names, k)
        if "preference" in req.questions and k > 1 else [],
        verbatims=[a.why for a in ok if a.why][:40], answers=answers, notes=notes, seconds=seconds,
    )


class SurveyView(JobStatus):
    report: SurveyReport | None = None
    request: SurveyRequest | None = None


def get_survey(pid: str, sid: str) -> SurveyView:
    status = _status(pid, "survey", sid)
    path = _job_dir(pid, "survey", sid) / "report.json"
    report = SurveyReport.model_validate(read_json(path)) if path.exists() else None
    return SurveyView(**status.model_dump(), report=report, request=_request(pid, "survey", sid, SurveyRequest))


def load_reading(pid: str, kind: Kind, jid: str) -> StudyReading | None:
    """The model's reading of a study (commentary and themes), if one was written."""
    path = _job_dir(pid, kind, jid) / "reading.json"
    return StudyReading.model_validate(read_json(path)) if path.exists() else None


def survey_report(pid: str, sid: str) -> str:
    view = get_survey(pid, sid)
    if view.report is None:
        raise AppError("the concept test has no answers yet", 409)
    board = _job_dir(pid, "survey", sid) / "board.jpg"
    return survey_report_html(view.report, board.read_bytes() if board.exists() else None, load_reading(pid, "survey", sid))


def survey_board_path(pid: str, sid: str) -> Path:
    path = _job_dir(pid, "survey", sid) / "board.jpg"
    if not path.exists():
        raise AppError(f"survey not found: {sid}", 404)
    return path


def _csv_cells(row: Sequence[object]) -> list[object]:
    return ["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
            for value in row]


def survey_csv(pid: str, sid: str) -> str:
    view = get_survey(pid, sid)
    if view.report is None:
        raise AppError("the survey has no answers yet", 409)
    r = view.report
    buf = io.StringIO()
    w = csv.writer(buf)
    k = len(r.stimuli)
    header = ["respondent", "age_group", "gender"]
    for q in SCALES:
        if q in r.questions:
            header += [f"{q}_{LETTERS[i]}" for i in range(k)]
    if "price_vw" in r.questions:
        header += ["too_cheap", "cheap", "expensive", "too_expensive"]
    if "preference" in r.questions:
        header.append("preferred")
    if "open" in r.questions:
        header.append("why")
    header.append("error")
    w.writerow(header)
    for a in r.answers:
        row: list[object] = [a.respondent, a.age_group, a.gender]
        for q in SCALES:
            if q in r.questions:
                vals = cast(list[int], getattr(a, q))
                row += [vals[i] if i < len(vals) else "" for i in range(k)]
        if "price_vw" in r.questions:
            row += [value if value is not None else "" for value in (a.too_cheap, a.cheap, a.expensive, a.too_expensive)]
        if "preference" in r.questions:
            row.append(LETTERS[a.preferred] if a.preferred is not None else "")
        if "open" in r.questions:
            row.append(a.why)
        row.append(a.error)
        w.writerow(_csv_cells(row))
    return buf.getvalue()


# ── shelf tests ─────────────────────────────────────────────────────────────────

class ShelfTestView(JobStatus):
    report: ShelfTestReport | None = None
    request: ShelfTestRequest | None = None


def _shelf_arms(pid: str, req: ShelfTestRequest | ShelfPreviewRequest, config: SimulationConfig) -> tuple[Rack, Rack, Face, list[str], list[str], str]:
    """Control and test rack, the face to show, what changed, warnings and the currency."""
    control = _load_store(pid, req.setup_id)
    rack = next((r for r in control.racks if r.id == req.rack_id), None)
    if rack is None:
        raise AppError(f"rack not in this layout: {req.rack_id}", 404)
    currency = simulation_currency(pid, control, config.currency)
    uris = {c.asset_id: "file://" + str(package_path(pid, c.asset_id).resolve()) for c in req.changes if c.kind == "package" and c.asset_id}
    test_store, applied, warnings = apply_changes(control, req.changes, package_uris=uris, minor_per_major=_minor_per_major(currency))
    test_rack = next(r for r in test_store.racks if r.id == req.rack_id)
    faces = {s.face for r in (rack, test_rack) for s in r.slots for i in s.items if not req.target_sku or i.sku == req.target_sku}
    face = Face(req.face) if req.face else (sorted(faces, key=lambda f: f.value)[0] if faces else None)
    if face is None or (req.target_sku and face not in faces):
        raise AppError("the target product is on neither shelf: move it there or pick another rack", 400)
    return rack, test_rack, face, applied, warnings, currency


def preview_shelf(pid: str, req: ShelfPreviewRequest, config: SimulationConfig) -> ShelfPreview:
    rack, test_rack, face, applied, warnings, currency = _shelf_arms(pid, req, config)

    def url(r: Rack) -> str:
        return "data:image/png;base64," + base64.b64encode(render_face(r, face, currency=currency, width=640, number_on_tag=False, image_loader=project_image_loader(pid)).png).decode()

    return ShelfPreview(face=face.value, control=url(rack), test=url(test_rack), applied=applied, warnings=warnings)


def start_shelf_test(pid: str, req: ShelfTestRequest, config: SimulationConfig) -> JobStatus:
    rack, test_rack, face, applied, warnings, currency = _shelf_arms(pid, req, config)
    if not applied:
        raise AppError(f"the test shelf changes nothing: {'; '.join(warnings) or 'no changes'}", 400)
    names = {i.sku: i.name for r in (rack, test_rack) for sl in r.slots for i in sl.items}
    target_name = names.get(req.target_sku, req.target_sku)
    respondents = select_personas(_quota(_personas(pid), req), req.panel, seed=req.seed)
    llm_config = capture_llm_config(config, req.model)
    if llm_config is None:
        raise AppError("a shelf test needs a vision model", 400)
    llm_config = llm_config.model_copy(update={
        "max_tokens": 400, "temperature": 0.6, "cache_dir": str(Path(DATA_DIR) / "llm_cache" / "shelf_test"),
    })
    name = req.name.strip() or f"Shelf test · {target_name}"
    status = _new_job(pid, "shelf", name, req)

    def run() -> None:
        t0 = time.perf_counter()
        status.status, status.stage = "running", "asking"
        _write_status(pid, status)
        try:
            for arm, arm_rack in (("control", rack), ("test", test_rack)):
                png = render_face(arm_rack, face, currency=currency, width=900, number_on_tag=False, image_loader=project_image_loader(pid)).png
                (_job_dir(pid, "shelf", status.job_id) / f"{arm}.png").write_bytes(png)
            choices = asyncio.run(shelf_panel(LiteLLMClient(llm_config), respondents, rack, test_rack, face, currency=currency, seed=req.seed, image_loader=project_image_loader(pid)))
            ok = [c for c in choices if not c.error]
            paired_ids = {c.respondent for c in ok if c.arm == "control"} & {c.respondent for c in ok if c.arm == "test"}
            if not paired_ids:
                raise ValueError("The vision model returned no complete response pairs; no shelf comparison is available.")
            paired = [c for c in ok if c.respondent in paired_ids]
            notes = ["Synthetic respondents looking at a rendered shelf: use for screening packs, prices and signs, then confirm in the field."]
            if len(paired_ids) < len(respondents):
                notes.append(f"{len(respondents) - len(paired_ids)} respondent(s) had incomplete responses and were excluded from all comparisons and pick shares.")
            if len(paired_ids) < 40:
                notes.append("Fewer than 40 respondents: only large differences in pick share are distinguishable from noise.")
            report = ShelfTestReport(
                test_id=status.job_id, name=name, setup_id=req.setup_id, rack_id=rack.id, rack_name=rack.rack_name or rack.id,
                face=face.value, target_sku=req.target_sku, target_name=target_name, model=llm_config.model, currency=currency,
                respondents=len(paired_ids), errors=len(choices) - len(ok), applied=applied, warnings=warnings,
                comparisons=compare_shelves(paired, req.target_sku, seed=req.seed), picks=pick_shares(paired, names),
                choices=choices, notes=notes, seconds=round(time.perf_counter() - t0, 1),
            )
            _finish(pid, status, report)
        except Exception as e:
            logger.exception(f"[marketing] shelf test {status.job_id} failed")
            _finish(pid, status, None, job_failure(e, "The test failed"))

    executor.submit(run)
    return status


def get_shelf_test(pid: str, tid: str) -> ShelfTestView:
    status = _status(pid, "shelf", tid)
    path = _job_dir(pid, "shelf", tid) / "report.json"
    report = ShelfTestReport.model_validate(read_json(path)) if path.exists() else None
    return ShelfTestView(**status.model_dump(), report=report, request=_request(pid, "shelf", tid, ShelfTestRequest))


def shelf_test_image(pid: str, tid: str, arm: Literal["control", "test"]) -> bytes:
    """The shelf face respondents saw in one arm (without badges)."""
    view = get_shelf_test(pid, tid)
    if view.report is None:
        raise AppError("the shelf test has no results yet", 409)
    path = _job_dir(pid, "shelf", tid) / f"{arm}.png"
    if not path.exists():
        raise AppError("This shelf test has no saved image; tests created before image snapshots cannot reproduce the original shelf.", 404)
    return path.read_bytes()


def shelf_test_report(pid: str, tid: str) -> str:
    view = get_shelf_test(pid, tid)
    if view.report is None:
        raise AppError("the shelf test has no results yet", 409)
    return shelf_report_html(view.report, shelf_test_image(pid, tid, "control"), shelf_test_image(pid, tid, "test"),
                             load_reading(pid, "shelf", tid))


# ── conjoint ────────────────────────────────────────────────────────────────────

def start_conjoint(pid: str, req: ConjointRequest, config: SimulationConfig) -> JobStatus:
    _check_id(pid, "project id")
    currency = project_currency(pid, config.currency)
    if req.prices and req.currency.upper() != currency:
        raise AppError(f"Conjoint prices must be in the project currency ({currency}); budgets are not converted automatically.", 422)
    req = req.model_copy(update={"currency": currency})
    respondents = select_personas(_quota(_personas(pid), req), req.panel, seed=req.seed)
    llm_config = capture_llm_config(config, req.model)
    if llm_config is None:
        raise AppError("a conjoint study needs a model", 400)
    llm_config = llm_config.model_copy(update={
        "max_tokens": 240 + 24 * req.tasks, "temperature": 0.6, "cache_dir": str(Path(DATA_DIR) / "llm_cache" / "conjoint"),
    })
    name = req.name.strip() or f"Conjoint · {req.product}"
    status = _new_job(pid, "conjoint", name, req)

    def run() -> None:
        t0 = time.perf_counter()
        status.status, status.stage = "running", "asking"
        _write_status(pid, status)
        try:
            answers = asyncio.run(conjoint_panel(
                LiteLLMClient(llm_config), respondents, req.attributes, req.prices, product=req.product, context=req.context,
                currency=currency, tasks=req.tasks, options=req.options, none_option=req.none_option, seed=req.seed,
            ))
            status.stage, status.progress = "estimating", 0.9
            _write_status(pid, status)
            _finish(pid, status, summarize_conjoint(status.job_id, name, llm_config.model, req, answers,
                                                     seconds=round(time.perf_counter() - t0, 1)))
        except Exception as e:
            logger.exception(f"[marketing] conjoint {status.job_id} failed")
            _finish(pid, status, None, job_failure(e, "The test failed"))

    executor.submit(run)
    return status


def summarize_conjoint(
    cid: str, name: str, model: str, req: ConjointRequest, answers: list[ConjointRespondent], *, seconds: float = 0.0,
) -> ConjointReport:
    ok = [a for a in answers if not a.error]
    est = estimate(ok, req.attributes, req.prices, none_option=req.none_option, currency=req.currency, seed=req.seed)
    if est is None:
        raise ValueError("No respondent answered the choice tasks; check the model and try again.")
    notes = ["Synthetic respondents: use the study to screen which attributes and levels matter and to shape a real conjoint, "
             "then calibrate against real choices before pricing on it."]
    errors = len(answers) - len(ok)
    if errors:
        notes.append(f"{errors} respondent(s) could not answer (model errors) and are left out.")
    if len(ok) < 30:
        notes.append("Fewer than 30 respondents: part-worth intervals are wide; read the order of levels, not the exact values.")
    if req.prices and (est.price_slope is None or est.price_slope >= 0):
        notes.append("Higher prices did not lower the chance of being chosen, so willingness to pay is not shown; "
                     "try a wider price range or a model that weighs budget more.")
    if est.fit.hit_rate < est.fit.chance_rate * 1.25:
        notes.append("The model predicts choices barely better than chance: answers look close to random.")
    share = none_share(ok)
    if req.none_option and share > 0.5:
        notes.append(f"Most choices ({share * 100:.0f} %) were “none”: the offers may sit outside what respondents expect to pay.")
    return ConjointReport(
        conjoint_id=cid, name=name, model=model, product=req.product, currency=req.currency, attributes=req.attributes,
        prices=req.prices, options=req.options, none_option=req.none_option, respondents=len(ok), errors=errors,
        none_share=share, part_worths=est.part_worths, importances=est.importances, price_slope=est.price_slope,
        price_mean=est.price_mean, none_utility=est.none_utility, fit=est.fit, segments=est.segments, answers=answers,
        verbatims=[a.why for a in ok if a.why][:40], notes=notes, seconds=seconds,
    )


class ConjointView(JobStatus):
    report: ConjointReport | None = None
    request: ConjointRequest | None = None


def get_conjoint(pid: str, cid: str) -> ConjointView:
    status = _status(pid, "conjoint", cid)
    path = _job_dir(pid, "conjoint", cid) / "report.json"
    report = ConjointReport.model_validate(read_json(path)) if path.exists() else None
    return ConjointView(**status.model_dump(), report=report, request=_request(pid, "conjoint", cid, ConjointRequest))


def conjoint_report(pid: str, cid: str) -> str:
    view = get_conjoint(pid, cid)
    if view.report is None:
        raise AppError("the conjoint study has no answers yet", 409)
    return conjoint_report_html(view.report, load_reading(pid, "conjoint", cid))


def conjoint_csv(pid: str, cid: str) -> str:
    """One row per option shown (long format), ready for re-estimation in other tools."""
    view = get_conjoint(pid, cid)
    if view.report is None:
        raise AppError("the conjoint study has no answers yet", 409)
    r = view.report
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_csv_cells(["respondent", "age_group", "gender", "task", "option", *[a.name for a in r.attributes],
                           *(["price"] if r.prices else []), "chosen"]))
    for a in r.answers:
        if a.error:
            continue
        for t, task in enumerate(a.tasks, start=1):
            for o, profile in enumerate(task.profiles):
                levels = [r.attributes[i].levels[profile[i]] for i in range(len(r.attributes))]
                price = [r.prices[profile[len(r.attributes)]]] if r.prices else []
                w.writerow(_csv_cells([a.respondent, a.age_group, a.gender, t, LETTERS[o], *levels, *price, int(task.choice == o)]))
            if r.none_option:
                w.writerow(_csv_cells([a.respondent, a.age_group, a.gender, t, "none", *([""] * len(r.attributes)),
                                       *([""] if r.prices else []), int(task.choice is None)]))
    return buf.getvalue()
