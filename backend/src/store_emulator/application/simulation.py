import asyncio
import csv
import io
import logging
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, Field

from store_emulator.domain.analysis import ComparisonReport, FidelityReport
from store_emulator.domain.config import (
    EngineType, ExposureModel, PlanPolicy, RouteOrdering, ShelfViewMode, SimulationConfig,
)
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.movement import MovementReport
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig
from store_emulator.domain.scenario import Scenario
from store_emulator.domain.result import AggregatedResult
from store_emulator.domain.runner import ProgressCallback, SimulationRunner
from store_emulator.domain.store import Store
from store_emulator.domain.types import stable_seed
from store_emulator.application.pos import parse_pos_csv
from store_emulator.application.movement import read_movement, score_movement
from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.application.runner import build_runner
from store_emulator.application.product_images import project_image_loader
from store_emulator.engine.perception.product_images import ProductImageLoader
from store_emulator.application.scenarios import get_preset, prepare_inputs, who_can_come
from store_emulator.application.town import town_for_run, town_visitors
from store_emulator.domain.town import Town, TownArrival
from store_emulator.application.storage.io import DATA_DIR, read_json, write_json, now_iso
from store_emulator.application.storage.setups import (
    read_setup, write_setup, personas_path, metadata_path,
)
from store_emulator.application.storage.runs import load_run_results, load_run_store, save_run
from store_emulator.application.storage import images as image_storage
from store_emulator.engine.analysis.compare import compare_runs, customer_metrics
from store_emulator.engine.analysis.fidelity import fidelity_report

from store_emulator.application.errors import AppError, model_failure
from store_emulator.application.currencies import simulation_currency
from store_emulator.application.shelf_views import views_dir

logger = logging.getLogger(__name__)

_PROGRESS_MIN_INTERVAL_SEC = 1.0


class RunOptions(BaseModel):
    """Per-run overrides of the server config (all optional)."""
    engine_type: EngineType | None = None
    seed: int | None = None
    replicate: int | None = None
    exposure_model: ExposureModel | None = None
    route_ordering: RouteOrdering | None = None
    # Deterministic subsample of personas, for cheap pilots of the LLM engine.
    max_customers: int | None = Field(default=None, ge=1)
    # Preview runs do not lock the setup and may run on draft or finalized setups.
    preview: bool = False
    # Model reference ("anthropic:claude-haiku-5-5", "qwen:qwen3.7-plus", …) for the engine's model.
    model: str | None = None
    # Several models as one consumer population (overrides `model`).
    ensemble: EnsembleConfig | None = None
    # Situation of the run: a preset id ("heatwave_weekend") or a full scenario.
    scenario_id: str | None = None
    scenario: Scenario | None = None
    # Draw visitors from the project's neighborhood model (distance, competitors, linked trips).
    use_town: bool = False
    town_scale: float = Field(default=1.0, gt=0.0, le=5.0)
    # Vision shoppers: who plans the visit ("vlm": the model at the entrance; "rule": rule planner).
    plan_policy: PlanPolicy | None = None
    # Vision shoppers: "chart" or "photo_chart" (the 3D store's photo of each face above the chart).
    shelf_view: ShelfViewMode | None = None


def apply_options(config: SimulationConfig, options: RunOptions) -> SimulationConfig:
    updates: dict[str, object] = {}
    for field in ("engine_type", "seed", "replicate", "exposure_model", "route_ordering"):
        value = getattr(options, field)
        if value is not None:
            updates[field] = value
    if options.ensemble is not None:
        updates["ensemble"] = options.ensemble
    if options.scenario is not None:
        updates["scenario"] = options.scenario
    elif options.scenario_id:
        preset = get_preset(options.scenario_id)
        if preset is None:
            raise ValueError(f"unknown scenario preset: {options.scenario_id}")
        updates["scenario"] = None if preset.id == "baseline" else preset
    config = config.model_copy(update=updates)
    if options.model:
        config = with_engine_model(config, options.model)
    if options.plan_policy is not None:
        vlm = config.engines.vlm_glance.model_copy(update={"plan_policy": options.plan_policy})
        config = config.model_copy(update={"engines": config.engines.model_copy(update={"vlm_glance": vlm})})
    if options.shelf_view is not None:
        vlm = config.engines.vlm_glance.model_copy(update={"shelf_view": options.shelf_view})
        config = config.model_copy(update={"engines": config.engines.model_copy(update={"vlm_glance": vlm})})
    return config


