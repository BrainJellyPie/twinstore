"""Observed staff-script field experiments; no model calls."""

from collections.abc import Callable

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from store_emulator.application import field_pilot
from store_emulator.application.errors import AppError
from store_emulator.domain.field_pilot import PilotRequest, PilotRevision, PilotSummary, PilotView

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


@router.get("/{pid}/staff-pilots/{pilot_id}", response_model=PilotView, summary="Field pilot design and observed results")
def get_pilot(pid: str, pilot_id: str) -> PilotView:
    return _call(lambda: field_pilot.get_pilot(pid, pilot_id))


@router.get("/{pid}/staff-pilots/{pilot_id}/observations.csv", summary="Download the assigned observation sheet")
def export_observations(pid: str, pilot_id: str) -> PlainTextResponse:
    text = _call(lambda: field_pilot.export_observations(pid, pilot_id))
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{pilot_id}-observations.csv"'})


@router.put("/{pid}/staff-pilots/{pilot_id}/observations", response_model=PilotView, summary="Replace observations from the complete CSV sheet")
async def import_observations(pid: str, pilot_id: str, file: UploadFile = File(...), revision: int = Form(..., ge=0)) -> PilotView:
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Observation CSV exceeds 2 MB")
    return await run_in_threadpool(_call, lambda: field_pilot.import_observations(pid, pilot_id, data, revision))


@router.post("/{pid}/staff-pilots/{pilot_id}/close", response_model=PilotView, summary="Close collection and lock the field results")
def finalize_pilot(pid: str, pilot_id: str, req: PilotRevision) -> PilotView:
    return _call(lambda: field_pilot.finalize_pilot(pid, pilot_id, req.revision))
