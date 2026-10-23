"""About how long and how much a simulation run will take, before it starts (the run dialog warns above the limits
in `estimates`).

Shoppers are counted exactly as the run will count them (customer cap, situation, opening hours, neighborhood).
Model work per shopper is measured on this project's last uncached finished run with the same engine and model when
there is one; otherwise typical figures for the engine are used. Cached replays do not predict new provider work.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from store_emulator.application.currencies import simulation_currency
from store_emulator.application.errors import AppError
from store_emulator.application.estimates import (
    cost_usd,
    effective_parallel,
    is_local_base,
    should_warn,
)
from store_emulator.application.providers import resolve_model
from store_emulator.application.simulation import RunOptions, run_shoppers
from store_emulator.application.storage.io import DATA_DIR, read_json
from store_emulator.application.storage.personas import read_personas
from store_emulator.application.storage.setups import read_setup
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig
from store_emulator.domain.store import Store

logger = logging.getLogger(__name__)

# Rule-based shoppers need no model: a few milliseconds each (10 ms leaves room for slower computers).
RULE_SECONDS_PER_SHOPPER = 0.01
# Typical model work per shopper without a finished run to measure: requests, prompt and completion tokens.
# LLM shoppers: a stage-1/2 plan and an impulse pass (measured on the sample project: ~20k prompt, ~8k completion).
# Vision shoppers: a plan at the entrance and the shelf glances that pass the gate, an image each (a local 0.8B run
# made ~1.4 requests a shopper; a provider counts more tokens for each image).
_PER_SHOPPER: dict[EngineType, tuple[float, float, float]] = {
    EngineType.PATTERN_INTENT_IMPULSE: (3.0, 20_000.0, 8_000.0),
    EngineType.VLM_GLANCE: (1.5, 2_000.0, 300.0),
}
# Seconds per request: a provider; the small model on this computer's processor.
_SECONDS_PER_REQUEST = {False: 4.0, True: 40.0}


class RunEstimate(BaseModel):
    customers: int
    days: int
    per_day: int
    engine: EngineType
    model: str
    local: bool
    model_calls: int
    minutes: float
    cost_usd: float | None
    warn: bool


class _Measured(BaseModel):
    requests: float | None   # per shopper (None: the run did not record requests)
    prompt: float
    completion: float
    seconds: float | None    # per shopper, at that run's pace


def estimate_run(pid: str, setup_id: str, options: RunOptions, config: SimulationConfig) -> RunEstimate:
    store, personas = _inputs(pid, setup_id, config.currency)
    run_config, _, shoppers, _, _ = run_shoppers(pid, config, store, personas, options)
    customers = len(shoppers)
    days = len({int(p.day) for p in shoppers}) or 1
    engine = run_config.engine_type

    def estimate(model: str, local: bool, calls: int, minutes: float, cost: float | None) -> RunEstimate:
        return RunEstimate(customers=customers, days=days, per_day=round(customers / days), engine=engine, model=model,
                           local=local, model_calls=calls, minutes=round(minutes, 1), cost_usd=cost,
                           warn=should_warn(minutes, cost))

    if engine == EngineType.RULE_BASED:
        return estimate("", True, 0, customers * RULE_SECONDS_PER_SHOPPER / 60, 0.0)

    llm = run_config.llm_for(engine)
    label = _model_label(run_config)
    resolved = _resolved(run_config, llm)
    local_members = [is_local_base(r.api_base) for r in resolved]
    local = all(local_members)
    ensemble = run_config.ensemble
    voting = ensemble is not None and ensemble.mode == "vote" and engine == EngineType.VLM_GLANCE
    weights = [member.weight for member in ensemble.members] if ensemble is not None and not voting else [1.0] * len(resolved)
    # Normalize before summing: valid finite weights can overflow together or be subnormal.
    largest = max(weights)
    weights = [weight / largest for weight in weights]
    shares = [weight / sum(weights) for weight in weights]
    requests, prompt, completion = _PER_SHOPPER.get(engine, (3.0, 7_000.0, 1_000.0))
    if voting:
        # Vision entrance plans and shelf glances ask every voter. Text engines use mixture.
        requests, prompt, completion = (value * len(resolved) for value in (requests, prompt, completion))
    seconds: float | None = None
    measured = _measured(pid, engine.value, label, ensemble)
    if measured is not None:
        requests = measured.requests if measured.requests is not None else requests
        prompt, completion, seconds = measured.prompt, measured.completion, measured.seconds
    calls = round(customers * requests)
    if seconds is not None:
        minutes = customers * seconds / 60
    else:
        cloud_seconds = 0.0
        local_seconds: dict[str, float] = {}
        for member, share, is_local in zip(resolved, shares, local_members, strict=True):
            parallel = effective_parallel(is_local, member.max_parallel)
            duration = calls * share * _SECONDS_PER_REQUEST[is_local] / parallel
            if is_local:
                endpoint = (member.api_base or "").rstrip("/")
                local_seconds[endpoint] = local_seconds.get(endpoint, 0.0) + duration
            else:
                cloud_seconds += duration
        minutes = max(cloud_seconds, *local_seconds.values(), 0.0) / 60
    cost: float | None = None
    if not local:
        prices = [0.0 if is_local else cost_usd(member.model, round(prompt * customers * share),
                                               round(completion * customers * share))
                  for member, share, is_local in zip(resolved, shares, local_members, strict=True)]
        known = [c for c in prices if c is not None]
        cost = round(sum(known), 2) if len(known) == len(prices) else None
    return estimate(label, local, calls, minutes, cost)


def _inputs(pid: str, setup_id: str, default_currency: str) -> tuple[Store, list[Persona]]:
    try:
        setup = read_setup(pid, setup_id)
    except FileNotFoundError:
        raise AppError(f"setup not found: {setup_id}", 404) from None
    if not setup.get("store"):
        raise AppError("this layout has no store yet", 400)
    store = Store.model_validate(setup["store"])
    store.currency = simulation_currency(pid, store, default_currency)
    personas = read_personas(pid)
    if not personas:
        raise AppError("the project has no customers yet", 400)
    return store, personas


def _model_label(config: SimulationConfig) -> str:
    """The model as a run's manifest names it (so a finished run with it can be found)."""
    if config.ensemble is not None:
        return f"ensemble[{config.ensemble.mode}]: " + ", ".join(
            f"{m.name}×{m.weight:g}" for m in config.ensemble.members)
    return config.llm_for(config.engine_type).model