def with_engine_model(config: SimulationConfig, model: str) -> SimulationConfig:
    """Point the run's engine (LLM or vision) at another model; sampling settings are kept."""
    engines = config.engines
    if config.engine_type == EngineType.VLM_GLANCE:
        vlm = engines.vlm_glance
        engines = engines.model_copy(update={"vlm_glance": vlm.model_copy(update={"llm": vlm.llm.model_copy(update={"model": model})})})
    elif config.engine_type == EngineType.PATTERN_INTENT_IMPULSE:
        pii = engines.pattern_intent_impulse
        llm = (pii.llm or config.llm).model_copy(update={"model": model})
        engines = engines.model_copy(update={"pattern_intent_impulse": pii.model_copy(update={"llm": llm})})
    else:
        return config
    return config.model_copy(update={"engines": engines})


def subsample_personas(personas: list[Persona], max_customers: int | None, seed: int) -> list[Persona]:
    """Same seed → same subset, so subsampled A/B runs stay paired. Customers the model wrote come before their twins
    (copies filling a day to its estimated visitors), so a sample has as many different people as it can."""
    if max_customers is None or max_customers >= len(personas):
        return personas
    ranked = sorted(personas, key=lambda p: (bool(p.twin_of), stable_seed(seed, "subsample", p.id)))
    keep = {p.id for p in ranked[:max_customers]}
    return [p for p in personas if p.id in keep]


async def run_simulation(
    config: SimulationConfig,
    store: Store,
    personas: list[Persona],
    max_concurrent: int = 20,
    address: str = "",
    customer_profile: str = "",
    on_progress: ProgressCallback | None = None,
    image_loader: ProductImageLoader | None = None,
) -> tuple[AggregatedResult, list[CustomerResult], SimulationRunner]:
    """Run a simulation and return (aggregated, per-customer results, runner).

    Caller uses the runner to extract engine-specific metadata via
    ``get_engine_metadata()``.
    """
    config = config.model_copy(update={"currency": store.currency or config.currency})
    runner = build_runner(config) if image_loader is None else build_runner(config, image_loader=image_loader)
    aggregated, customers = await runner.run(
        store, personas,
        max_concurrent=max_concurrent,
        address=address, customer_profile=customer_profile,
        on_progress=on_progress,
    )
    return aggregated, customers, runner


def prepare_simulation(
    pid: str, setup_id: str, run_id: str | None = None, *, preview: bool = False, default_currency: str = "USD",
) -> tuple[str, Store, list[Persona], str, str]:
    """Validate, load inputs, and transition state before running. AppError on failure.

    Three-phase helper pipeline: _validate → _load_inputs → _mark_running.
    Returns (run_id, store, personas, address, customer_profile).
    """
    setup = _validate_simulation(pid, setup_id, preview=preview)
    rid, store, personas, address, customer_profile = _load_simulation_inputs(
        pid, setup, run_id, default_currency,
    )
    _mark_simulation_running(pid, setup_id, rid, preview=preview)
    return rid, store, personas, address, customer_profile


def _validate_simulation(pid: str, setup_id: str, *, preview: bool = False) -> dict[str, Any]:
    """Single setup load + status/readiness check. Returns setup dict (with readiness)."""
    from store_emulator.application.setups import get_setup as _get_setup
    try:
        setup = _get_setup(pid, setup_id)
    except AppError:
        raise

    if not preview:
        if setup["status"] == "locked":
            raise AppError("this setup is finalized. Branch it to run again, or start a preview run.", 409)
        if setup["status"] == "running":
            raise AppError("this setup is already running.", 409)

    readiness = cast(dict[str, Any], setup.get("readiness") or {})
    if not readiness.get("ready", True):
        reasons = cast(list[str], readiness.get("reasons", []))
        raise AppError(f"cannot start simulation: {', '.join(reasons)}", 409)
    return setup


