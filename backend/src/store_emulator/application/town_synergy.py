"""VLM synergy jobs: what a neighboring venue does to our visitors (demand model) and to their
baskets (VLM shoppers with and without the venue in their trip context). Background jobs under
`.data/<pid>/synergy/<job>/` (status.json, result.json), polled like optimizations."""

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig
from store_emulator.domain.store import Store
from store_emulator.domain.town import DayType, Town, VLMSynergyResult
from store_emulator.domain.types import RESOURCE_ID_PATTERN, ResourceId
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.engine.town.vlm_synergy import vlm_basket_synergy

from .async_executor import executor
from .errors import AppError
from .presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from .providers import build_client, ensure_resolvable
from .scenarios import get_preset
from .simulation import with_engine_model
from .storage.io import DATA_DIR, now_iso, read_json, write_json
from .storage.setups import personas_path, read_setup, read_state
from .town import require_town

logger = logging.getLogger(__name__)

_MIN_STATUS_INTERVAL_SEC = 1.0


class SynergyRequest(BaseModel):
    model: str | None = Field(default=None, description='VLM model reference, e.g. "llamacpp:local" (None = server default)')
    ensemble: EnsembleConfig | None = None
    customers: int = Field(default=40, ge=4, le=400, description="Panel size (visitors simulated with the venue)")
    scenario_id: str | None = None
    setup_id: ResourceId | None = Field(default=None, description="Layout to simulate (default: the active layout)")
    day_type: DayType = "weekday"


class SynergyJobStatus(BaseModel):
    job_id: str
    venue_id: str
    venue_name: str = ""
    setup_id: str
    status: str  # pending | running | completed | failed
    phase: str = ""  # "with venue" / "without venue" while simulating, then "done"
    done: int = 0  # customer simulations finished (both arms)
    total: int = 0
    error: str = ""
    request: SynergyRequest
    scenario: str = ""
    created_at: str = ""
    finished_at: str = ""


class SynergyJobView(BaseModel):
    status: SynergyJobStatus
    result: VLMSynergyResult | None = None


def _dir(pid: str, job_id: str) -> Path:
    return Path(DATA_DIR) / pid / "synergy" / job_id


def _write_status(pid: str, status: SynergyJobStatus) -> None:
    write_json(_dir(pid, status.job_id) / "status.json", status.model_dump(mode="json"))


def get_synergy_job(pid: str, job_id: str) -> SynergyJobView:
    path = _dir(pid, job_id) / "status.json"
    if not path.exists():
        raise AppError(f"synergy job not found: {job_id}", 404)
    status = SynergyJobStatus.model_validate(read_json(path))
    result_path = _dir(pid, job_id) / "result.json"
    result = VLMSynergyResult.model_validate(read_json(result_path)) if result_path.exists() else None
    return SynergyJobView(status=status, result=result)


def list_synergy_jobs(pid: str, venue_id: str | None = None) -> list[SynergyJobStatus]:
    base = Path(DATA_DIR) / pid / "synergy"
    if not base.is_dir():
        return []
    jobs = [SynergyJobStatus.model_validate(read_json(p / "status.json")) for p in base.iterdir()
            if (p / "status.json").exists()]
    return sorted((j for j in jobs if venue_id is None or j.venue_id == venue_id),
                  key=lambda j: j.created_at, reverse=True)


def _setup_id(pid: str, town: Town, requested: str | None) -> str:
    if requested:
        return requested
    active = read_state(pid).get("activeSetupId")
    if isinstance(active, str) and active:
        return active
    focal = town.get_venue(town.focal_venue_id)
    if focal is not None and focal.setup_id:
        return focal.setup_id
    raise AppError("no layout to simulate: pass setup_id", 400)


def start_vlm_synergy(pid: str, venue_id: str, request: SynergyRequest, config: SimulationConfig) -> SynergyJobStatus:
    town = require_town(pid)
    venue = town.get_venue(venue_id)
    if venue is None:
        raise AppError(f"venue not found: {venue_id}", 404)
    if venue.id == town.focal_venue_id:
        raise AppError("pick a venue other than our own store", 400)
    setup_id = _setup_id(pid, town, request.setup_id)
    if not re.fullmatch(RESOURCE_ID_PATTERN, setup_id):
        raise AppError("invalid setup id", 400)
    try:
        setup = read_setup(pid, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404) from None
    if not setup.get("store"):
        raise AppError("this layout has no store yet", 400)
    store = Store.model_validate(setup["store"])
    if not personas_path(pid).exists():
        raise AppError("the project has no personas yet", 400)
    personas = [Persona.model_validate(p) for p in cast(list[dict[str, Any]], read_json(personas_path(pid)))]
    if not personas:
        raise AppError("the project has no personas yet", 400)
    scenario = get_preset(request.scenario_id) if request.scenario_id else None
    if request.scenario_id and scenario is None:
        raise AppError(f"unknown scenario preset: {request.scenario_id}", 400)
    run_config = config.model_copy(update={
        "engine_type": EngineType.VLM_GLANCE, "ensemble": request.ensemble,
        "scenario": None if scenario is None or scenario.id == "baseline" else scenario,
    })
    if request.model:
        run_config = with_engine_model(run_config, request.model)
    try:
        ensure_resolvable(run_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    status = SynergyJobStatus(
        job_id=f"syn_{uuid.uuid4().hex[:6]}", venue_id=venue_id, venue_name=venue.name, setup_id=setup_id,
        status="pending", request=request, scenario=scenario.name if scenario else "", created_at=now_iso(),
    )
    _write_status(pid, status)
    executor.submit(_run_job, pid, status, town, store, personas, run_config)
    return status


def _run_job(
    pid: str, status: SynergyJobStatus, town: Town, store: Store, personas: list[Persona], config: SimulationConfig,
) -> None:
    status.status = "running"
    status.phase = "sampling"
    _write_status(pid, status)
    last = 0.0

    def on_progress(phase: str, done: int, total: int) -> None:
        nonlocal last
        now = time.monotonic()
        status.phase, status.done, status.total = phase, done, total
        if done < total and now - last < _MIN_STATUS_INTERVAL_SEC:
            return
        last = now
        _write_status(pid, status)

    try:
        pathfinder = AStarPathFinder(diagonal=config.diagonal_moves)
        llm = build_client(config.llm_for(EngineType.VLM_GLANCE), config.ensemble)
        request = status.request
        result = asyncio.run(vlm_basket_synergy(
            town, status.venue_id, store, personas,
            config=config, engine=build_engine(config, llm=llm, pathfinder=pathfinder), pathfinder=pathfinder,
            cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, customers=request.customers,
            day_type=request.day_type,
            model_label=request.model or config.llm_for(EngineType.VLM_GLANCE).model, on_progress=on_progress,
        ))
        write_json(_dir(pid, status.job_id) / "result.json", json.loads(result.model_dump_json()))
        status.status, status.phase = "completed", "done"
    except Exception as e:  # surface any failure to the UI instead of a stuck job
        logger.exception(f"[town] synergy job {status.job_id} failed")
        status.status = "failed"
        status.error = f"{type(e).__name__}: {e}"[:500]
    status.finished_at = now_iso()
    _write_status(pid, status)
