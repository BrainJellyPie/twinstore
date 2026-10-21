"""Read-only project-scoped inventory worksheets; no saved stock mutation."""

from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import _check_id  # pyright: ignore[reportPrivateUsage]
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.inventory_review import InventoryPeriod, InventoryReport
from store_emulator.engine.analysis.inventory_review import inventory_csv, inventory_template, review_inventory


def _project(pid: str) -> None:
    _check_id(pid, "project id")
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)


def template(pid: str) -> str:
    _project(pid)
    return inventory_template()


def preview(pid: str, data: bytes, period: InventoryPeriod) -> InventoryReport:
    _project(pid)
    try:
        return review_inventory(data, period)
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc


def export(pid: str, data: bytes, period: InventoryPeriod) -> str:
    return inventory_csv(preview(pid, data, period))
