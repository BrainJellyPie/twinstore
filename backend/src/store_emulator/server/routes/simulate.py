from typing import Annotated, Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from store_emulator.application import run_analyst
from store_emulator.application import simulation as sim_service
from store_emulator.application import town as town_service
from store_emulator.application.async_executor import executor
from store_emulator.application.errors import AppError
from store_emulator.application.movement import MAX_TRACK_BYTES
from store_emulator.application.operations_lab import PlanRequest, ReplayRequest, plan_run, replay_run
from store_emulator.application.providers import (
    ensure_resolvable,
    load_settings,
    local_model_answers,
    missing_key,
    resolve_model,
    text_model_fallback,
)
from store_emulator.application.run_estimate import RunEstimate, estimate_run
from store_emulator.application.simulation import RunOptions, with_vision_default
from store_emulator.domain.analysis import ComparisonReport, FidelityReport
from store_emulator.domain.config import EngineType, ExposureModel, LLMConfig, PlanPolicy, RouteOrdering, ShelfViewMode
from store_emulator.domain.movement import MovementReport
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig
from store_emulator.domain.operations import OperationsConfig, OperationsPlan, OperationsReplay, OperationsReport
from store_emulator.domain.scenario import Scenario
from store_emulator.domain.store import Store
from store_emulator.domain.types import RESOURCE_ID_PATTERN, ResourceId
from store_emulator.engine.run_analyst import DifferenceReading
from store_emulator.server.schemas import EngineInfo, SimulationStartResponse
from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["simulate"])
engines_router = APIRouter(prefix="/api", tags=["simulate"])


class SimulateRequest(BaseModel):
    """Simulation run request. Executed against the server-stored setup.

    Every option is optional and overrides the server configuration for this run only."""
    setup_id: ResourceId = Field(description="Setup ID")
    run_id: ResourceId | None = Field(default=None, description="run ID (auto-generated if omitted)")
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
    use_town: bool = Field(default=False, description="Draw visitors from the project's neighborhood model")
    town_scale: float = Field(default=1.0, gt=0.0, le=5.0, description="Share of the predicted daily visitors to simulate")
    plan_policy: PlanPolicy | None = Field(
        default=None,
        description='Vision shoppers only: "vlm" (the model plans the visit at the entrance) or "rule" (rule planner)',
    )
    shelf_view: ShelfViewMode | None = Field(
        default=None,
        description='Vision shoppers only: "chart" (rendered shelf chart) or "photo_chart" (the 3D store\'s photo of each '
                    "face above the chart; render the photos first with PUT /setups/{sid}/shelf-views/{key})",
    )
    operations: OperationsConfig | None = Field(
        default=None,
        description="Shoppers share the store: finite stock per shelf face, restocking, and a line at the tills "
                    "(GET /runs/{rid}/operations reports stock-outs, waits and tills needed). Omitted: the "
                    "layout's saved settings (PUT /setups/{sid}/operations), if any.",
    )
    shared_store: bool | None = Field(
        default=None,
        description="false: shoppers each have the store to themselves, whatever the layout saved. "
                    "Omitted: `operations` if given, else the layout's saved settings, else none.",
    )


@engines_router.get("/engines", summary="Available simulation engines", response_model=list[EngineInfo])
async def list_engines() -> list[EngineInfo]:
    """Engines selectable per run, with the server's current defaults. `model_ready` is false for a model on this
    computer whose server does not answer (the local model off or not started), as for a cloud model without a key."""
    return await run_in_threadpool(_engines)


