"""Layout optimization jobs: run in the background, report progress, apply the result as a new layout."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.optimize import JudgeSpec, OptimizeResult, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.optimize.judge import (
    OptimizationCanceled,
    judge_layout_search,
)
from store_emulator.engine.optimize.search import optimize
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine

from .async_executor import executor
from .errors import AppError, job_failure
from .currencies import simulation_currency
from .presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from .providers import build_client, ensure_resolvable
from .scenarios import get_preset, scenario_shoppers, scenario_store
from .setups import set_active_setup, setup_summary
from .simulation import with_vision_default
from .storage.io import DATA_DIR, now_iso, read_json, write_json
from .storage.setups import new_setup_data, personas_path, read_setup, setup_path

logger = logging.getLogger(__name__)

_MIN_STATUS_INTERVAL_SEC = 0.5


_cancel_requests: set[tuple[str, str]] = set()


class OptimizationStatus(BaseModel):
    job_id: str
    setup_id: str
    status: str                       # pending | running | completed | failed | canceled
    # judge "vlm": calibrating → searching → judging k/K; judge "rule": searching
    phase: str = ""
    judge: JudgeSpec = JudgeSpec()
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
    judge: JudgeSpec | None = None,
) -> OptimizationStatus:
    judge = judge or JudgeSpec()
    store, personas = _load_store_and_personas(pid, setup_id)
    scenario = get_preset(scenario_id) if scenario_id else None
    if scenario_id and scenario is None:
        raise AppError(f"unknown scenario preset: {scenario_id}", 400)
    run_config = config.model_copy(update={
        "engine_type": EngineType.RULE_BASED,
        "currency": simulation_currency(pid, store, config.currency),
        "scenario": None if scenario is None or scenario.id == "baseline" else scenario,
    })
    vlm_config: SimulationConfig | None = None
    if judge.judge == "vlm":
        vlm_config = vlm_judge_config(run_config, judge)
        try:
            ensure_resolvable(vlm_config)
        except ValueError as e:
            raise AppError(str(e), 400) from e
    job_id = f"opt_{uuid.uuid4().hex[:6]}"
    status = OptimizationStatus(
        job_id=job_id, setup_id=setup_id, status="pending", budget=spec.budget, spec=spec, judge=judge,
        scenario=scenario.name if scenario else "", created_at=now_iso(),
    )
    _write_status(pid, status)
    executor.submit(_run_job, pid, status, store, personas, run_config, vlm_config)
    return status


def vlm_judge_config(config: SimulationConfig, judge: JudgeSpec) -> SimulationConfig:
    """The VLM shoppers' run config: same seed, scenario and settings as the search, vision engine."""
    vlm = config.model_copy(update={"engine_type": EngineType.VLM_GLANCE, "ensemble": judge.ensemble})
    return with_vision_default(vlm, judge.model)


def cancel_optimization(pid: str, job_id: str) -> OptimizationStatus:
    """Ask a running job to stop at its next step (between surrogate phases and VLM layout runs)."""
    status = _read_status(pid, job_id)
    if status.status in ("pending", "running"):
        _cancel_requests.add((pid, job_id))
    return status