def _load_simulation_inputs(
    pid: str, setup: dict[str, Any], run_id: str | None, default_currency: str = "USD",
) -> tuple[str, Store, list[Persona], str, str]:
    """Loads Store / Persona / metadata and pre-checks run_id collision."""
    if not setup.get("store"):
        raise AppError("no store layout.")
    store = Store.model_validate(setup["store"])

    p_path = personas_path(pid)
    if not p_path.exists():
        raise AppError("no personas.")
    personas = [Persona.model_validate(p) for p in read_json(p_path)]
    if not personas:
        raise AppError("no personas.")

    rid = run_id or f"run_{uuid.uuid4().hex[:6]}"
    if _status_path(pid, rid).exists():
        raise AppError(f"run ID already exists: {rid}", 409)

    meta_file = metadata_path(pid)
    meta: dict[str, Any] = read_json(meta_file) if meta_file.exists() else {}
    store.currency = simulation_currency(pid, store, default_currency)
    address = str(meta.get("address", ""))
    customer_profile = str(meta.get("customer_profile", ""))
    return rid, store, personas, address, customer_profile


def _mark_simulation_running(pid: str, setup_id: str, run_id: str, *, preview: bool = False) -> None:
    """setup.status=running + run status=pending. Re-checks status/run_id at mark.

    A minimal CAS-style safeguard against load-vs-mark races — not fully atomic.
    recover_running_setups cleans residual running setups back to draft on restart.
    Preview runs leave the setup status untouched.
    """
    if _status_path(pid, run_id).exists():
        raise AppError(f"concurrent start detected: run ID already exists: {run_id}", 409)
    if not preview:
        fresh = read_setup(pid, setup_id)
        if fresh["status"] in ("running", "locked"):
            raise AppError("concurrent start detected: setup is already running or finalized.", 409)
        fresh["status"] = "running"
        write_setup(pid, setup_id, fresh)
    write_status(pid, run_id, "pending", setup_id=setup_id, preview=preview)


def _status_path(pid: str, run_id: str) -> Path:
    return Path(DATA_DIR) / pid / "runs" / run_id / "status.json"


def write_status(pid: str, run_id: str, status: str, error: str = "", **extra: object) -> None:
    path = _status_path(pid, run_id)
    existing: dict[str, object] = read_json(path) if path.exists() else {}
    data: dict[str, object] = {**existing, "status": status, "error": error, **extra}
    if "created_at" not in data:
        data["created_at"] = now_iso()
    write_json(path, data)


def run_shoppers(
    pid: str, config: SimulationConfig, store: Store, personas: list[Persona], options: RunOptions,
) -> tuple[SimulationConfig, Store, list[Persona], list[TownArrival], Town | None]:
    """The run's config, the store as its situation has it, and the shoppers it simulates (neighborhood visitors,
    the customer cap, the situation's days, traffic and budgets, opening hours) — what a run and its estimate see.
    Also each visitor's neighborhood arrival and the neighborhood, when the run draws from one."""
    config = apply_options(config, options)
    config = config.model_copy(update={"currency": store.currency or config.currency})
    if config.engines.vlm_glance.shelf_view == "photo_chart":
        vlm = config.engines.vlm_glance.model_copy(update={"shelf_views_dir": str(views_dir(pid))})
        config = config.model_copy(update={"engines": config.engines.model_copy(update={"vlm_glance": vlm})})
    town = town_for_run(pid) if options.use_town else None
    arrivals: list[TownArrival] = []
    if town is not None:
        personas, arrivals = town_visitors(town, personas, seed=config.seed, scale=options.town_scale,
                                           scenario=config.scenario, store=store,
                                           scenario_priors=config.scenario_priors)
    # The cap counts shoppers who come on the scenario's days and opening hours, not ones dropped right after.
    personas = subsample_personas(who_can_come(config, store, personas), options.max_customers, config.seed)
    store, personas = prepare_inputs(config, store, personas, traffic_applied=town is not None)
    return config, store, personas, arrivals, town


