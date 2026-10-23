"""Other operations plans tried on a finished run: the same shoppers, the store run differently, no model call.

A run whose shoppers shared the store kept their visits as decided (timeline_planned.json); a run whose shoppers each
had the store alone saved them as they were (timeline.json). Either replays under any stock, refill and till plan."""

from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field

from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import DATA_DIR, read_json
from store_emulator.application.storage.runs import load_run_store
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.operations import (
    MemoryConfig, OperationsConfig, OperationsCosts, OperationsPlan, OperationsReplay, OperationsReport, RosterRules,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import stable_seed
from store_emulator.engine.simulation.customer_memory import simulate_weeks
from store_emulator.engine.simulation.operations_plan import plan_operations, replay


class ReplayRequest(BaseModel):
    operations: OperationsConfig = OperationsConfig()
    costs: OperationsCosts = OperationsCosts()
    # Shoppers who remember: the run's week repeated, with the shoppers a bad visit put off staying away.
    memory: MemoryConfig | None = None


class PlanRequest(BaseModel):
    costs: OperationsCosts = OperationsCosts()
    # The plan starts from these settings (patience, checkout speed …); None = the run's own, or the defaults.
    operations: OperationsConfig | None = None
    max_tills: int | None = Field(default=None, ge=1, le=50)
    max_crew: int | None = Field(default=None, ge=1, le=100)   # with a crew: the most staff tried in an hour
    # With a crew: answer with a roster of shifts this long instead of hour-by-hour numbers.
    roster: RosterRules | None = None
    # Judge plans by their money over the weeks that follow, with shoppers who remember their visits.
    memory: MemoryConfig | None = None


def _load(pid: str, run_id: str) -> tuple[Store, list[CustomerResult], int, OperationsConfig | None]:
    """The run's store, its shoppers' visits as decided, its seed, and its own operations plan (None: its shoppers
    each had the store alone)."""
    base = Path(DATA_DIR) / pid / "runs" / run_id
    output = base / "output"
    if not (output / "timeline.json").exists():
        raise AppError(f"run {run_id} has no results (not completed?)", 404)
    try:
        own: OperationsConfig | None = None
        if (output / "operations.json").exists():
            saved = read_json(output / "operations.json")
            own = OperationsReport.model_validate(saved).config
            settings = cast(dict[str, object], saved).get("config") if isinstance(saved, dict) else None
            if not isinstance(settings, dict) or "crowd_limit" not in settings:
                own = own.model_copy(update={"crowd_limit": None})   # made before crowding: none happened
            if not (output / "timeline_planned.json").exists():
                raise AppError("this run was made before its shoppers' visits were kept for replaying; run it again "
                               "to try other operations plans", 409)
            planned_path = output / "timeline_planned.json"
        else:
            planned_path = output / "timeline.json"
        visits = read_json(planned_path)
        if not isinstance(visits, list):
            raise ValueError("the saved shopper visits must be a list")
        planned = [CustomerResult.model_validate(c) for c in cast(list[object], visits)]
        config = read_json(base / "input" / "config.json")
        store = load_run_store(base)
    except (ValueError, OSError) as error:   # cut short or damaged on disk
        raise AppError(f"the run's saved files cannot be read: {error}", 422) from error
    saved = cast(dict[str, object], config) if isinstance(config, dict) else {}
    seed, replicate = saved.get("seed", 0), saved.get("replicate", 0)
    return store, planned, stable_seed(seed if isinstance(seed, int) else 0,
                                       replicate if isinstance(replicate, int) else 0), own


def replay_run(pid: str, run_id: str, request: ReplayRequest) -> OperationsReplay:
    store, planned, seed, _ = _load(pid, run_id)
    result, report, _ = replay(store, planned, request.operations, request.costs, seed=seed)
    weeks = (simulate_weeks(store, planned, request.operations, request.memory, request.costs, seed=seed)
             if request.memory is not None else None)
    return OperationsReplay(planned_revenue=sum(c.total_spent for c in planned), outcome=result, report=report,
                            weeks=weeks)


def plan_run(pid: str, run_id: str, request: PlanRequest) -> OperationsPlan:
    store, planned, seed, own = _load(pid, run_id)
    start = request.operations or own or OperationsConfig()
    try:
        return plan_operations(store, planned, start, request.costs, seed=seed, max_tills=request.max_tills,
                               memory=request.memory, max_crew=request.max_crew, roster=request.roster)
    except ValueError as error:
        raise AppError(str(error), 422) from error
