"""Read-only price-check use cases scoped to an existing project."""

from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import _check_id  # pyright: ignore[reportPrivateUsage]
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.price_checks import PriceCheckReport, PriceCheckScope
from store_emulator.engine.analysis.price_checks import price_check_csv, price_check_template, review_price_checks


def _project(pid: str) -> None:
    _check_id(pid, "project id")
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)


def template(pid: str) -> str:
    _project(pid)
    return price_check_template()


def preview(pid: str, labels: bytes, checkouts: bytes, scope: PriceCheckScope) -> PriceCheckReport:
    _project(pid)
    try:
        return review_price_checks(labels, checkouts, scope)
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc


def export(pid: str, labels: bytes, checkouts: bytes, scope: PriceCheckScope, expected_sha256: str) -> str:
    report = preview(pid, labels, checkouts, scope)
    if report.source_sha256 != expected_sha256:
        raise AppError("Price-check sources or scope changed; review again before export", 409)
    return price_check_csv(report)