def run_simulation_background(
    pid: str, run_id: str, setup_id: str,
    store: Store, personas: list[Persona],
    config: SimulationConfig,
    address: str = "",
    customer_profile: str = "",
    options: RunOptions | None = None,
) -> None:
    options = options or RunOptions()
    try:
        config, store, personas, arrivals, town = run_shoppers(pid, config, store, personas, options)
        if not personas:
            # Finishing "completed" with nobody would lock the layout and the customers for good.
            raise ValueError("No shoppers come on this scenario's days and opening hours, so there is nothing to "
                             "simulate. Pick another scenario, or change the layout's opening hours.")
        write_status(
            pid, run_id, "running", total_customers=len(personas), completed_customers=0,
            failed_customers=0, engine_type=config.engine_type.value, seed=config.seed,
            replicate=config.replicate, started_at=now_iso(),
            scenario=config.scenario.name if config.scenario else "",
        )
        last_write = 0.0

        def on_progress(completed: int, failed: int, total: int) -> None:
            nonlocal last_write
            now = time.monotonic()
            if completed < total and now - last_write < _PROGRESS_MIN_INTERVAL_SEC:
                return
            last_write = now
            write_status(pid, run_id, "running", completed_customers=completed, failed_customers=failed)

        aggregated, customers, runner = asyncio.run(
            run_simulation(config, store, personas,
                           address=address, customer_profile=customer_profile,
                           on_progress=on_progress, image_loader=project_image_loader(pid)),
        )
        failed = aggregated.diagnostics.failed_customers
        if not customers and failed:
            # Every shopper failed (a key turned down, a model that is not there): a "completed" run of nobody would
            # lock the layout and the customers. Say what went wrong instead.
            raise RuntimeError(model_failure(RuntimeError(failed[0].reason),
                                             f"All {len(failed)} shoppers failed, so nothing was simulated"))
        run_dir = save_run(
            DATA_DIR, pid, run_id,
            aggregated, customers, store, personas, config,
            BEHAVIOR_PATTERNS,
        )
        meta = runner.get_engine_metadata()
        if meta:
            write_json(run_dir / "output" / f"{config.engine_type}_meta.json", meta)
        if town is not None:
            kept = {p.id for p in personas}
            write_json(run_dir / "output" / "town_arrivals.json",
                       {"town": town.name, "arrivals": [a.model_dump(mode="json") for a in arrivals if a.persona_id in kept]})
            manifest_path = run_dir / "output" / "manifest.json"
            if manifest_path.exists():
                write_json(manifest_path, {**read_json(manifest_path), "town": town.name})
        write_status(
            pid, run_id, "completed", finished_at=now_iso(),
            completed_customers=len(personas),
            failed_customers=len(aggregated.diagnostics.failed_customers),
        )

        if options.preview:
            return
        # Setup transitions to locked + runId. The run summary is the single
        # source of truth for KPIs.
        try:
            setup = read_setup(pid, setup_id)
            setup["status"] = "locked"
            setup["runId"] = run_id
            write_setup(pid, setup_id, setup)
        except Exception:
            pass  # Setup-file update failure must not lose the run data.

    except Exception as e:
        write_status(pid, run_id, "failed", f"{e}\n{traceback.format_exc()}")
        if options.preview:
            return
        try:
            setup = read_setup(pid, setup_id)
            setup["status"] = "draft"
            write_setup(pid, setup_id, setup)
        except Exception:
            pass


def _run_base(pid: str, run_id: str) -> Path:
    return Path(DATA_DIR) / pid / "runs" / run_id


def get_run_output(pid: str, run_id: str, filename: str) -> Any:
    path = _run_base(pid, run_id) / "output" / filename
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found")
    return read_json(path)


