"""Marketing studio: A/B experiments on a layout and survey-style concept tests."""

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from store_emulator.application import marketing as mk
from store_emulator.application import staff_pitch
from store_emulator.application.errors import AppError
from store_emulator.application.marketing import ExperimentView, SurveyView
from store_emulator.domain.marketing import (
    ExperimentRequest,
    JobStatus,
    MarketingInfo,
    ShelfPreview,
    ShelfPreviewRequest,
    ShelfTestRequest,
    SurveyRequest,
)
from store_emulator.domain.staff_pitch import PitchRequest, PitchView
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
