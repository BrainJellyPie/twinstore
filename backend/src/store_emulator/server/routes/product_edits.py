from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from store_emulator.application import product_edits
from store_emulator.application.errors import AppError
from store_emulator.domain.product_edits import (
    ProductCatalog, ProductEditsPreview, ProductEditsRequest, ProductEditsSave, ProductEditsSaved, ProductLayoutId,
)

router = APIRouter(prefix="/api/projects/{pid}/setups/{sid}/product-edits", tags=["setups"])


@router.get("", response_model=ProductCatalog)
async def catalog(pid: ProductLayoutId, sid: ProductLayoutId) -> ProductCatalog:
    try:
        return await run_in_threadpool(product_edits.catalog, pid, sid)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/preview", response_model=ProductEditsPreview)
async def preview(pid: ProductLayoutId, sid: ProductLayoutId, req: ProductEditsRequest) -> ProductEditsPreview:
    try:
        return await run_in_threadpool(product_edits.preview, pid, sid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/save", response_model=ProductEditsSaved)
async def save(pid: ProductLayoutId, sid: ProductLayoutId, req: ProductEditsSave) -> ProductEditsSaved:
    try:
        return await run_in_threadpool(product_edits.save, pid, sid, req)
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
