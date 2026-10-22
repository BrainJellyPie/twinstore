from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from store_emulator.application import starter_fill
from store_emulator.application.errors import AppError
from store_emulator.domain.product_edits import ProductLayoutId
from store_emulator.domain.starter_fill import StarterAutoRequest, StarterCatalog, StarterFillRequest, StarterFillSave, StarterPreview, StarterSaved
from store_emulator.server.deps import get_config

router = APIRouter(prefix="/api/projects/{pid}/setups/{sid}/starter-fill", tags=["setups"])


@router.post("/auto-select", response_model=StarterFillRequest)
async def auto_select(pid: ProductLayoutId, sid: ProductLayoutId, req: StarterAutoRequest) -> StarterFillRequest:
    try:
        return await run_in_threadpool(starter_fill.auto_select, pid, sid, req, get_config())
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.get("", response_model=StarterCatalog)
async def catalog(pid: ProductLayoutId, sid: ProductLayoutId) -> StarterCatalog:
    try:
        return await run_in_threadpool(starter_fill.catalog, pid, sid)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/preview", response_model=StarterPreview)
async def preview(pid: ProductLayoutId, sid: ProductLayoutId, req: StarterFillRequest) -> StarterPreview:
    try:
        return await run_in_threadpool(starter_fill.preview, pid, sid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/save", response_model=StarterSaved)
async def save(pid: ProductLayoutId, sid: ProductLayoutId, req: StarterFillSave) -> StarterSaved:
    try:
        return await run_in_threadpool(starter_fill.save, pid, sid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
