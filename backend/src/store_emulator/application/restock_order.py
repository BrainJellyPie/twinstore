"""Build an unsaved purchasing worksheet from a completed shelf audit."""

from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import get_job
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.restock_order import RestockOrderPlan, RestockOrderRequest
from store_emulator.engine.shelf_lab.restock_order import plan_restock_order, restock_order_csv


def preview_order(pid: str, cid: str, jid: str, request: RestockOrderRequest) -> RestockOrderPlan:
    job = get_job(pid, cid, jid)
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)
    if job.status.status != "completed" or job.audit is None:
        raise AppError("A completed compliance audit is required for restocking quantities", 409)
    if job.audit.job_id != jid or job.audit.capture_id != cid:
        raise AppError("The saved audit does not match this job and capture", 409)
    try:
        return plan_restock_order(job.audit, request)
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc


def export_order(pid: str, cid: str, jid: str, request: RestockOrderRequest) -> str:
    return restock_order_csv(preview_order(pid, cid, jid, request))
