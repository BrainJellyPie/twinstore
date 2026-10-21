"""Observed display / checkout reconciliation endpoints."""

from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from store_emulator.application import price_checks
from store_emulator.application.errors import AppError
from store_emulator.domain.price_checks import PriceCheckReport, PriceCheckScope

router = APIRouter(prefix="/api/projects/{pid}/price-checks", tags=["observed price checks"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


async def _input(labels: UploadFile, checkouts: UploadFile, store_ref: str, audit_date: str) -> tuple[bytes, bytes, PriceCheckScope]:
    try:
        scope = PriceCheckScope(store_ref=store_ref, audit_date=date.fromisoformat(audit_date))
    except ValueError as exc:
        raise HTTPException(422, "Use a valid store reference and audit date") from exc
    parts: list[bytes] = []
    for name, file in (("Label", labels), ("Checkout", checkouts)):
        data = await file.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise HTTPException(413, f"{name} CSV exceeds 2 MB")
        parts.append(data)
    return parts[0], parts[1], scope


@router.get("/template.csv")
def template(pid: str) -> PlainTextResponse:
    return PlainTextResponse(_call(lambda: price_checks.template(pid)), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="price-check-template.csv"'})


@router.post("/preview", response_model=PriceCheckReport)
async def preview(pid: str, labels: UploadFile = File(...), checkouts: UploadFile = File(...), store_ref: str = Form(..., min_length=1, max_length=120), audit_date: str = Form(..., min_length=10, max_length=10, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")) -> PriceCheckReport:
    label_data, checkout_data, scope = await _input(labels, checkouts, store_ref, audit_date)
    return await run_in_threadpool(_call, lambda: price_checks.preview(pid, label_data, checkout_data, scope))


@router.post("/export.csv")
async def export(pid: str, labels: UploadFile = File(...), checkouts: UploadFile = File(...), store_ref: str = Form(..., min_length=1, max_length=120), audit_date: str = Form(..., min_length=10, max_length=10, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"), source_sha256: str = Form(..., pattern=r"^[0-9a-f]{64}$")) -> PlainTextResponse:
    label_data, checkout_data, scope = await _input(labels, checkouts, store_ref, audit_date)
    result = await run_in_threadpool(_call, lambda: price_checks.export(pid, label_data, checkout_data, scope, source_sha256))
    return PlainTextResponse(result, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="price-check-audit.csv"'})
