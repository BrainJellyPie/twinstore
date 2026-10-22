from collections.abc import Callable
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from store_emulator.application import library_photos
from store_emulator.application.errors import AppError
from store_emulator.application.storage.images import ImageStorageError
from store_emulator.domain.library_photos import PhotoDigest, PhotoOptions, PhotoPreview, PhotoRequest, PhotoSave, PhotoSaved
from store_emulator.domain.product_edits import ProductLayoutId

router = APIRouter(prefix="/api/projects/{pid}", tags=["setups"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    except (OSError, ValueError, ImageStorageError) as exc:
        raise HTTPException(409, "Photo data could not be read or saved. Reload and review the library") from exc


@router.get("/setups/{sid}/library-photos", response_model=PhotoOptions)
async def options(pid: ProductLayoutId, sid: ProductLayoutId) -> PhotoOptions:
    return await run_in_threadpool(_call, lambda: library_photos.options(pid, sid))


@router.post("/setups/{sid}/library-photos/preview", response_model=PhotoPreview)
async def preview(pid: ProductLayoutId, sid: ProductLayoutId, req: PhotoRequest) -> PhotoPreview:
    return await run_in_threadpool(_call, lambda: library_photos.preview(pid, sid, req))


@router.post("/setups/{sid}/library-photos/save", response_model=PhotoSaved)
async def save(pid: ProductLayoutId, sid: ProductLayoutId, req: PhotoSave) -> PhotoSaved:
    return await run_in_threadpool(_call, lambda: library_photos.save(pid, sid, req))


@router.get("/product-photo-files/{digest}")
def photo(pid: ProductLayoutId, digest: PhotoDigest) -> FileResponse:
    return FileResponse(_call(lambda: library_photos.photo_file(pid, digest)), media_type="image/png")
