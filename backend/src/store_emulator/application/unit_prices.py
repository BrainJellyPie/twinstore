"""Read-only project-scoped offer reviews."""

from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import _check_id  # pyright: ignore[reportPrivateUsage]
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.unit_prices import PriceScope, UnitPriceReport
from store_emulator.engine.analysis.unit_prices import review_unit_prices, unit_price_csv, unit_price_template


def _project(pid: str) -> None:
    _check_id(pid, "project id")
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)


def template(pid: str) -> str:
    _project(pid)
    return unit_price_template()


def preview(pid: str, data: bytes, scope: PriceScope) -> UnitPriceReport:
    _project(pid)
    try:
        return review_unit_prices(data, scope)
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc


def export(pid: str, data: bytes, scope: PriceScope, expected_sha256: str) -> str:
    report = preview(pid, data, scope)
    if report.source_sha256 != expected_sha256:
        raise AppError("Offer source changed; review it again before export", 409)
    return unit_price_csv(report)
