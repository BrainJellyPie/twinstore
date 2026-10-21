"""Observed staff-script field experiments; no model calls."""

from collections.abc import Callable

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from store_emulator.application import field_pilot
from store_emulator.application.errors import AppError
from store_emulator.domain.field_pilot import PilotRequest, PilotRevision, PilotSummary, PilotView
from store_emulator.domain.field_planning import PilotPlanningRequest, PilotPlanningResult
from store_emulator.domain.field_observations import ObservationImportAudit, ObservationPreview
from store_emulator.domain.field_collection import PilotCollectionReport

router = APIRouter(prefix="/api/projects", tags=["field pilots"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/{pid}/staff-pitches/{pitch_id}/pilots", response_model=PilotView, summary="Prepare a fixed staff-script field pilot")
def create_pilot(pid: str, pitch_id: str, req: PilotRequest) -> PilotView:
    return _call(lambda: field_pilot.create_pilot(pid, pitch_id, req))


@router.get("/{pid}/staff-pilots", response_model=list[PilotSummary], summary="List observed field pilots")
def list_pilots(pid: str) -> list[PilotSummary]:
    return _call(lambda: field_pilot.list_pilots(pid))


@router.post("/{pid}/staff-pilots/plan", response_model=PilotPlanningResult, summary="Preview conservative sample requirements before a field pilot")
def preview_plan(pid: str, req: PilotPlanningRequest) -> PilotPlanningResult:
    return _call(lambda: field_pilot.preview_plan(pid, req))


@router.get("/{pid}/staff-pilots/{pilot_id}", response_model=PilotView, summary="Field pilot design and observed results")
def get_pilot(pid: str, pilot_id: str) -> PilotView:
    return _call(lambda: field_pilot.get_pilot(pid, pilot_id))


@router.get("/{pid}/staff-pilots/{pilot_id}/observations.csv", summary="Download the assigned observation sheet")
def export_observations(pid: str, pilot_id: str) -> PlainTextResponse:
    text = _call(lambda: field_pilot.export_observations(pid, pilot_id))
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{pilot_id}-observations.csv"'})


@router.get("/{pid}/staff-pilots/{pilot_id}/collection-checks", response_model=PilotCollectionReport, summary="Check collection completeness without reporting purchase outcomes")
def get_collection_checks(pid: str, pilot_id: str) -> PilotCollectionReport:
    return _call(lambda: field_pilot.get_collection_checks(pid, pilot_id))


@router.get("/{pid}/staff-pilots/{pilot_id}/follow-up.csv", summary="Export the latest collection follow-up checklist")
def export_collection_tasks(pid: str, pilot_id: str) -> PlainTextResponse:
    text = _call(lambda: field_pilot.export_collection_tasks(pid, pilot_id))
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{pilot_id}-follow-up.csv"'})


@router.put("/{pid}/staff-pilots/{pilot_id}/observations", response_model=PilotView, summary="Replace observations from the complete CSV sheet")
async def import_observations(pid: str, pilot_id: str, file: UploadFile = File(...), revision: int = Form(..., ge=0),
                              review_token: str = Form(..., pattern=r"^[0-9a-f]{64}$"),
                              reason: str = Form(..., min_length=1, max_length=300)) -> PilotView:
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Observation CSV exceeds 2 MB")
    return await run_in_threadpool(_call, lambda: field_pilot.import_observations(pid, pilot_id, data, revision, review_token, reason))


@router.post("/{pid}/staff-pilots/{pilot_id}/observations/preview", response_model=ObservationPreview, summary="Review a full observation sheet without saving it")
async def review_observations(pid: str, pilot_id: str, file: UploadFile = File(...), revision: int = Form(..., ge=0)) -> ObservationPreview:
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Observation CSV exceeds 2 MB")
    return await run_in_threadpool(_call, lambda: field_pilot.review_observations(pid, pilot_id, data, revision))


@router.get("/{pid}/staff-pilots/{pilot_id}/imports.csv", summary="Export committed observation changes")
def export_import_history(pid: str, pilot_id: str) -> PlainTextResponse:
    text = _call(lambda: field_pilot.export_import_history(pid, pilot_id))
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{pilot_id}-import-history.csv"'})


@router.get("/{pid}/staff-pilots/{pilot_id}/imports/{revision}", response_model=ObservationImportAudit, summary="Read the recorded changes in one import")
def get_import_audit(pid: str, pilot_id: str, revision: int) -> ObservationImportAudit:
    return _call(lambda: field_pilot.get_import_audit(pid, pilot_id, revision))


@router.post("/{pid}/staff-pilots/{pilot_id}/close", response_model=PilotView, summary="Close collection and lock the field results")
def finalize_pilot(pid: str, pilot_id: str, req: PilotRevision) -> PilotView:
    return _call(lambda: field_pilot.finalize_pilot(pid, pilot_id, req.revision))