def _run_job(
    pid: str, status: OptimizationStatus, store: Store, personas: list[Persona], config: SimulationConfig,
    vlm_config: SimulationConfig | None = None,
) -> None:
    spec, judge = status.spec, status.judge
    status.status = "running"
    status.phase = "searching" if vlm_config is None else ""
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

    def on_phase(name: str) -> None:
        status.phase = name
        _write_status(pid, status)

    try:
        if (pid, status.job_id) in _cancel_requests:
            raise OptimizationCanceled("optimization canceled before starting")
        # The situation's days, traffic and budgets pick the panels; its promotions and stock-outs go on every
        # layout the shoppers walk (the layouts themselves, and the one saved, keep the regular prices).
        personas = scenario_shoppers(config, store, personas)
        if not personas:
            raise ValueError("No shoppers come on this situation's days and opening hours, so there is nothing to "
                             "optimize for. Pick another situation, or change the layout's opening hours.")
        situation: Callable[[Store], Store] | None = None
        if config.scenario is not None:
            situation = partial(scenario_store, config)
        search_personas = select_personas(personas, spec.eval_customers, seed=spec.seed)
        if vlm_config is None:
            evaluator = LayoutEvaluator(
                config, search_personas, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(diagonal=config.diagonal_moves),
                spec.objective, prepare_store=situation,
            )
            validation = select_personas(personas, spec.validation_size, seed=spec.seed + 1)
            result = asyncio.run(optimize(store, spec, evaluator, validation_personas=validation, on_progress=on_progress,
                                          should_stop=lambda: (pid, status.job_id) in _cancel_requests))
        else:
            pathfinder = AStarPathFinder(diagonal=vlm_config.diagonal_moves)
            llm = build_client(vlm_config.llm_for(EngineType.VLM_GLANCE), vlm_config.ensemble)
            result = asyncio.run(judge_layout_search(
                store, spec, judge,
                surrogate_config=config, vlm_config=vlm_config,
                vlm_engine=build_engine(vlm_config, llm=llm, pathfinder=pathfinder),
                # The judge panel is a subset of the search panel, so calibration and search share people.
                search_personas=search_personas,
                vlm_personas=select_personas(search_personas, judge.vlm_customers, seed=spec.seed + 2),
                cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, pathfinder=pathfinder,
                model_label=judge.model or vlm_config.llm_for(EngineType.VLM_GLANCE).model,
                on_phase=on_phase, on_progress=on_progress,
                should_stop=lambda: (pid, status.job_id) in _cancel_requests, prepare_store=situation,
            ))
        if (pid, status.job_id) in _cancel_requests:
            raise OptimizationCanceled("optimization canceled before publishing its result")
        write_json(_dir(pid, status.job_id) / "result.json", json.loads(result.model_dump_json()))
        status.status = "completed"
        status.phase = "done"
        status.baseline_score, status.best_score = result.baseline_score, result.best_score
        status.evaluations = result.evaluations
    except OptimizationCanceled:
        logger.info(f"[optimize] job {status.job_id} canceled")
        status.status = "canceled"
    except Exception as e:
        logger.exception(f"[optimize] job {status.job_id} failed")
        status.status = "failed"
        status.error = job_failure(e, "The optimization failed")
    _cancel_requests.discard((pid, status.job_id))
    status.finished_at = now_iso()
    _write_status(pid, status)


def apply_optimization(pid: str, job_id: str, name: str | None = None) -> dict[str, Any]:
    """Save the optimized layout as a new draft layout (the original stays untouched)."""
    view = get_optimization(pid, job_id)
    if view.result is None:
        raise AppError("optimization has no result yet", 409)
    try:
        source = read_setup(pid, view.status.setup_id)
    except FileNotFoundError:
        raise AppError("The source layout no longer exists; this optimization cannot be saved.", 404) from None
    label = f"{view.result.validation_relative_improvement:+.1%}" if view.result.validation_relative_improvement is not None else ""
    final_name = name or f"{source.get('name') or 'layout'} (optimized{' ' + label if label else ''})"
    memo = "; ".join(view.result.applied_moves[:12])
    new_setup = new_setup_data(final_name, view.status.setup_id, view.result.best_store.model_dump(mode="json"), memo[:1000])
    if source.get("building") is not None:  # the optimized layout stays on the same building floor
        new_setup["building"] = BuildingFloorInfo.model_validate(source["building"]).model_dump(mode="json")
    write_json(setup_path(pid, new_setup["id"]), new_setup)
    set_active_setup(pid, new_setup["id"])
    status = view.status.model_copy(update={"applied_setup_id": new_setup["id"]})
    _write_status(pid, status)
    return setup_summary(pid, new_setup)
