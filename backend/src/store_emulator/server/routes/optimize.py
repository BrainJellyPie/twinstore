"""Layout / planogram optimization driven by synthetic shoppers."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from store_emulator.application import optimize as opt_service
from store_emulator.application import optimize_goal
from store_emulator.application import setups as setup_service
from store_emulator.application.errors import AppError
from store_emulator.application.optimize import OptimizationStatus, OptimizationView
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.optimize import JudgeSpec, OptimizeJudge, OptimizeSpec
from store_emulator.domain.providers import EnsembleConfig
from store_emulator.engine.optimize.goal import OptimizeGoal

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["optimize"])


class OptimizeRequest(BaseModel):
    spec: OptimizeSpec = OptimizeSpec()
    scenario_id: str | None = Field(default=None, description="Optimize for a situation (weather/event demand effects)")
    judge: OptimizeJudge = Field(
        default="rule",
        description='"rule": the rule surrogate picks the layout. "vlm": the VLM shoppers judge the surrogate\'s'
                    " top_k candidates and the baseline on one paired panel and pick the winner",
    )
    model: str | None = Field(default=None, description='VLM judge model reference, e.g. "llamacpp:local"')
    ensemble: EnsembleConfig | None = Field(default=None, description="VLM judge: several models as one population")
    vlm_customers: int = Field(default=60, ge=4, le=400, description="VLM judge panel size (same people on every layout)")
    top_k: int = Field(default=4, ge=1, le=8, description="Distinct surrogate candidates judged by the VLM shoppers")
    calibrate: bool = Field(default=True, description="Fit the surrogate's impulse knobs to a VLM pilot first")
    operations: OperationsConfig | None = Field(
        default=None, description="Judge candidates in a shared store run this way; omitted: the layout's saved settings")
    shared_store: bool | None = Field(default=None, description="false: each shopper has the store alone")

    def judge_spec(self) -> JudgeSpec:
        return JudgeSpec(judge=self.judge, model=self.model, ensemble=self.ensemble,
                         vlm_customers=self.vlm_customers, top_k=self.top_k, calibrate=self.calibrate)


class ApplyRequest(BaseModel):
    name: str | None = None


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e


@router.post("/{pid}/setups/{sid}/optimize/goal", summary="Read an optimization goal into its settings", response_model=OptimizeGoal)
async def read_goal(pid: str, sid: str, req: optimize_goal.GoalRequest) -> OptimizeGoal:
    """The text model chooses the objective, what may change, the move limit, the locked shelves (of this layout, by
    name) and the smallest gain worth keeping from the goal. Nothing starts; the settings fill the dialog."""
    return await run_in_threadpool(_call, lambda: optimize_goal.read(pid, sid, req, get_config()))


@router.post("/{pid}/setups/{sid}/optimize", summary="Start a layout optimization", response_model=OptimizationStatus)
def start(pid: str, sid: str, req: OptimizeRequest) -> OptimizationStatus:
    """Searches planogram and/or rack placement with the rule-based shoppers (common random numbers),
    then validates the best layout against the original on fresh customers. With `judge: "vlm"` the
    surrogate is first calibrated to a VLM pilot, and the VLM shoppers pick the winner among the
    surrogate's `top_k` candidates and the baseline (paired deltas, rank agreement in `result.judge`).
    Runs in the background; poll `GET /optimizations/{job_id}` (`status.phase`)."""
    return _call(lambda: opt_service.start_optimization(
        pid, sid, req.spec, get_config(), scenario_id=req.scenario_id, judge=req.judge_spec(),
        operations=setup_service.run_operations(pid, sid, req.operations, req.shared_store),
    ))


@router.get("/{pid}/optimizations", summary="Optimization jobs", response_model=list[OptimizationStatus])
def list_jobs(pid: str, setup_id: str | None = None) -> list[OptimizationStatus]:
    return opt_service.list_optimizations(pid, setup_id)


@router.get("/{pid}/optimizations/{job_id}", summary="Progress and result", response_model=OptimizationView)
def get_job(pid: str, job_id: str) -> OptimizationView:
    return _call(lambda: opt_service.get_optimization(pid, job_id))


@router.post("/{pid}/optimizations/{job_id}/cancel", summary="Stop a running optimization",
             response_model=OptimizationStatus)
def cancel(pid: str, job_id: str) -> OptimizationStatus:
    """The job stops at its next step (between search phases and between VLM layout runs) with
    status `canceled`."""
    return _call(lambda: opt_service.cancel_optimization(pid, job_id))


@router.post("/{pid}/optimizations/{job_id}/apply", summary="Save the optimized layout as a new layout")
def apply(pid: str, job_id: str, req: ApplyRequest) -> dict[str, Any]:
    return _call(lambda: opt_service.apply_optimization(pid, job_id, req.name))
