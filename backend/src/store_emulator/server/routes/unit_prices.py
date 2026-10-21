"""Observed cross-retailer price comparisons, without price write-back."""

from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from store_emulator.application import unit_prices
from store_emulator.application.errors import AppError
from store_emulator.domain.unit_prices import PriceScope, UnitPriceReport

router = APIRouter(prefix="/api/projects/{pid}/unit-prices", tags=["observed unit prices"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


async def _input(file: UploadFile, focal_retailer: str, as_of: date, max_age_days: int) -> tuple[bytes, PriceScope]:
    try:
        scope = PriceScope(focal_retailer=focal_retailer, as_of=as_of, max_age_days=max_age_days)
    except ValueError as exc:
        raise HTTPException(422, "Use a valid focal retailer ID and 0–365 maximum age days") from exc
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Offer CSV exceeds 2 MB")
    return data, scope


@router.get("/template.csv")
def template(pid: str) -> PlainTextResponse:
    return PlainTextResponse(_call(lambda: unit_prices.template(pid)), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="offer-template.csv"'})


@router.post("/preview", response_model=UnitPriceReport)
async def preview(pid: str, file: UploadFile = File(...), focal_retailer: str = Form(..., min_length=1, max_length=120), as_of: date = Form(...), max_age_days: int = Form(..., ge=0, le=365)) -> UnitPriceReport:
    data, scope = await _input(file, focal_retailer, as_of, max_age_days)
    return await run_in_threadpool(_call, lambda: unit_prices.preview(pid, data, scope))


@router.post("/export.csv")
async def export(pid: str, file: UploadFile = File(...), focal_retailer: str = Form(..., min_length=1, max_length=120), as_of: date = Form(...), max_age_days: int = Form(..., ge=0, le=365), source_sha256: str = Form(..., pattern=r"^[0-9a-f]{64}$")) -> PlainTextResponse:
    data, scope = await _input(file, focal_retailer, as_of, max_age_days)
    result = await run_in_threadpool(_call, lambda: unit_prices.export(pid, data, scope, source_sha256))
    return PlainTextResponse(result, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="unit-price-audit.csv"'})
