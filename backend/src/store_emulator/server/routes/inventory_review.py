"""Descriptive inventory performance from an explicitly scoped operator CSV."""

from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from store_emulator.application import inventory_review
from store_emulator.application.errors import AppError
from store_emulator.domain.inventory_review import InventoryPeriod, InventoryReport

router = APIRouter(prefix="/api/projects/{pid}/inventory-review", tags=["inventory review"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


async def _input(file: UploadFile, start_date: date, end_date: date, currency: str) -> tuple[bytes, InventoryPeriod]:
    try:
        period = InventoryPeriod(start_date=start_date, end_date=end_date, currency=currency)
    except ValueError as exc:
        raise HTTPException(422, "Use a 1–3660 day period with end on or after start, and a three-letter uppercase currency code") from exc
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Inventory CSV exceeds 2 MB")
    return data, period


@router.get("/template.csv", summary="Download the inventory period input columns")
def template(pid: str) -> PlainTextResponse:
    text = _call(lambda: inventory_review.template(pid))
    return PlainTextResponse(text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="inventory-template.csv"'})


@router.post("/preview", response_model=InventoryReport, summary="Reconcile supplied inventory and calculate period margin ratios")
async def preview(pid: str, file: UploadFile = File(...), start_date: date = Form(...), end_date: date = Form(...),
                  currency: str = Form(..., min_length=3, max_length=3)) -> InventoryReport:
    data, period = await _input(file, start_date, end_date, currency)
    return await run_in_threadpool(_call, lambda: inventory_review.preview(pid, data, period))


@router.post("/export.csv", summary="Export the inventory audit and the exact supplied period")
async def export(pid: str, file: UploadFile = File(...), start_date: date = Form(...), end_date: date = Form(...),
                 currency: str = Form(..., min_length=3, max_length=3)) -> PlainTextResponse:
    data, period = await _input(file, start_date, end_date, currency)
    text = await run_in_threadpool(_call, lambda: inventory_review.export(pid, data, period))
    return PlainTextResponse(text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="inventory-review.csv"'})
