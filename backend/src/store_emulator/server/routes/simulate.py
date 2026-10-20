from typing import Annotated, Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from store_emulator.application import simulation as sim_service
from store_emulator.application.async_executor import executor
from store_emulator.application.errors import AppError
from store_emulator.application.providers import ensure_resolvable
from store_emulator.application.simulation import RunOptions
from store_emulator.domain.analysis import ComparisonReport, FidelityReport
from store_emulator.domain.config import EngineType, ExposureModel, RouteOrdering
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig
from store_emulator.domain.scenario import Scenario
from store_emulator.server.schemas import EngineInfo, SimulationStartResponse
from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["simulate"])
engines_router = APIRouter(prefix="/api", tags=["simulate"])


class SimulateRequest(BaseModel):
    """Simulation run request. Executed against the server-stored setup.

    Every option is optional and overrides the server configuration for this run only."""
    setup_id: str = Field(description="Setup ID")
    run_id: str | None = Field(default=None, description="run ID (auto-generated if omitted)")
    engine_type: EngineType | None = Field(default=None, description="`pattern_intent_impulse` (LLM) or `rule_based` (instant, no LLM cost)")
    seed: int | None = Field(default=None, description="Run seed. Equal seeds across layouts give paired (common-random-number) comparisons")
    replicate: int | None = Field(default=None, ge=0, description="Replicate index for repeated runs of the same layout")
    exposure_model: ExposureModel | None = Field(default=None, description="`visibility` (default) or legacy `adjacency`")
    route_ordering: RouteOrdering | None = Field(default=None, description="`planned` (default) or legacy `nearest`")
    max_customers: int | None = Field(default=None, ge=1, description="Deterministic persona subsample for cheap pilots")
    preview: bool = Field(default=False, description="Preview runs don't lock the setup and are allowed on draft or finalized setups")
    model: str | None = Field(default=None, description='Model reference for the engine, e.g. "openai:gpt-6-luna", "qwen:qwen3.7-plus"')
    ensemble: EnsembleConfig | None = Field(default=None, description="Several models as one consumer population (mixture or vote)")
    scenario_id: str | None = Field(default=None, description='Scenario preset id (GET /api/scenarios), e.g. "heatwave_weekend"')
    scenario: Scenario | None = Field(default=None, description="Custom scenario (overrides scenario_id)")


@engines_router.get("/engines", summary="Available simulation engines", response_model=list[EngineInfo])
async def list_engines() -> list[EngineInfo]:
    """Engines selectable per run, with the server's current defaults."""
    config = get_config()
    llm = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE)
    vlm = config.llm_for(EngineType.VLM_GLANCE)
    return [
        EngineInfo(
            engine_type=EngineType.PATTERN_INTENT_IMPULSE.value, label="LLM shoppers",
            description="3-stage LLM pipeline (pattern → intent → impulse). Realistic, costs LLM calls.",
            uses_llm=True, model=llm.model, default=config.engine_type == EngineType.PATTERN_INTENT_IMPULSE,
        ),
        EngineInfo(
            engine_type=EngineType.RULE_BASED.value, label="Rule-based preview",
            description="Calibratable heuristic shoppers. Seconds per run, no LLM cost — for quick layout iteration.",
            uses_llm=False, model="", default=config.engine_type == EngineType.RULE_BASED,
        ),
        EngineInfo(
            engine_type=EngineType.VLM_GLANCE.value, label="Vision shoppers",
            description="Rule-based planning; impulse picks made by a vision-language model looking at rendered "
                        "shelves. Runs on a local CPU model — use a small customer sample.",
            uses_llm=True, model=vlm.model, default=config.engine_type == EngineType.VLM_GLANCE,
        ),
    ]


@router.get("/{pid}/runs", summary="Simulation run history")
async def list_runs(
    pid: str,
    setup_id: str | None = Query(default=None, description="filter by setup"),
) -> list[dict[str, Any]]:
    """List simulation runs for the project.

    **Filter:** `?setup_id=xxx` to scope to a single setup.
    **Sort:** `created_at` descending.
    **Response fields:** `run_id`, `status`, `setup_id`, `created_at`, `summary` (when completed)."""
    return sim_service.list_runs(pid, setup_id)


