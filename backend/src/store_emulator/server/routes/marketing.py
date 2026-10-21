"""Marketing studio: A/B experiments on a layout and survey-style concept tests."""

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from store_emulator.application import marketing as mk
from store_emulator.application import staff_pitch
from store_emulator.application import study_design, study_reading
from store_emulator.application import factorial
from store_emulator.application.errors import AppError
from store_emulator.application.marketing import ExperimentView, SurveyView
from store_emulator.domain.marketing import (
    ConjointRequest,
    ExperimentRequest,
    JobStatus,
    MarketingInfo,
    ShelfPreview,
    ShelfPreviewRequest,
    ShelfTestRequest,
    SurveyRequest,
)
from store_emulator.domain.staff_pitch import PitchRequest, PitchView
from store_emulator.domain.factorial import FactorialReport, FactorialRequest, FactorialSource
from store_emulator.engine.marketing.conjoint_design import ConjointDesign
from store_emulator.engine.marketing.experiment_design import ExperimentDesign
from store_emulator.engine.marketing.reading import StudyReading
from store_emulator.engine.marketing.script_writer import ScriptDraft
from store_emulator.engine.marketing.report import ReportNarrative

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["marketing"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/{pid}/marketing", summary="Marketing studio settings", response_model=MarketingInfo)
def marketing_info(pid: str) -> MarketingInfo:
    return MarketingInfo(currency=get_config().currency)


@router.post("/{pid}/experiments/design", summary="Draft an A/B test from a question", response_model=ExperimentDesign)
async def design_experiment(pid: str, req: study_design.ExperimentDesignRequest) -> ExperimentDesign:
    """The text model drafts variants (price, discount, sign, move, package, category price) on the layout's own
    products and shelves. Nothing runs; the draft fills the builder."""
    return await run_in_threadpool(_call, lambda: study_design.design_ab(pid, req, get_config()))


@router.post("/{pid}/experiments", summary="Start an A/B test", response_model=JobStatus)
async def start_experiment(pid: str, req: ExperimentRequest) -> JobStatus:
    """Variants of a layout (price, discount, promotion sign, placement, packaging, category pricing) run on the same
    shopper panel as the control; poll `GET .../experiments/{eid}` for the report."""
    return await run_in_threadpool(_call, lambda: mk.start_experiment(pid, req, get_config()))


@router.get("/{pid}/experiments", summary="A/B tests of a project", response_model=list[JobStatus])
def list_experiments(pid: str) -> list[JobStatus]:
    return _call(lambda: mk.list_jobs(pid, "experiment"))


@router.get("/{pid}/experiments/{eid}", summary="A/B test status and report", response_model=ExperimentView)
def get_experiment(pid: str, eid: str) -> ExperimentView:
    return _call(lambda: mk.get_experiment(pid, eid))


@router.get("/{pid}/experiments/{eid}/report.html", summary="A/B test report (print-ready HTML)", response_class=HTMLResponse)
def experiment_report_html(pid: str, eid: str, download: bool = False) -> HTMLResponse:
    """Summary with a rule-based recommendation, the test design, results with paired 95 % intervals and charts,
    tracked products, method and caveats; the model commentary when one was written. Print it to save a PDF."""
    html = _call(lambda: mk.experiment_report_html(pid, eid))
    headers = {"Content-Disposition": f'attachment; filename="{eid}-report.html"'} if download else None
    return HTMLResponse(html, headers=headers)


@router.get("/{pid}/experiments/{eid}/factorial/source", response_model=FactorialSource,
            summary="Check retained paired outcomes for exploratory price by sign analysis")
def factorial_source(pid: str, eid: str) -> FactorialSource:
    return _call(lambda: factorial.source(pid, eid))


@router.post("/{pid}/experiments/{eid}/factorial/preview", response_model=FactorialReport,
             summary="Calculate paired price by sign contrasts without new model calls")
async def factorial_preview(pid: str, eid: str, req: FactorialRequest) -> FactorialReport:
    return await run_in_threadpool(_call, lambda: factorial.preview(pid, eid, req))


@router.post("/{pid}/experiments/{eid}/factorial/export.csv", summary="Export source-bound factorial audit and selected shopper cells")
async def factorial_export(pid: str, eid: str, req: FactorialRequest) -> PlainTextResponse:
    text = await run_in_threadpool(_call, lambda: factorial.export(pid, eid, req))
    return PlainTextResponse(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{eid}-factorial.csv"'})


@router.get("/{pid}/experiments/{eid}/report.md", summary="A/B test report (Markdown)")
def experiment_report_markdown(pid: str, eid: str) -> PlainTextResponse:
    text = _call(lambda: mk.experiment_report_markdown(pid, eid))
    return PlainTextResponse(text, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{eid}-report.md"'})


class NarrativeRequest(BaseModel):
    model: str = Field(default="", description='model reference; "" = the app text model')


@router.post("/{pid}/experiments/{eid}/narrative", summary="Write the report commentary with a model", response_model=ReportNarrative)
async def experiment_narrative(pid: str, eid: str, req: NarrativeRequest) -> ReportNarrative:
    return await run_in_threadpool(_call, lambda: mk.write_experiment_narrative(pid, eid, req.model, get_config()))


@router.delete("/{pid}/experiments/{eid}/narrative", summary="Remove the report commentary", status_code=204)
def delete_experiment_narrative(pid: str, eid: str) -> None:
    _call(lambda: mk.delete_experiment_narrative(pid, eid))


_STUDY_PATHS: dict[str, study_reading.StudyKind] = {
    "surveys": "survey", "shelf-tests": "shelf", "conjoints": "conjoint", "staff-pitches": "pitch",
}
StudyPath = Literal["surveys", "shelf-tests", "conjoints", "staff-pitches"]


@router.post("/{pid}/{study}/{jid}/reading", summary="Write a model's reading of a study", response_model=StudyReading)
async def write_study_reading(pid: str, study: StudyPath, jid: str, req: NarrativeRequest) -> StudyReading:
    """Concept, shelf, conjoint and staff-script studies: the respondents' open answers coded into themes (per arm
    for paired studies) and a commentary on the report's numbers. Replaces an earlier reading; the print-ready report
    shows it, labelled as model-written."""
    kind = _STUDY_PATHS[study]
    return await run_in_threadpool(_call, lambda: study_reading.write_reading(pid, kind, jid, req.model, get_config()))


@router.get("/{pid}/{study}/{jid}/reading", summary="A study's reading (null until one is written)",
            response_model=StudyReading | None)
def get_study_reading(pid: str, study: StudyPath, jid: str) -> StudyReading | None:
    return _call(lambda: study_reading.get_reading(pid, _STUDY_PATHS[study], jid))


@router.delete("/{pid}/{study}/{jid}/reading", summary="Remove a study's reading", status_code=204)
def delete_study_reading(pid: str, study: StudyPath, jid: str) -> None:
    _call(lambda: study_reading.delete_reading(pid, _STUDY_PATHS[study], jid))


@router.post("/{pid}/surveys", summary="Start a concept test", response_model=JobStatus)
async def start_survey(pid: str, req: SurveyRequest) -> JobStatus:
    """Synthetic respondents (the project's personas, optionally by quota) look at product images and answer purchase
    intent, appeal, value, uniqueness, Van Westendorp price and preference questions."""
    return await run_in_threadpool(_call, lambda: mk.start_survey(pid, req, get_config()))


@router.get("/{pid}/surveys", summary="Concept tests of a project", response_model=list[JobStatus])
def list_surveys(pid: str) -> list[JobStatus]:
    return _call(lambda: mk.list_jobs(pid, "survey"))


@router.get("/{pid}/surveys/{sid}", summary="Concept test status and report", response_model=SurveyView)
def get_survey(pid: str, sid: str) -> SurveyView:
    return _call(lambda: mk.get_survey(pid, sid))


@router.get("/{pid}/surveys/{sid}/board.jpg", summary="The stimulus board respondents saw")
def survey_board(pid: str, sid: str) -> FileResponse:
    return FileResponse(_call(lambda: mk.survey_board_path(pid, sid)), media_type="image/jpeg")


@router.get("/{pid}/surveys/{sid}/report.html", summary="Concept test report (print-ready HTML)", response_class=HTMLResponse)
def survey_report(pid: str, sid: str) -> HTMLResponse:
    return HTMLResponse(_call(lambda: mk.survey_report(pid, sid)))


@router.get("/{pid}/surveys/{sid}/export.csv", summary="Respondent-level answers as CSV")
def survey_csv(pid: str, sid: str) -> PlainTextResponse:
    text = _call(lambda: mk.survey_csv(pid, sid))
    return PlainTextResponse(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{sid}.csv"'})


@router.delete("/{pid}/experiments/{eid}", summary="Delete an A/B test", status_code=204)
def delete_experiment(pid: str, eid: str) -> None:
    _call(lambda: mk.delete_job(pid, "experiment", eid))


@router.delete("/{pid}/surveys/{sid}", summary="Delete a concept test", status_code=204)
def delete_survey(pid: str, sid: str) -> None:
    _call(lambda: mk.delete_job(pid, "survey", sid))


@router.post("/{pid}/staff-pitches/draft-script", summary="Draft an alternative staff script", response_model=ScriptDraft)
async def draft_pitch_script(pid: str, req: staff_pitch.ScriptDraftRequest) -> ScriptDraft:
    """The text model writes another script for the same product and offer, using only the verified facts given.
    Nothing runs; the draft fills script B."""
    return await run_in_threadpool(_call, lambda: staff_pitch.draft_pitch_script(pid, req, get_config()))


@router.post("/{pid}/staff-pitches", summary="Start a paired staff script screening test", response_model=JobStatus)
async def start_pitch(pid: str, req: PitchRequest) -> JobStatus:
    return await run_in_threadpool(_call, lambda: staff_pitch.start_pitch(pid, req, get_config()))


@router.get("/{pid}/staff-pitches", summary="Staff script tests", response_model=list[JobStatus])
def list_pitches(pid: str) -> list[JobStatus]:
    return _call(lambda: mk.list_jobs(pid, "pitch"))


@router.get("/{pid}/staff-pitches/{pitch_id}", summary="Staff script test status and report", response_model=PitchView)
def get_pitch(pid: str, pitch_id: str) -> PitchView:
    return _call(lambda: staff_pitch.get_pitch(pid, pitch_id))


@router.get("/{pid}/staff-pitches/{pitch_id}/export.csv", summary="Paired script ratings and exact stimuli")
def pitch_csv(pid: str, pitch_id: str) -> PlainTextResponse:
    text = _call(lambda: staff_pitch.pitch_csv(pid, pitch_id))
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{pitch_id}.csv"'})


@router.delete("/{pid}/staff-pitches/{pitch_id}", summary="Delete a completed staff script test", status_code=204)
def delete_pitch(pid: str, pitch_id: str) -> None:
    _call(lambda: mk.delete_job(pid, "pitch", pitch_id))


@router.post("/{pid}/shelf-tests", summary="Start a virtual shelf test", response_model=JobStatus)
async def start_shelf_test(pid: str, req: ShelfTestRequest) -> JobStatus:
    """The same respondents see the control shelf face and the changed one (new pack, price, sign, placement), pick one
    product and name what caught their eye first; the target's pick share and stand-out are compared pair by pair."""
    return await run_in_threadpool(_call, lambda: mk.start_shelf_test(pid, req, get_config()))


@router.post("/{pid}/shelf-tests/preview", summary="Render the control and test shelf", response_model=ShelfPreview)
async def preview_shelf(pid: str, req: ShelfPreviewRequest) -> ShelfPreview:
    return await run_in_threadpool(_call, lambda: mk.preview_shelf(pid, req, get_config()))


@router.get("/{pid}/shelf-tests", summary="Shelf tests of a project", response_model=list[JobStatus])
def list_shelf_tests(pid: str) -> list[JobStatus]:
    return _call(lambda: mk.list_jobs(pid, "shelf"))


@router.get("/{pid}/shelf-tests/{tid}", summary="Shelf test status and report", response_model=mk.ShelfTestView)
def get_shelf_test(pid: str, tid: str) -> mk.ShelfTestView:
    return _call(lambda: mk.get_shelf_test(pid, tid))


@router.get("/{pid}/shelf-tests/{tid}/report.html", summary="Shelf test report (print-ready HTML)", response_class=HTMLResponse)
def shelf_test_report(pid: str, tid: str) -> HTMLResponse:
    return HTMLResponse(_call(lambda: mk.shelf_test_report(pid, tid)))


@router.get("/{pid}/shelf-tests/{tid}/{arm}.png", summary="The shelf one arm saw", response_class=Response)
async def shelf_test_image(pid: str, tid: str, arm: Literal["control", "test"]) -> Response:
    png = await run_in_threadpool(_call, lambda: mk.shelf_test_image(pid, tid, arm))
    return Response(png, media_type="image/png")


@router.delete("/{pid}/shelf-tests/{tid}", summary="Delete a shelf test", status_code=204)
def delete_shelf_test(pid: str, tid: str) -> None:
    _call(lambda: mk.delete_job(pid, "shelf", tid))


@router.post("/{pid}/conjoints/design", summary="Draft a conjoint study from a question", response_model=ConjointDesign)
async def design_conjoint(pid: str, req: study_design.ConjointDesignRequest) -> ConjointDesign:
    """The text model drafts the product, attributes, levels and price levels (in the request's currency, bracketing
    comparable products of the layout) for the question. Nothing runs; the draft fills the builder."""
    return await run_in_threadpool(_call, lambda: study_design.design(pid, req, get_config()))


@router.post("/{pid}/conjoints", summary="Start a choice-based conjoint study", response_model=JobStatus)
async def start_conjoint(pid: str, req: ConjointRequest) -> JobStatus:
    """Respondents choose between versions of a product (attribute levels and prices) in several choice tasks; a logit
    model gives part-worths, attribute importance and willingness to pay, with intervals over respondents."""
    return await run_in_threadpool(_call, lambda: mk.start_conjoint(pid, req, get_config()))


@router.get("/{pid}/conjoints", summary="Conjoint studies of a project", response_model=list[JobStatus])
def list_conjoints(pid: str) -> list[JobStatus]:
    return _call(lambda: mk.list_jobs(pid, "conjoint"))


@router.get("/{pid}/conjoints/{cid}", summary="Conjoint study status and report", response_model=mk.ConjointView)
def get_conjoint(pid: str, cid: str) -> mk.ConjointView:
    return _call(lambda: mk.get_conjoint(pid, cid))


@router.get("/{pid}/conjoints/{cid}/report.html", summary="Conjoint report (print-ready HTML)", response_class=HTMLResponse)
def conjoint_report(pid: str, cid: str) -> HTMLResponse:
    return HTMLResponse(_call(lambda: mk.conjoint_report(pid, cid)))


@router.get("/{pid}/conjoints/{cid}/export.csv", summary="Every option shown and whether it was chosen, as CSV")
def conjoint_csv(pid: str, cid: str) -> PlainTextResponse:
    text = _call(lambda: mk.conjoint_csv(pid, cid))
    return PlainTextResponse(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{cid}.csv"'})


@router.delete("/{pid}/conjoints/{cid}", summary="Delete a conjoint study", status_code=204)
def delete_conjoint(pid: str, cid: str) -> None:
    _call(lambda: mk.delete_job(pid, "conjoint", cid))
