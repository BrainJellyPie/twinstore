from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from store_emulator.application import rack_copy
from store_emulator.application.errors import AppError
from store_emulator.domain.product_edits import ProductLayoutId
from store_emulator.domain.rack_copy import RackCopyOptions, RackCopyPreview, RackCopyRequest, RackCopySave, RackCopySaved

router = APIRouter(prefix="/api/projects/{pid}/setups/{sid}/rack-copy", tags=["setups"])


@router.get("", response_model=RackCopyOptions)
async def options(pid: ProductLayoutId, sid: ProductLayoutId, source_rack_id: str | None = Query(default=None, min_length=1, max_length=200)) -> RackCopyOptions:
    try:
        return await run_in_threadpool(rack_copy.options, pid, sid, source_rack_id)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/preview", response_model=RackCopyPreview)
async def preview(pid: ProductLayoutId, sid: ProductLayoutId, req: RackCopyRequest) -> RackCopyPreview:
    try:
        return await run_in_threadpool(rack_copy.preview, pid, sid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/save", response_model=RackCopySaved)
async def save(pid: ProductLayoutId, sid: ProductLayoutId, req: RackCopySave) -> RackCopySaved:
    try:
        return await run_in_threadpool(rack_copy.save, pid, sid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
