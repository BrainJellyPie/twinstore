import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, RunManifest
from store_emulator.domain.store import Store

from store_emulator.application.storage.io import now_iso, read_json, write_json


def save_run(
    data_dir: str,
    project_id: str,
    run_id: str,
    result: AggregatedResult,
    customer_results: list[CustomerResult],
    store: Store,
    personas: list[Persona],
    config: SimulationConfig,
    patterns: list[BehaviorPattern] | None = None,
) -> Path:
    base = Path(data_dir) / project_id / "runs" / run_id
    save_run_dir(base, result, customer_results, store, personas, config, patterns)
    return base


def save_run_dir(
    base: Path,
    result: AggregatedResult,
    customer_results: list[CustomerResult],
    store: Store,
    personas: list[Persona],
    config: SimulationConfig,
    patterns: list[BehaviorPattern] | None = None,
) -> None:
    """Write a run in the standard layout (input/ + output/). Used by the API and the CLI."""
    _save_input(base, store, personas, config, patterns)
    _save_output(base, result, customer_results, personas)
    write_json(base / "output" / "manifest.json", build_manifest(store, personas, config).model_dump())


def load_run_results(base: Path) -> list[CustomerResult]:
    path = base / "output" / "timeline.json"
    return [CustomerResult.model_validate(c) for c in read_json(path)]


def load_run_store(base: Path) -> Store:
    return Store.model_validate(read_json(base / "input" / "store.json"))


def fingerprint(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]


def build_manifest(store: Store, personas: list[Persona], config: SimulationConfig) -> RunManifest:
    try:
        pkg = version("store-emulator")
    except PackageNotFoundError:
        pkg = ""
    llm = config.llm_for(config.engine_type)
    model = llm.model
    if config.ensemble is not None:
        model = f"ensemble[{config.ensemble.mode}]: " + ", ".join(
            f"{m.name}×{m.weight:g}" for m in config.ensemble.members)
    return RunManifest(
        engine_type=config.engine_type.value,
        model=model if config.engine_type.value != "rule_based" else "",
        seed=config.seed,
        replicate=config.replicate,
        exposure_model=config.exposure_model,
        route_ordering=config.route_ordering,
        store_fingerprint=fingerprint(store.model_dump()),
        persona_fingerprint=fingerprint([p.model_dump() for p in personas]),
        package_version=pkg,
        created_at=now_iso(),
        scenario=config.scenario.name if config.scenario else "",
        scenario_id=config.scenario.id if config.scenario else "",
    )


def _save_input(
    base: Path,
    store: Store,
    personas: list[Persona],
    config: SimulationConfig,
    patterns: list[BehaviorPattern] | None,
) -> None:
    d = base / "input"
    d.mkdir(parents=True, exist_ok=True)
    write_json(d / "store.json", store.model_dump())
    write_json(d / "personas.json", [p.model_dump() for p in personas])
    write_json(d / "config.json", config.model_dump())
    if patterns:
        write_json(d / "behavior_patterns.json", [p.model_dump() for p in patterns])


def _save_output(
    base: Path,
    result: AggregatedResult,
    customer_results: list[CustomerResult],
    personas: list[Persona],
) -> None:
    d = base / "output"
    d.mkdir(parents=True, exist_ok=True)
    write_json(d / "summary.json", result.summary.model_dump())
    write_json(d / "pathcalc_heatmap.json", result.pathcalc_heatmap)
    write_json(d / "persona_heatmap.json", result.persona_heatmap)
    write_json(d / "dwell_heatmap.json", result.dwell_heatmap)
    write_json(d / "diagnostics.json", result.diagnostics.model_dump())
    if result.operations is not None:
        write_json(d / "operations.json", result.operations.model_dump())
        write_json(d / "timeline_planned.json", [cr.model_dump() for cr in result.planned_customers])
    write_json(d / "timeline.json", [cr.model_dump() for cr in customer_results])
    write_json(d / "personas.json", {p.id: p.model_dump() for p in personas})
    write_json(d / "token_usage.json", result.token_usage.model_dump())
