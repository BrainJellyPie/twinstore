from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from store_emulator.application.catalog_images import packshot

router = APIRouter(prefix="/api/catalog-images", tags=["images"])


@router.get("/{sheet}/{index}.webp", summary="Bundled starter product image")
def catalog_image(sheet: str, index: int) -> Response:
    try:
        data = packshot(sheet, index)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(data, media_type="image/webp", headers={"Cache-Control": "public, max-age=31536000, immutable"})
