"""Marketing studio use cases: the product image library, A/B experiments on a layout, and survey panels.

Files per project (`.data/<pid>/`):
- lab_assets/<aid>.png, <aid>.json        product images (shared with Shelf Lab's "new package" edits)
- marketing/experiments/<eid>/            request.json, status.json, report.json
- marketing/surveys/<sid>/                request.json, status.json, report.json, board.jpg
"""
# (reuses Shelf Lab's private store and persona helpers)

import asyncio
import csv
import io
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Literal, cast

from PIL import Image

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.marketing import (
    ExperimentReport,
    ExperimentRequest,
    JobStatus,
    ScaleSummary,
    SegmentRow,
    SurveyAnswer,
    SurveyReport,
    SurveyRequest,
)
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing import (
    apply_changes,
    likert_summary,
    preference_shares,
    run_experiment,
    survey_panel,
    van_westendorp,
)
from store_emulator.engine.marketing.report import ReportNarrative, report_html, report_markdown, write_narrative
from store_emulator.engine.marketing.survey import LETTERS, SCALES, stimulus_board
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.prompting import display_price
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine

from .async_executor import executor
from .capture import capture_llm_config
from .errors import AppError
from .presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from .providers import build_client
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

Kind = Literal["experiment", "survey"]


def _root(pid: str, kind: Kind) -> Path:
    _check_id(pid, "project id")
    return Path(DATA_DIR) / pid / "marketing" / f"{kind}s"


def _job_dir(pid: str, kind: Kind, jid: str) -> Path:
    _check_id(jid, f"{kind} id")
    return _root(pid, kind) / jid


def _write_status(pid: str, status: JobStatus) -> None:
    write_json(_job_dir(pid, status.kind, status.job_id) / "status.json", status.model_dump(mode="json"))


def _new_job(pid: str, kind: Kind, name: str, request: object) -> JobStatus:
    jid = f"{'exp' if kind == 'experiment' else 'srv'}_{uuid.uuid4().hex[:6]}"
    status = JobStatus(job_id=jid, kind=kind, name=name, status="pending", stage="queued", created_at=now_iso())
    folder = _job_dir(pid, kind, jid)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "request.json", json.loads(cast(Any, request).model_dump_json()))
    _write_status(pid, status)
    return status


def _finish(pid: str, status: JobStatus, report: ExperimentReport | SurveyReport | None, error: str = "") -> None:
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
    for f in sorted(folder.rglob("*"), reverse=True):
        f.unlink() if f.is_file() else f.rmdir()
    folder.rmdir()


def recover_running_jobs() -> int:
    """Mark jobs left in flight by a previous server process as failed."""
    recovered = 0
    for kind in ("experiment", "survey"):
        for path in Path(DATA_DIR).glob(f"*/marketing/{kind}s/*/status.json"):
            try:
                status = JobStatus.model_validate(read_json(path))
            except (OSError, ValueError) as e:
                logger.warning(f"[marketing] could not recover {path}: {e}")
                continue
            if status.status in ("pending", "running"):
                status.status = "failed"
                status.stage = "interrupted"
                status.error = "interrupted by server restart; start a new job to retry"
                status.finished_at = now_iso()
                write_json(path, status.model_dump(mode="json"))
                recovered += 1
    return recovered


_ZERO_DECIMAL = {"KRW", "JPY", "VND", "IDR", "CLP", "ISK", "HUF", "TWD"}


def _minor_per_major(currency: str) -> int:
    return 1 if currency.upper() in _ZERO_DECIMAL else 100


# ── experiments ─────────────────────────────────────────────────────────────────

