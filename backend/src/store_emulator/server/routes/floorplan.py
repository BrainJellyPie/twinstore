"""Floor plan import: a plan image or PDF page becomes a new draft layout."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from store_emulator.application import floorplan as service
from store_emulator.application.errors import AppError
from store_emulator.application.floorplan import FloorPlanImport, FloorPlanPreview
from store_emulator.domain.floorplan import PlanReader

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["floor plan"])


@router.post("/{pid}/floorplan/preview", summary="Preview a selected plan page without creating a layout", response_model=FloorPlanPreview)
async def preview_plan(
    pid: str,
    plan: Annotated[UploadFile, File()],
    page_number: Annotated[int, Form(ge=1)] = 1,
    rotation: Annotated[int, Form(ge=0, le=270, multiple_of=90)] = 0,
) -> FloorPlanPreview:
    data = await plan.read(service.MAX_PLAN_BYTES + 1)
    try:
        return await run_in_threadpool(service.preview_floor_plan, pid, data, plan.filename or "plan",
                                       page_number=page_number, rotation=rotation)
    except AppError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/{pid}/floorplan", summary="Import a floor plan as a new layout", response_model=FloorPlanImport)
async def import_plan(
    pid: str,
    plan: Annotated[UploadFile, File(description="hand sketch, CAD export or scanned plan (PNG/JPEG/WebP/PDF)")],
    reader: Annotated[PlanReader, Form(description="auto: vision model, falling back to geometry; classic: geometry only")] = "auto",
    model: Annotated[str, Form(description='model reference; "" = the app vision model, "none" = geometry only')] = "",
    name: Annotated[str, Form()] = "",
    page_number: Annotated[int, Form(ge=1)] = 1,
    rotation: Annotated[int, Form(ge=0, le=270, multiple_of=90)] = 0,
) -> FloorPlanImport:
    data = await plan.read(service.MAX_PLAN_BYTES + 1)

    def run() -> FloorPlanImport:
        try:
            return service.import_floor_plan(pid, data, plan.filename or "plan", reader=reader, model=model,
                                             name=name or None, config=get_config(), page_number=page_number, rotation=rotation)
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e

    return await run_in_threadpool(run)