def _engines() -> list[EngineInfo]:
    config = get_config()
    llm = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE)
    # The model a vision run uses when it names none: a connected cloud provider's, else the app's (local) one.
    vlm = with_vision_default(config.model_copy(update={"engine_type": EngineType.VLM_GLANCE}), None).llm_for(
        EngineType.VLM_GLANCE)
    settings = load_settings()

    def ready(model: LLMConfig) -> bool:
        if model.api_key is not None:
            return True
        if model.api_base is None and missing_key(model.model, settings) is not None:
            return False
        try:
            resolved = resolve_model(model.model, base=model)
        except ValueError:
            return False
        if resolved.api_base:   # a server (llamacpp:local, the app's local model, a self-hosted one) must answer
            return local_model_answers(resolved.api_base)
        return missing_key(model.model, settings) is None

    def suggested(model: LLMConfig) -> str:
        return "" if ready(model) else text_model_fallback(model.model, settings) or ""

    return [
        EngineInfo(
            engine_type=EngineType.PATTERN_INTENT_IMPULSE.value, label="LLM shoppers",
            description="3-stage LLM pipeline (pattern → intent → impulse). Realistic, costs LLM calls.",
            uses_llm=True, model=llm.model, default=config.engine_type == EngineType.PATTERN_INTENT_IMPULSE,
            model_ready=ready(llm), suggested_model=suggested(llm),
        ),
        EngineInfo(
            engine_type=EngineType.RULE_BASED.value, label="Rule-based preview",
            description="Calibratable heuristic shoppers. Seconds per run, no LLM cost — for quick layout iteration.",
            uses_llm=False, model="", default=config.engine_type == EngineType.RULE_BASED,
        ),
        EngineInfo(
            engine_type=EngineType.VLM_GLANCE.value, label="Vision shoppers",
            description="A vision-language model plans each visit at the entrance (store directory map, "
                        "situation, budget) and makes the impulse picks looking at rendered shelves. Runs on a "
                        "local CPU model — use a small customer sample.",
            uses_llm=True, model=vlm.model, default=config.engine_type == EngineType.VLM_GLANCE,
            model_ready=ready(vlm), suggested_model=suggested(vlm),
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


def _options(req: SimulateRequest) -> RunOptions:
    return RunOptions(
        engine_type=req.engine_type, seed=req.seed, replicate=req.replicate,
        exposure_model=req.exposure_model, route_ordering=req.route_ordering,
        max_customers=req.max_customers, preview=req.preview, model=req.model, ensemble=req.ensemble,
        scenario_id=req.scenario_id, scenario=req.scenario, use_town=req.use_town, town_scale=req.town_scale,
        plan_policy=req.plan_policy, shelf_view=req.shelf_view, operations=req.operations,
    )


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
    options = _options(req)
    config = get_config()
    try:
        ensure_resolvable(sim_service.apply_options(config, options))
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        if options.use_town:
            town_service.town_for_run(pid)  # before the setup is marked running
        run_id, store, personas, address, customer_profile, operations = await run_in_threadpool(
            sim_service.prepare_simulation, pid, req.setup_id, req.run_id,
            preview=req.preview, default_currency=config.currency,
            operations=req.operations, shared_store=req.shared_store,
        )
    except AppError as e:
        raise HTTPException(e.status_code, str(e))

    options = options.model_copy(update={"operations": operations})
    executor.submit(
        sim_service.run_simulation_background,
        pid, run_id, req.setup_id, store, personas,
        config, address, customer_profile, options,
    )

    return SimulationStartResponse(project_id=pid, run_id=run_id, setup_id=req.setup_id)


@router.post("/{pid}/runs/estimate", summary="About how long and how much a run will take",
             response_model=RunEstimate)
async def estimate_simulation(pid: str, req: SimulateRequest) -> RunEstimate:
    """Shoppers the run would simulate (after the customer cap, situation and opening hours), the model requests that
    takes, and about how many minutes and dollars (`cost_usd` null: free on this computer or the model has no listed
    price). `warn` is true from about 10 minutes or about $1: the run dialog asks before starting such a run.
    Starts nothing.

    **Errors:** 400 (no layout or customers, unknown situation), 404 (setup not found)."""
    options = _options(req)
    try:
        return await run_in_threadpool(estimate_run, pid, req.setup_id, options, get_config())
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


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
            "summary": sim_service.get_run_summary(pid, run_id),
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


@router.get("/{pid}/runs/{run_id}/operations", summary="Stock-outs and till lines of a shared-store run",
            response_model=OperationsReport)
async def get_operations(pid: str, run_id: str) -> OperationsReport:
    """What sharing the store did to a run: products that ran out (when, for how long, units and revenue lost or
    replaced by another product), shoppers' waits at the tills by hour, who left the line, the tills' use and the
    fewest tills that would have kept each hour's average wait within the target.
    404 for runs whose shoppers each had the store to themselves."""
    try:
        return OperationsReport.model_validate(sim_service.get_run_output(pid, run_id, "operations.json"))
    except FileNotFoundError:
        raise HTTPException(404, "this run did not share the store's stock and tills")
    except ValueError:   # cut short or damaged on disk
        raise HTTPException(422, "the run's operations.json is damaged and cannot be read")


@router.post("/{pid}/runs/{run_id}/operations/replay", summary="Replay a run under another operations plan",
             response_model=OperationsReplay)
async def replay_operations(pid: str, run_id: str, req: ReplayRequest) -> OperationsReplay:
    """The run's shoppers, their decisions unchanged, in a store run another way: other shelf stock (per product
    too), refills and tills staffed (per hour too). No model call; the shoppers keep their patience and their
    substitute-or-not draws, so plans compare on the same people. With `costs`, the outcome counts till hours, refill
    rounds and units kept on the shelves against revenue. Works for any completed run, shared store or not."""
    try:
        return await run_in_threadpool(replay_run, pid, run_id, req)
    except AppError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("/{pid}/runs/{run_id}/operations/plan", summary="Find an operations plan for a run's shoppers",
             response_model=OperationsPlan)
async def plan_operations(pid: str, run_id: str, req: PlanRequest) -> OperationsPlan:
    """Replays the run's shoppers under hundreds of plans — refill interval with shelf stock, more stock for the
    products that still run out, tills hour by hour — and returns the one with the most revenue left after `costs`
    (ties to the plan using less). Seconds, no model call."""
    try:
        return await run_in_threadpool(plan_run, pid, run_id, req)
    except AppError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/{pid}/compare", summary="Paired A/B comparison of two runs", response_model=ComparisonReport)
async def compare(
    pid: str,
    a: str = Query(pattern=RESOURCE_ID_PATTERN, description="baseline run id"),
    b: str = Query(pattern=RESOURCE_ID_PATTERN, description="variant run id"),
    n_bootstrap: int = Query(default=2000, ge=200, le=20000),
) -> ComparisonReport:
    """Per-customer paired comparison (B − A) with bootstrap confidence intervals.

    Customers are matched by persona id. Metrics: spend, units, bought (conversion), impulse_spend,
    visit_sec, path_tiles. Each metric reports the difference, its 95% CI, the share of bootstrap
    draws favoring B, and how many customers a 5% effect would need. Run both layouts with the same
    seed so customers share random draws — that is what makes the paired test sharp."""
    try:
        return await run_in_threadpool(sim_service.compare_project_runs, pid, a, b, n_bootstrap=n_bootstrap)
    except AppError as e:
        raise HTTPException(e.status_code, e.message)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


class ExplainRequest(BaseModel):
    model: str = Field(default="", description='model reference; "" = the app text model')


@router.post("/{pid}/compare/explain", summary="Explain why run B differs from run A", response_model=DifferenceReading)
async def explain_compare(
    pid: str, req: ExplainRequest,
    a: str = Query(pattern=RESOURCE_ID_PATTERN, description="baseline run id"),
    b: str = Query(pattern=RESOURCE_ID_PATTERN, description="variant run id"),
) -> DifferenceReading:
    """The text model reads the paired comparison and both runs' fact sheets (shelves, hours, products, groups) and
    says what changed, where it came from and what is within noise, listing the figures it used."""
    def run() -> DifferenceReading:
        try:
            return run_analyst.explain_comparison(pid, a, b, req.model, get_config())
        except AppError as e:
            raise HTTPException(e.status_code, e.message) from e

    return await run_in_threadpool(run)


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
        return await run_in_threadpool(sim_service.run_fidelity, pid, run_id, data, file.filename or "pos.csv")
    except AppError as e:
        raise HTTPException(e.status_code, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/{pid}/runs/{run_id}/movement", summary="Compare anonymous tracks with simulated movement", response_model=MovementReport)
async def movement_fidelity(
    pid: str, run_id: str,
    file: Annotated[UploadFile, File(description="UTF-8 CSV: track_id,x,y,timestamp_sec; zero-based grid cells")],
    max_gap_seconds: Annotated[float, Form(gt=0, le=300, allow_inf_nan=False)] = 30,
) -> MovementReport:
    data = await file.read(MAX_TRACK_BYTES + 1)
    if len(data) > MAX_TRACK_BYTES:
        raise HTTPException(413, "Track CSV is too large (maximum 10 MB).")
    try:
        return await run_in_threadpool(sim_service.run_movement_fidelity, pid, run_id, data, max_gap_seconds=max_gap_seconds)
    except AppError as e:
        raise HTTPException(e.status_code, e.message) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{pid}/runs/{run_id}/movement", summary="Read the aggregate movement comparison", response_model=MovementReport | None)
def get_movement_fidelity(pid: str, run_id: str) -> MovementReport | None:
    try:
        return sim_service.get_movement_fidelity(pid, run_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{pid}/runs/{run_id}/export.csv", summary="Per-customer results as CSV")
async def export_csv(pid: str, run_id: str) -> Response:
    """One row per simulated customer (persona attributes, spend, units, conversion, impulse spend,
    visit time, path length, products) — for Excel / BI tools."""
    try:
        body = await run_in_threadpool(sim_service.export_customers_csv, pid, run_id)
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


@router.get("/{pid}/runs/{run_id}/store", summary="Store at simulation time", response_model=Store)
async def get_run_store(pid: str, run_id: str) -> Store:
    """Recorded layout, enriched with current SKU photos where the snapshot has none."""
    try:
        return sim_service.get_run_store_view(pid, run_id)
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