def start_experiment(pid: str, req: ExperimentRequest, config: SimulationConfig) -> JobStatus:
    control = _load_store(pid, req.setup_id)
    personas = _personas(pid)
    currency = config.currency
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
                engine = build_engine(run_config, llm=llm, pathfinder=pathfinder)
                model = req.model or run_config.llm_for(EngineType.VLM_GLANCE).model
            evaluator = LayoutEvaluator(run_config, panel, sample_cue, BEHAVIOR_PATTERNS, pathfinder,
                                        OptimizeObjective.REVENUE_PER_VISITOR, engine=engine)

            def progress(p: float, stage: str) -> None:
                status.progress, status.stage = round(p, 3), stage
                _write_status(pid, status)

            control_result, results, winner = asyncio.run(run_experiment(
                evaluator, control, built, panel, req.focus_skus, on_progress=progress, seed=req.seed,
            ))
            days = max(1, len({p.day for p in personas}))
            notes: list[str] = []
            if len(panel) < 100:
                notes.append("Fewer than 100 shoppers per variant: differences under ~5 % are hard to tell from noise.")
            if req.engine == "rule" and any(c.kind == "promo" for v in req.variants for c in v.changes):
                notes.append("The rule-based shoppers read promotion signs as a generic impulse boost; vision shoppers see the sign itself.")
            report = ExperimentReport(
                experiment_id=status.job_id, name=name, setup_id=req.setup_id, engine=req.engine, model=model,
                panel_size=len(panel), currency=currency, visitors_per_day=round(len(personas) / days, 1),
                focus_skus=req.focus_skus, control=control_result, variants=results, winner=winner, notes=notes,
                seconds=round(time.perf_counter() - t0, 1),
            )
            _finish(pid, status, report)
        except Exception as e:
            logger.exception(f"[marketing] experiment {status.job_id} failed")
            _finish(pid, status, None, f"{type(e).__name__}: {e}")

    executor.submit(run)
    return status


class ExperimentView(JobStatus):
    report: ExperimentReport | None = None


def get_experiment(pid: str, eid: str) -> ExperimentView:
    status = _status(pid, "experiment", eid)
    path = _job_dir(pid, "experiment", eid) / "report.json"
    report = ExperimentReport.model_validate(read_json(path)) if path.exists() else None
    return ExperimentView(**status.model_dump(), report=report)


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
        llm = build_client(llm_config, None, model_ref=model.strip() or None)
        narrative = asyncio.run(write_narrative(llm, report, layout))
    except ValueError as e:
        raise AppError(str(e), 400) from e
    except Exception as e:  # provider errors reach the user as a message
        logger.warning(f"[marketing] narrative for {eid} failed: {type(e).__name__}: {e}")
        raise AppError(f"the commentary could not be written ({type(e).__name__}): {str(e)[:200]}", 502) from e
    narrative.model = model.strip() or llm_config.model
    write_json(_job_dir(pid, "experiment", eid) / "narrative.json", narrative.model_dump(mode="json"))
    return narrative


def delete_experiment_narrative(pid: str, eid: str) -> None:
    (_job_dir(pid, "experiment", eid) / "narrative.json").unlink(missing_ok=True)


# ── surveys ─────────────────────────────────────────────────────────────────────

def _quota(personas: list[Persona], req: SurveyRequest) -> list[Persona]:
    out = [p for p in personas
           if (not req.age_groups or str(p.age_group) in req.age_groups) and (not req.genders or str(p.gender) in req.genders)]
    if not out:
        raise AppError("no personas match the quota", 400)
    return out


def start_survey(pid: str, req: SurveyRequest, config: SimulationConfig) -> JobStatus:
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
            _finish(pid, status, None, f"{type(e).__name__}: {e}")

    executor.submit(run)
    return status


def summarize_survey(
    sid: str, name: str, model: str, req: SurveyRequest, names: list[str], answers: list[SurveyAnswer], *, seconds: float = 0.0,
) -> SurveyReport:
    ok = [a for a in answers if not a.error]
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


def get_survey(pid: str, sid: str) -> SurveyView:
    status = _status(pid, "survey", sid)
    path = _job_dir(pid, "survey", sid) / "report.json"
    report = SurveyReport.model_validate(read_json(path)) if path.exists() else None
    return SurveyView(**status.model_dump(), report=report)


def survey_board_path(pid: str, sid: str) -> Path:
    path = _job_dir(pid, "survey", sid) / "board.jpg"
    if not path.exists():
        raise AppError(f"survey not found: {sid}", 404)
    return path


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
        w.writerow(row)
    return buf.getvalue()
