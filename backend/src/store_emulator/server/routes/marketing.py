"""Marketing studio: A/B experiments on a layout and survey-style concept tests."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from store_emulator.application import marketing as mk
from store_emulator.application.errors import AppError
from store_emulator.application.marketing import ExperimentView, SurveyView
from store_emulator.domain.marketing import ExperimentRequest, JobStatus, MarketingInfo, SurveyRequest
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