def _resolved(config: SimulationConfig, base: LLMConfig) -> list[LLMConfig]:
    refs = [m.model for m in config.ensemble.members] if config.ensemble is not None else [base.model]
    out: list[LLMConfig] = []
    for ref in refs:
        try:
            out.append(resolve_model(ref, base=base))
        except Exception:  # an unusable reference fails the run itself with its own message
            logger.debug("could not resolve %s for an estimate", ref, exc_info=True)
            out.append(base.model_copy(update={"model": ref}))
    return out


def _measured(pid: str, engine: str, model: str, ensemble: EnsembleConfig | None = None) -> _Measured | None:
    """Model work per shopper on the newest usable uncached, successful run of this engine and model."""
    runs = Path(DATA_DIR) / pid / "runs"
    if not runs.is_dir():
        return None
    found: list[tuple[str, _Measured]] = []
    for run in runs.iterdir():
        try:
            raw_status: object = read_json(run / "status.json")
            if not isinstance(raw_status, dict):
                continue
            status = cast(dict[str, object], raw_status)
            if status.get("status") != "completed":
                continue
            failures = status.get("failed_customers", 0)
            if type(failures) is not int or failures != 0:
                # Completed counts include failed/skipped shoppers; their reduced work cannot price a full run.
                continue
            raw_manifest: object = read_json(run / "output" / "manifest.json")
            if not isinstance(raw_manifest, dict):
                continue
            manifest = cast(dict[str, object], raw_manifest)
            if manifest.get("engine_type") != engine or manifest.get("model") != model:
                continue
            if ensemble is not None:
                # Display aliases and rounded weights do not identify the models that did the work.
                raw_config: object = read_json(run / "input" / "config.json")
                if not isinstance(raw_config, dict):
                    continue
                saved = EnsembleConfig.model_validate(cast(dict[str, object], raw_config).get("ensemble"))
                if saved.mode != ensemble.mode or [(m.model, m.weight) for m in saved.members] != [
                    (m.model, m.weight) for m in ensemble.members
                ]:
                    continue
            raw_usage: object = read_json(run / "output" / "token_usage.json")
            if not isinstance(raw_usage, dict):
                continue
            usage = cast(dict[str, object], raw_usage)
            if usage.get("cached_requests", 0) != 0:
                # Cached requests add no provider tokens and run much faster. Their mix is not transferable
                # to different shoppers/layouts, so use an uncached run or the engine defaults instead.
                continue
            prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if (type(prompt) is not int or type(completion) is not int or prompt < 0 or completion < 0
                    or prompt + completion == 0):
                continue
            shoppers = status.get("completed_customers") or status.get("total_customers")
            if not isinstance(shoppers, int) or shoppers < 5:
                continue
            requests = usage.get("requests")
            seconds = _elapsed(status.get("started_at"), status.get("finished_at"))
            found.append((str(status.get("finished_at") or status.get("created_at") or ""), _Measured(
                requests=requests / shoppers if isinstance(requests, int) and requests > 0 else None,
                prompt=prompt / shoppers,
                completion=completion / shoppers,
                seconds=seconds / shoppers if seconds else None,
            )))
        except (OSError, ValueError):
            continue
    return max(found, key=lambda pair: pair[0])[1] if found else None


def _elapsed(started: object, finished: object) -> float | None:
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    try:
        seconds = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
    except (ValueError, TypeError):  # mixed timezone-aware/naive legacy clocks cannot measure elapsed time
        return None
    return seconds if seconds > 0 else None
