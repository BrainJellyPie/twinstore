from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from store_emulator.application.storage import images as image_storage


router = APIRouter(prefix="/api/projects/{pid}", tags=["images"])


@router.post("/sku-images", summary="Upload single SKU image")
@router.post("/sku-images/{sku:path}", include_in_schema=False)
async def upload_sku_image(
    pid: str,
    sku: str,
    file: UploadFile = File(..., description="image file (PNG/JPG/WebP, ≤2MB)"),
) -> dict[str, str]:
    data = await file.read(image_storage.MAX_IMAGE_BYTES + 1)
    try:
        # PIL parse + file write are sync I/O; offload to threadpool so the
        # event loop is not blocked.
        await run_in_threadpool(
            image_storage.save_image, pid, sku, data, file.filename or sku,
        )
    except image_storage.ImageTooLargeError as e:
        raise HTTPException(413, str(e))
    except image_storage.UnsupportedImageFormatError as e:
        raise HTTPException(422, str(e))
    except image_storage.ImageStorageError as e:
        raise HTTPException(500, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e))
    url = image_storage.image_url_for(pid, sku)
    if url is None:
        raise HTTPException(404, "The project or image no longer exists.")
    return {"sku": sku, "url": url}


@router.get("/images", summary="Download SKU image")
@router.get("/images/{sku:path}", include_in_schema=False)
async def get_sku_image(pid: str, sku: str) -> FileResponse:
    try:
        resolved = image_storage.resolve_image(pid, sku)
    except ValueError:
        raise HTTPException(400, "invalid project id")
    if resolved is None:
        raise HTTPException(404, f"image not found: {sku}")
    path, mime = resolved
    return FileResponse(path, media_type=mime)
