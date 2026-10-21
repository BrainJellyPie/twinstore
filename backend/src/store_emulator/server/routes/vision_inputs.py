"""Photo inputs: storefront appeal of a neighborhood venue, and receipts read into a POS export."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from store_emulator.application import vision_inputs as service
from store_emulator.application.errors import AppError
from store_emulator.application.vision_inputs import ReceiptsResult, StorefrontResult

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["photo inputs"])


@router.post("/{pid}/town/venues/{venue_id}/storefront", summary="Rate a storefront photo; sets the venue's pull",
             response_model=StorefrontResult)
async def storefront(
    pid: str, venue_id: str,
    photo: Annotated[UploadFile, File(description="the shop front as seen from the street")],
    model: Annotated[str, Form(description='model reference; "" = app vision model, "none" = image statistics')] = "",
) -> StorefrontResult:
    data = await photo.read()

    def run() -> StorefrontResult:
        try:
            return service.rate_storefront(pid, venue_id, data, model=model, config=get_config())
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e

    return await run_in_threadpool(run)


@router.post("/{pid}/receipts", summary="Read receipt photos into POS lines", response_model=ReceiptsResult)
async def receipts(
    pid: str,
    photos: Annotated[list[UploadFile], File(description="one photo per receipt")],
    setup_id: Annotated[str, Form(pattern=r"^[A-Za-z0-9_-]*$", description="layout whose products the lines are matched to")] = "",
    run_id: Annotated[str, Form(pattern=r"^[A-Za-z0-9_-]*$", description="or: the run whose store the lines are matched to")] = "",
    model: Annotated[str, Form()] = "",
) -> ReceiptsResult:
    datas = [await p.read() for p in photos]

    def run() -> ReceiptsResult:
        try:
            return service.read_receipts(pid, datas, setup_id=setup_id or None, run_id=run_id or None, model=model, config=get_config())
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e

    return await run_in_threadpool(run)