def engine_meta_summary(pid: str, run_id: str, *, max_examples: int = 8) -> dict[str, object] | None:
    """Engine-specific run metadata without its per-row records (those can be thousands of rows),
    plus a few example rows where something happened. None when the engine saved none."""
    try:
        manifest: object = get_run_output(pid, run_id, "manifest.json")
    except FileNotFoundError:
        return None
    engine_type = cast(dict[str, object], manifest).get("engine_type") if isinstance(manifest, dict) else None
    if not isinstance(engine_type, str) or not engine_type:
        return None
    try:
        raw: object = get_run_output(pid, run_id, f"{engine_type}_meta.json")
    except FileNotFoundError:
        return None
    if not isinstance(raw, dict):
        return None
    meta = cast(dict[str, object], raw)
    summary: dict[str, object] = {k: v for k, v in meta.items() if k not in ("records", "plan_records")}
    records = meta.get("records")
    if isinstance(records, list):
        rows = [cast(dict[str, object], r) for r in cast(list[object], records) if isinstance(r, dict)]
        summary["examples"] = [r for r in rows if r.get("outcome") in ("buy", "look")][:max_examples]
    plans = meta.get("plan_records")
    if isinstance(plans, list):
        rows = [cast(dict[str, object], r) for r in cast(list[object], plans) if isinstance(r, dict)]
        summary["plan_examples"] = rows[:max_examples]
    return summary


def get_run_store_view(pid: str, run_id: str) -> Store:
    """Enrich playback with current SKU photos without changing the run snapshot."""
    store = load_run_store(_run_base(pid, run_id))
    manifest = image_storage.load_manifest(pid)
    if manifest:
        for rack in store.racks:
            for slot in rack.slots:
                for item in slot.items:
                    if not item.image_url:
                        item.image_url = image_storage.image_url_for(pid, item.sku, manifest)
    return store


def get_run_input(pid: str, run_id: str, filename: str) -> Any:
    path = _run_base(pid, run_id) / "input" / filename
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found")
    return read_json(path)


def get_run_status(pid: str, run_id: str) -> dict[str, Any]:
    path = _status_path(pid, run_id)
    if not path.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")
    return read_json(path)


def list_runs(pid: str, setup_id: str | None = None) -> list[dict[str, Any]]:
    runs_dir = Path(DATA_DIR) / pid / "runs"
    if not runs_dir.exists():
        return []
    results: list[dict[str, Any]] = []
    for d in runs_dir.iterdir():
        if not d.is_dir():
            continue
        entry: dict[str, Any] = {"run_id": d.name}
        status_file = d / "status.json"
        if status_file.exists():
            entry.update(read_json(status_file))
        if setup_id and entry.get("setup_id") != setup_id:
            continue
        summary_file = d / "output" / "summary.json"
        if summary_file.exists():
            entry["summary"] = read_json(summary_file)
        manifest_file = d / "output" / "manifest.json"
        if manifest_file.exists():
            entry["manifest"] = read_json(manifest_file)
        results.append(entry)
    results.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return results


def _completed_run_base(pid: str, run_id: str) -> Path:
    base = _run_base(pid, run_id)
    if not (base / "output" / "timeline.json").exists():
        raise FileNotFoundError(f"run {run_id} has no results (not completed?)")
    return base


def compare_project_runs(
    pid: str, run_a: str, run_b: str, *, n_bootstrap: int = 2000, seed: int = 0,
) -> ComparisonReport:
    """Paired comparison of two completed runs of the same project (B − A)."""
    base_a = _completed_run_base(pid, run_a)
    base_b = _completed_run_base(pid, run_b)
    currencies: list[str] = []
    for base in (base_a, base_b):
        currency = "USD"
        for relative_path in ("output/summary.json", "input/config.json", "input/store.json"):
            path = base / relative_path
            saved: dict[str, object] = read_json(path) if path.exists() else {}
            value = saved.get("currency")
            if isinstance(value, str) and value.strip():
                currency = value.strip().upper()
                break
        currencies.append("USD" if currency == "USD_CENTS" else currency)
    if currencies[0] != currencies[1]:
        raise AppError(
            f"These runs use different currencies ({currencies[0]} and {currencies[1]}). "
            "Compare runs in the same currency; saved monetary values are not converted automatically.",
            422,
        )
    a = load_run_results(base_a)
    b = load_run_results(base_b)
    report = compare_runs(a, b, run_a=run_a, run_b=run_b, n_bootstrap=n_bootstrap, seed=seed)
    report.notes.append(f"Spend values in both runs use {currencies[0]} minor units.")
    ma, mb = _manifest_or_empty(pid, run_a), _manifest_or_empty(pid, run_b)
    if ma and mb and (ma.get("seed"), ma.get("replicate")) != (mb.get("seed"), mb.get("replicate")):
        report.notes.append(
            "Runs used different seed/replicate, so customers do not share random draws; "
            "intervals include run-to-run noise. Re-run with equal seeds for a sharper paired test."
        )
    if ma and mb and ma.get("engine_type") != mb.get("engine_type"):
        report.notes.append("Runs used different engines; the difference mixes engine and layout effects.")
    return report


