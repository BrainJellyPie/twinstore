"""Layout optimization jobs: run in the background, report progress, apply the result as a new layout."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.optimize import OptimizeResult, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.optimize.search import optimize
from store_emulator.engine.routing.pathfinder import AStarPathFinder

from .async_executor import executor
from .errors import AppError
from .presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from .scenarios import get_preset
from .setups import set_active_setup, setup_summary
from .storage.io import DATA_DIR, now_iso, read_json, write_json
from .storage.setups import new_setup_data, personas_path, read_setup, setup_path

logger = logging.getLogger(__name__)

_MIN_STATUS_INTERVAL_SEC = 0.5


class OptimizationStatus(BaseModel):
    job_id: str
    setup_id: str
    status: str                       # pending | running | completed | failed
    error: str = ""
    evaluations: int = 0
    budget: int = 0
    baseline_score: float | None = None
    best_score: float | None = None
    scenario: str = ""
    spec: OptimizeSpec
    created_at: str = ""
    finished_at: str = ""
    applied_setup_id: str | None = None


class OptimizationView(BaseModel):
    status: OptimizationStatus
    result: OptimizeResult | None = None


def _dir(pid: str, job_id: str) -> Path:
    return Path(DATA_DIR) / pid / "optimizations" / job_id


def _write_status(pid: str, status: OptimizationStatus) -> None:
    write_json(_dir(pid, status.job_id) / "status.json", status.model_dump(mode="json"))


def _read_status(pid: str, job_id: str) -> OptimizationStatus:
    path = _dir(pid, job_id) / "status.json"
    if not path.exists():
        raise AppError(f"optimization not found: {job_id}", 404)
    return OptimizationStatus.model_validate(read_json(path))


def get_optimization(pid: str, job_id: str) -> OptimizationView:
    status = _read_status(pid, job_id)
    result_path = _dir(pid, job_id) / "result.json"
    result = OptimizeResult.model_validate(read_json(result_path)) if result_path.exists() else None
    return OptimizationView(status=status, result=result)


def list_optimizations(pid: str, setup_id: str | None = None) -> list[OptimizationStatus]:
    base = Path(DATA_DIR) / pid / "optimizations"
    if not base.is_dir():
        return []
    out = [OptimizationStatus.model_validate(read_json(p / "status.json")) for p in base.iterdir() if (p / "status.json").exists()]
    out = [s for s in out if setup_id is None or s.setup_id == setup_id]
    return sorted(out, key=lambda s: s.created_at, reverse=True)


def _load_store_and_personas(pid: str, setup_id: str) -> tuple[Store, list[Persona]]:
    try:
        setup = read_setup(pid, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404) from None
    store_data = setup.get("store")
    if not store_data:
        raise AppError("this layout has no store yet", 400)
    store = Store.model_validate(store_data)
    path = personas_path(pid)
    if not path.exists():
        raise AppError("the project has no personas yet", 400)
    personas = [Persona.model_validate(p) for p in cast(list[dict[str, Any]], read_json(path))]
    if not personas:
        raise AppError("the project has no personas yet", 400)
    return store, personas


def start_optimization(
    pid: str, setup_id: str, spec: OptimizeSpec, config: SimulationConfig, *, scenario_id: str | None = None,
) -> OptimizationStatus:
    store, personas = _load_store_and_personas(pid, setup_id)
    scenario = get_preset(scenario_id) if scenario_id else None
    if scenario_id and scenario is None:
        raise AppError(f"unknown scenario preset: {scenario_id}", 400)
    job_id = f"opt_{uuid.uuid4().hex[:6]}"
    status = OptimizationStatus(
        job_id=job_id, setup_id=setup_id, status="pending", budget=spec.budget, spec=spec,
        scenario=scenario.name if scenario else "", created_at=now_iso(),
    )
    _write_status(pid, status)
    run_config = config.model_copy(update={
        "engine_type": EngineType.RULE_BASED,
        "scenario": None if scenario is None or scenario.id == "baseline" else scenario,
    })
    executor.submit(_run_job, pid, status, store, personas, run_config)
    return status


def _run_job(pid: str, status: OptimizationStatus, store: Store, personas: list[Persona], config: SimulationConfig) -> None:
    spec = status.spec
    status.status = "running"
    _write_status(pid, status)
    last = 0.0

    def on_progress(done: int, budget: int, best: float) -> None:
        nonlocal last
        now = time.monotonic()
        status.evaluations, status.budget, status.best_score = done, budget, best
        if done < budget and now - last < _MIN_STATUS_INTERVAL_SEC:
            return
        last = now
        _write_status(pid, status)

    try:
        evaluator = LayoutEvaluator(
            config, select_personas(personas, spec.eval_customers, seed=spec.seed), sample_cue, BEHAVIOR_PATTERNS,
            AStarPathFinder(), spec.objective,
        )
        validation = select_personas(personas, spec.validation_size, seed=spec.seed + 1)
        result = asyncio.run(optimize(store, spec, evaluator, validation_personas=validation, on_progress=on_progress))
        write_json(_dir(pid, status.job_id) / "result.json", json.loads(result.model_dump_json()))
        status.status = "completed"
        status.baseline_score, status.best_score = result.baseline_score, result.best_score
        status.evaluations = result.evaluations
    except Exception as e:  # noqa: BLE001 — surface any failure to the UI instead of a stuck job
        logger.exception(f"[optimize] job {status.job_id} failed")
        status.status = "failed"
        status.error = f"{type(e).__name__}: {e}"[:500]
    status.finished_at = now_iso()
    _write_status(pid, status)


def apply_optimization(pid: str, job_id: str, name: str | None = None) -> dict[str, Any]:
    """Save the optimized layout as a new draft layout (the original stays untouched)."""
    view = get_optimization(pid, job_id)
    if view.result is None:
        raise AppError("optimization has no result yet", 409)
    source = read_setup(pid, view.status.setup_id)
    label = f"{view.result.validation_relative_improvement:+.1%}" if view.result.validation_relative_improvement is not None else ""
    final_name = name or f"{source.get('name') or 'layout'} (optimized{' ' + label if label else ''})"
    memo = "; ".join(view.result.applied_moves[:12])
    new_setup = new_setup_data(final_name, view.status.setup_id, view.result.best_store.model_dump(mode="json"), memo[:1000])
    write_json(setup_path(pid, new_setup["id"]), new_setup)
    set_active_setup(pid, new_setup["id"])
    status = view.status.model_copy(update={"applied_setup_id": new_setup["id"]})
    _write_status(pid, status)
    return setup_summary(pid, new_setup)