@router.post("/{pid}/runs", summary="Start simulation", response_model=SimulationStartResponse)
async def start_simulation(pid: str, req: SimulateRequest) -> SimulationStartResponse:
    """Run a simulation asynchronously. Returns immediately; work runs in the background.

    **Engine:** runs on the `pattern_intent_impulse` engine.

    **Preconditions (setup readiness must pass):**
    - `setup.store` exists
    - At least one product is placed in slots (registered via `PUT /setups/{sid}/slots`)
    - At least one project persona exists
    - No layout/persona generation is in progress

    **Setup lock:** the same setup cannot run concurrently. A running setup is in `running` state.
    **On completion:** the setup transitions to `locked` and `runId` is recorded.
    **On failure:** the setup reverts to `draft`.

    **Errors:** 400 (no layout / no personas), 404 (setup not found), 409 (locked / running / readiness not met / duplicate run_id)"""
    options = RunOptions(
        engine_type=req.engine_type, seed=req.seed, replicate=req.replicate,
        exposure_model=req.exposure_model, route_ordering=req.route_ordering,
        max_customers=req.max_customers, preview=req.preview, model=req.model, ensemble=req.ensemble,
        scenario_id=req.scenario_id, scenario=req.scenario,
    )
    config = get_config()
    try:
        ensure_resolvable(sim_service.apply_options(config, options))
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        run_id, store, personas, address, customer_profile = sim_service.prepare_simulation(
            pid, req.setup_id, req.run_id, preview=req.preview,
        )
    except AppError as e:
        raise HTTPException(e.status_code, str(e))

    executor.submit(
        sim_service.run_simulation_background,
        pid, run_id, req.setup_id, store, personas,
        config, address, customer_profile, options,
    )

    return SimulationStartResponse(project_id=pid, run_id=run_id, setup_id=req.setup_id)


@router.get("/{pid}/runs/{run_id}/status", summary="Get simulation status")
async def get_status(pid: str, run_id: str) -> dict[str, Any]:
    """Poll simulation progress.

    **Common response:** `{ status, error, created_at, setup_id, total_customers, completed_customers, failed_customers }`.
    **status values:** `"pending"` → `"running"` → `"completed"` | `"failed"`.
    When `failed`, `error` carries the exception message.
    """
    try:
        return sim_service.get_run_status(pid, run_id)
    except FileNotFoundError:
        raise HTTPException(404, "run result not found")


