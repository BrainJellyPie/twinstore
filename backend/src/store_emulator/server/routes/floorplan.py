"""Floor plan import: a plan image or PDF page becomes a new draft layout."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from store_emulator.application import floorplan as service
from store_emulator.application.errors import AppError
from store_emulator.application.floorplan import FloorPlanImport
from store_emulator.domain.floorplan import PlanReader

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["floor plan"])


@router.post("/{pid}/floorplan", summary="Import a floor plan as a new layout", response_model=FloorPlanImport)
async def import_plan(
    pid: str,
    plan: Annotated[UploadFile, File(description="hand sketch, CAD export or scanned plan (PNG/JPEG/WebP; PDF with pypdfium2)")],
    reader: Annotated[PlanReader, Form(description="auto: vision model, falling back to geometry; classic: geometry only")] = "auto",
    model: Annotated[str, Form(description='model reference; "" = the app vision model, "none" = geometry only')] = "",
    name: Annotated[str, Form()] = "",
) -> FloorPlanImport:
    data = await plan.read()

    def run() -> FloorPlanImport:
        try:
            return service.import_floor_plan(pid, data, plan.filename or "plan", reader=reader, model=model,
                                             name=name or None, config=get_config())
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e

    return await run_in_threadpool(run)
