"""Shelf capture: photograph a real shelf, get a planogram, test it as a new layout."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from store_emulator.application import capture as capture_service, capture_batch
from store_emulator.domain.capture_batch import CaptureBatchPreview, CaptureBatchRequest, CaptureBatchSave, CaptureBatchSaved
from store_emulator.application.capture import ApplyResult, CaptureUpdate, CaptureView
from store_emulator.application.errors import AppError
from store_emulator.domain.capture import (
    CaptureDetector,
    CaptureOptions,
    CaptureRackType,
    CaptureStatus,
)
from store_emulator.domain.types import ResourceId

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["capture"])


class ApplyCaptureRequest(BaseModel):
    setup_id: ResourceId = Field(description="layout to start from; it is not modified")
    rack_id: str | None = Field(default=None, description="replace this rack's face with the captured shelf")
    face: str | None = Field(default=None, description="N | S | E | W; default: the face holding most products")
    new_rack: bool = Field(default=False, description="add the shelf as new rack(s) on free floor instead")
    name: str | None = None


class ApplyCapturesRequest(BaseModel):
    capture_ids: list[ResourceId] = Field(min_length=1, description="several photos → several new racks")
    setup_id: ResourceId
    name: str | None = None


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/{pid}/captures", summary="Upload a shelf photo", response_model=CaptureStatus)
async def create(
    pid: str,
    image: Annotated[UploadFile, File(description="shelf photo (JPEG/PNG/WebP, ≤25 MB)")],
    detector: Annotated[CaptureDetector, Form()] = "auto",
    model: Annotated[str, Form(description='model reference, "" = app vision model, "none" = no recognition')] = "",
    currency: Annotated[str, Form()] = "",
    rack_type: Annotated[CaptureRackType, Form()] = "shelf",
    label: Annotated[str, Form()] = "",
) -> CaptureStatus:
    """Detects shelf levels, product facings and gaps, reads each product (name, brand, category, price)
    with a vision-language model, and builds a planogram. Runs in the background; poll `GET .../captures/{cid}`."""
    data = await image.read()
    options = CaptureOptions(detector=detector, model=model, currency=currency, rack_type=rack_type, label=label)
    return await run_in_threadpool(
        _call, lambda: capture_service.create_capture(pid, data, image.filename or "photo", options, get_config()),
    )


@router.get("/{pid}/captures", summary="Shelf captures", response_model=list[CaptureStatus])
def list_all(pid: str) -> list[CaptureStatus]:
    return _call(lambda: capture_service.list_captures(pid))


@router.post("/{pid}/captures/apply", summary="Add several captured shelves as new racks", response_model=ApplyResult)
def apply_many(pid: str, req: ApplyCapturesRequest) -> ApplyResult:
    return _call(lambda: capture_service.apply_captures(
        pid, req.capture_ids, req.setup_id, new_rack=True, name=req.name, default_currency=get_config().currency,
    ))


@router.post("/{pid}/captures/batch-preview", response_model=CaptureBatchPreview)
def preview_batch(pid: str, req: CaptureBatchRequest) -> CaptureBatchPreview:
    return _call(lambda: capture_batch.preview(pid, req, default_currency=get_config().currency))


@router.post("/{pid}/captures/batch-save", response_model=CaptureBatchSaved)
def save_batch(pid: str, req: CaptureBatchSave) -> CaptureBatchSaved:
    return _call(lambda: capture_batch.save(pid, req, default_currency=get_config().currency))


@router.get("/{pid}/captures/{cid}", summary="Capture status and planogram", response_model=CaptureView)
def get_one(pid: str, cid: str) -> CaptureView:
    return _call(lambda: capture_service.get_capture(pid, cid))


@router.get("/{pid}/captures/{cid}/image", summary="The photo, or the annotated overlay with overlay=1")
def image(pid: str, cid: str, overlay: int = 0) -> FileResponse:
    path = _call(lambda: capture_service.capture_image_path(pid, cid, overlay=bool(overlay)))
    return FileResponse(path, media_type="image/png" if overlay else "image/jpeg")


@router.put("/{pid}/captures/{cid}", summary="Save the corrected product list", response_model=CaptureView)
def update(pid: str, cid: str, req: CaptureUpdate) -> CaptureView:
    """Full replacement of the product list: edit names/prices/facings, leave items out to delete them,
    list absorbed ids in `merged_from` to merge, omit `id` to add a product."""
    return _call(lambda: capture_service.update_capture(pid, cid, req))


@router.post("/{pid}/captures/{cid}/apply", summary="Save the captured shelf into a new layout", response_model=ApplyResult)
def apply(pid: str, cid: str, req: ApplyCaptureRequest) -> ApplyResult:
    return _call(lambda: capture_service.apply_captures(
        pid, [cid], req.setup_id, rack_id=req.rack_id, face=req.face, new_rack=req.new_rack, name=req.name,
        default_currency=get_config().currency,
    ))


@router.delete("/{pid}/captures/{cid}", summary="Delete a capture", status_code=204)
def delete(pid: str, cid: str) -> None:
    _call(lambda: capture_service.delete_capture(pid, cid))