def _manifest_or_empty(pid: str, run_id: str) -> dict[str, Any]:
    path = _run_base(pid, run_id) / "output" / "manifest.json"
    return cast(dict[str, Any], read_json(path)) if path.exists() else {}


def run_fidelity(pid: str, run_id: str, data: bytes, filename: str) -> FidelityReport:
    """Score a completed run against an uploaded POS export and store the report with the run."""
    base = _completed_run_base(pid, run_id)
    try:
        lines = parse_pos_csv(data, filename)
    except ValueError as e:
        raise AppError(str(e), 400)
    store = load_run_store(base)
    skus = {i.sku for r in store.racks for slot in r.slots for i in slot.items}
    if lines and not any(line.sku in skus for line in lines):
        # Scored, it read 0 on every measure and replaced any earlier report of the run.
        sample = ", ".join(sorted({line.sku for line in lines})[:3])
        raise AppError(f"None of the {len(lines)} POS lines' SKUs ({sample}…) is on this run's shelves. Export the POS "
                       "with the same product codes the layout uses (Store tab → products), then upload it again.", 400)
    report = fidelity_report(store, load_run_results(base), lines)
    write_json(base / "output" / "fidelity.json", report.model_dump())
    return report


def run_movement_fidelity(pid: str, run_id: str, data: bytes, *, max_gap_seconds: float) -> MovementReport:
    return score_movement(_completed_run_base(pid, run_id), data, max_gap_seconds=max_gap_seconds)


def get_movement_fidelity(pid: str, run_id: str) -> MovementReport | None:
    return read_movement(_completed_run_base(pid, run_id))


_ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}   # as the app shows money


def _money_unit(base: Path) -> str:
    """"USD cents", "GBP 1/100", or "KRW" (no minor unit) for a run's money columns."""
    try:
        raw = cast(dict[str, Any], read_json(base / "output" / "summary.json")).get("currency")
    except (OSError, ValueError):
        raw = None
    code = "USD" if not isinstance(raw, str) or raw in ("", "USD_CENTS") else raw.upper()
    if code in _ZERO_DECIMAL:
        return code
    return f"{code} cents" if code in ("USD", "EUR", "CAD", "AUD", "NZD") else f"{code} 1/100"


def export_customers_csv(pid: str, run_id: str) -> str:
    """One row per simulated customer: persona attributes + outcomes, for spreadsheet analysis."""
    base = _completed_run_base(pid, run_id)
    results = load_run_results(base)
    personas_raw = cast(dict[str, Any], read_json(base / "output" / "personas.json"))
    out = io.StringIO()
    persona_cols = ["identity", "age_group", "gender", "purpose", "arrival_hour", "budget_min", "budget_max"]
    metric_cols = ["spend", "units", "bought", "impulse_spend", "visit_sec", "path_tiles"]
    writer = csv.writer(out)
    # Money columns (budget_min, budget_max, spend, impulse_spend) are in the currency's minor unit, as the app keeps
    # them: say so on every row, or 350 reads as $350 in a spreadsheet.
    unit = _money_unit(base)
    writer.writerow(["persona_id", "day", "arrival_time", "leave_time", *persona_cols, *metric_cols, "products",
                     "money_unit"])
    for r in results:
        p = cast(dict[str, Any], personas_raw.get(r.persona_id, {}))
        m = customer_metrics(r)
        products = "; ".join(f"{e.product_name} x{e.quantity}" for e in r.purchases)
        row: list[object] = [
            r.persona_id, int(r.day), r.arrival_time, r.leave_time,
            *[p.get(c, "") for c in persona_cols],
            *[int(m[c]) if float(m[c]).is_integer() else m[c] for c in metric_cols],
            products, unit,
        ]
        writer.writerow("'" + cell if isinstance(cell, str) and cell.lstrip().startswith(("=", "+", "-", "@")) else cell
                        for cell in row)
    return out.getvalue()
