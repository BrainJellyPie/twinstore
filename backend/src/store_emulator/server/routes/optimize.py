"""Layout / planogram optimization driven by synthetic shoppers."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from store_emulator.application import optimize as opt_service
from store_emulator.application.errors import AppError
from store_emulator.application.optimize import OptimizationStatus, OptimizationView
from store_emulator.domain.optimize import OptimizeSpec

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["optimize"])


class OptimizeRequest(BaseModel):
    spec: OptimizeSpec = OptimizeSpec()
    scenario_id: str | None = Field(default=None, description="Optimize for a situation (weather/event demand effects)")


class ApplyRequest(BaseModel):
    name: str | None = None


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e


@router.post("/{pid}/setups/{sid}/optimize", summary="Start a layout optimization", response_model=OptimizationStatus)
def start(pid: str, sid: str, req: OptimizeRequest) -> OptimizationStatus:
    """Searches planogram and/or rack placement with the rule-based shoppers (common random numbers),
    then validates the best layout against the original on fresh customers. Runs in the background;
    poll `GET /optimizations/{job_id}`."""
    return _call(lambda: opt_service.start_optimization(pid, sid, req.spec, get_config(), scenario_id=req.scenario_id))


@router.get("/{pid}/optimizations", summary="Optimization jobs", response_model=list[OptimizationStatus])
def list_jobs(pid: str, setup_id: str | None = None) -> list[OptimizationStatus]:
    return opt_service.list_optimizations(pid, setup_id)


@router.get("/{pid}/optimizations/{job_id}", summary="Progress and result", response_model=OptimizationView)
def get_job(pid: str, job_id: str) -> OptimizationView:
    return _call(lambda: opt_service.get_optimization(pid, job_id))


@router.post("/{pid}/optimizations/{job_id}/apply", summary="Save the optimized layout as a new layout")
def apply(pid: str, job_id: str, req: ApplyRequest) -> dict[str, Any]:
    return _call(lambda: opt_service.apply_optimization(pid, job_id, req.name))