@router.get("/{pid}/runs/{run_id}/summary", summary="Simulation summary + personas")
async def get_summary(pid: str, run_id: str) -> dict[str, Any]:
    """Aggregated simulation result and the personas used.

    **Response:** `{ summary: SimulationSummary, personas: { id: Persona } }`.
    **Note:** `personas` is a `persona_id → Persona` map, not an array.
    **summary fields:** total_customers, total_revenue, top_products, by_purpose/identity/age/gender.
    `by_*` distributions depend on persona attributes — some engines may leave them empty or weakly meaningful."""
    try:
        return {
            "summary": sim_service.get_run_output(pid, run_id, "summary.json"),
            "personas": sim_service.get_run_output(pid, run_id, "personas.json"),
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/{pid}/runs/{run_id}/heatmap", summary="Heatmap data")
async def get_heatmap(pid: str, run_id: str) -> dict[str, Any]:
    """Customer-flow heatmaps.

    **Response:**
    - `pathcalc_heatmap`: float[][] — per-cell movement frequency
    - `persona_heatmap`: int[][] — per-cell timeline event count
    - `dwell_heatmap`: float[][] — seconds spent per cell, summed over customers (empty for older runs)
    - size = grid_size [height][width]"""
    try:
        result: dict[str, Any] = {
            "pathcalc_heatmap": sim_service.get_run_output(pid, run_id, "pathcalc_heatmap.json"),
            "persona_heatmap": sim_service.get_run_output(pid, run_id, "persona_heatmap.json"),
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    try:
        result["dwell_heatmap"] = sim_service.get_run_output(pid, run_id, "dwell_heatmap.json")
    except FileNotFoundError:
        result["dwell_heatmap"] = []
    return result


@router.get("/{pid}/runs/{run_id}/diagnostics", summary="Run diagnostics, manifest and cost")
async def get_diagnostics(pid: str, run_id: str) -> dict[str, Any]:
    """Data-quality and reproducibility information for a run.

    **Response:** `{ diagnostics, manifest, token_usage, engine_meta? }` — failed customers with reasons,
    dropped hallucinated / over-budget buys, buy-invariant violations, the seed/engine/fingerprints
    needed to reproduce the run, and LLM token + request counts (incl. cache hits).
    Older runs return empty objects for fields they did not record."""
    out: dict[str, Any] = {}
    for key, fname in (("diagnostics", "diagnostics.json"), ("manifest", "manifest.json"), ("token_usage", "token_usage.json")):
        try:
            out[key] = sim_service.get_run_output(pid, run_id, fname)
        except FileNotFoundError:
            out[key] = {}
    if not any(out.values()):
        raise HTTPException(404, "run result not found")
    summary = sim_service.engine_meta_summary(pid, run_id)
    if summary is not None:
        out["engine_meta"] = summary
    return out


@router.get("/{pid}/compare", summary="Paired A/B comparison of two runs", response_model=ComparisonReport)
async def compare(
    pid: str,
    a: str = Query(description="baseline run id"),
    b: str = Query(description="variant run id"),
    n_bootstrap: int = Query(default=2000, ge=200, le=20000),
) -> ComparisonReport:
    """Per-customer paired comparison (B − A) with bootstrap confidence intervals.

    Customers are matched by persona id. Metrics: spend, units, bought (conversion), impulse_spend,
    visit_sec, path_tiles. Each metric reports the difference, its 95% CI, the share of bootstrap
    draws favoring B, and how many customers a 5% effect would need. Run both layouts with the same
    seed so customers share random draws — that is what makes the paired test sharp."""
    try:
        return sim_service.compare_project_runs(pid, a, b, n_bootstrap=n_bootstrap)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/{pid}/runs/{run_id}/fidelity", summary="Score a run against real POS data", response_model=FidelityReport)
async def fidelity(
    pid: str,
    run_id: str,
    file: Annotated[UploadFile, File(description="POS export (.csv or .xlsx)")],
) -> FidelityReport:
    """Compare simulated sales with an uploaded POS export of the same store.

    Required columns (any common alias): transaction id and SKU. Optional: quantity, unit price
    or line total (same minor currency unit as shelf prices), timestamp or hour.
    Reports SKU/rack Spearman, JS similarity, NDCG, basket-size and basket-value distribution
    distances, variance ratio and hourly profile similarity. The report is saved with the run."""
    data = await file.read()
    try:
        return sim_service.run_fidelity(pid, run_id, data, file.filename or "pos.csv")
    except AppError as e:
        raise HTTPException(e.status_code, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/{pid}/runs/{run_id}/export.csv", summary="Per-customer results as CSV")
async def export_csv(pid: str, run_id: str) -> Response:
    """One row per simulated customer (persona attributes, spend, units, conversion, impulse spend,
    visit time, path length, products) — for Excel / BI tools."""
    try:
        body = sim_service.export_customers_csv(pid, run_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return Response(
        content="\ufeff" + body,  # BOM so Excel opens UTF-8 correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{pid}_{run_id}_customers.csv"'},
    )


@router.get("/{pid}/runs/{run_id}/timeline", summary="Per-customer timeline")
async def get_timeline(pid: str, run_id: str) -> Any:
    """Behavior timeline for every customer.

    **Response:** `CustomerResult[]` — chronologically ordered events per customer. The `engine_type` field identifies which engine produced the result.
    Each event: elapsed_sec, x, y, action (enter/move/browse/buy/pay/exit), duration, product_sku, etc.
    **If the file has not been generated yet, returns an empty array** (not 404)."""
    try:
        return sim_service.get_run_output(pid, run_id, "timeline.json")
    except FileNotFoundError:
        return []


@router.get("/{pid}/runs/{run_id}/store", summary="Store at simulation time")
async def get_run_store(pid: str, run_id: str) -> dict[str, Any]:
    """Store layout (Store object) at the time of the simulation run."""
    try:
        return sim_service.get_run_input(pid, run_id, "store.json")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/{pid}/runs/{run_id}/personas", summary="Simulation personas",
            response_model=dict[str, Persona])
async def get_run_personas(pid: str, run_id: str) -> dict[str, Persona]:
    """Personas used in the simulation. **`persona_id → Persona` map** (not an array).

    Returns `output/personas.json` as-is. Shape differs from `input/personas.json` (which is an array).
    """
    try:
        raw = sim_service.get_run_output(pid, run_id, "personas.json")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {pid_: Persona.model_validate(p) for pid_, p in raw.items()}


