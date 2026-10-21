"""VLM shoppers as the judge of a layout search.

The rule-based surrogate is fast enough to score hundreds of layouts; the VLM shoppers are not, but
they are the consumer model the decision should rest on. So:

1. calibrate (optional): simulate the VLM shoppers on the baseline (the judge panel) and fit the
   surrogate's impulse knobs — impulse_base and a tilt of the shelf-level attention — by grid search
   so its impulse rate, impulse revenue share and picked-level distribution match the VLM pilot;
2. search with the (calibrated) surrogate as usual;
3. judge: simulate the VLM shoppers on the top_k distinct surrogate candidates and the baseline,
   all on the same panel (same personas and seeds: common random numbers), and pick the winner by
   the VLM objective, with paired per-customer deltas against the baseline and the Spearman rank
   agreement between surrogate and VLM scores.
"""

import logging
import random
import time
from collections.abc import Callable
from typing import cast

import numpy as np

from store_emulator.domain.analysis import ComparisonReport, MetricComparison
from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.engine import CustomerBehaviorEngine
from store_emulator.domain.optimize import (
    ImpulseProfile,
    JudgedCandidate,
    JudgeSpec,
    LayoutCandidate,
    OptimizeResult,
    OptimizeSpec,
    SurrogateCalibration,
    VLMJudgeReport,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import RACK_LEVELS
from store_emulator.domain.result import SimulationSummary
from store_emulator.domain.store import Store
from store_emulator.domain.types import PathFinder
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.analysis.fidelity import spearman
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner

from .evaluate import COMPARISON_METRICS, LayoutEvaluator
from .search import ProgressCallback, optimize

logger = logging.getLogger(__name__)

type CueSampler = Callable[[random.Random], BehaviorCue]
type PhaseCallback = Callable[[str], None]

_IMPULSE_SCALES = (0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
_LEVEL_TILTS = (0.0, 0.5, 1.0)
_LEVEL_SMOOTHING = 0.02


class OptimizationCanceled(Exception):
    """Raised between expensive steps when the job was asked to stop."""


def impulse_profile(store: Store, customers: list[CustomerResult]) -> ImpulseProfile:
    """Impulse purchase lines per visitor, impulse revenue share and the shelf levels picked."""
    levels: dict[tuple[str, str, str], int] = {}
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                levels.setdefault((rack.id, slot.face.value, item.sku), slot.level)
                levels.setdefault((rack.id, "", item.sku), slot.level)
    lines = 0
    revenue = impulse_revenue = 0
    picked = dict.fromkeys(range(1, RACK_LEVELS + 1), 0)
    for customer in customers:
        revenue += customer.total_spent
        for event in customer.purchases:
            if event.origin != "impulse":
                continue
            lines += 1
            impulse_revenue += event.price * event.quantity
            face = event.face.value if event.face is not None else ""
            level = levels.get((event.target_rack, face, event.product_sku)) or levels.get(
                (event.target_rack, "", event.product_sku))
            if level is not None:
                picked[level] += 1
    total = sum(picked.values())
    return ImpulseProfile(
        impulse_rate=round(lines / len(customers), 4) if customers else 0.0,
        impulse_revenue_share=round(impulse_revenue / revenue, 4) if revenue else 0.0,
        level_distribution={k: round(v / total, 4) for k, v in picked.items()} if total else {},
    )


def profile_gap(profile: ImpulseProfile, target: ImpulseProfile) -> float:
    """|Δ rate| / max(rate, 0.05) + 2 |Δ share| + total-variation distance of the level distributions."""
    rate = abs(profile.impulse_rate - target.impulse_rate) / max(target.impulse_rate, 0.05)
    share = 2.0 * abs(profile.impulse_revenue_share - target.impulse_revenue_share)
    if not target.level_distribution:
        levels = 0.0
    elif not profile.level_distribution:
        levels = 1.0
    else:
        levels = 0.5 * sum(abs(profile.level_distribution.get(k, 0.0) - target.level_distribution.get(k, 0.0))
                           for k in range(1, RACK_LEVELS + 1))
    return round(rate + share + levels, 4)


def _tilted_attention(
    attention: dict[int, float], before: ImpulseProfile, target: ImpulseProfile, tilt: float,
) -> dict[int, float]:
    """Level attention moved (geometrically, by `tilt` ∈ [0, 1]) toward the one-step correction
    a(l) × p_target(l) / p_surrogate(l), normalized to a maximum of 1."""
    if tilt == 0 or not target.level_distribution or not before.level_distribution:
        return dict(attention)
    corrected: dict[int, float] = {}
    for level in range(1, RACK_LEVELS + 1):
        a = attention.get(level, 0.7)
        ratio = ((target.level_distribution.get(level, 0.0) + _LEVEL_SMOOTHING)
                 / (before.level_distribution.get(level, 0.0) + _LEVEL_SMOOTHING))
        corrected[level] = a * ratio
    peak = max(corrected.values())
    out: dict[int, float] = {}
    for level, value in corrected.items():
        fitted = min(1.0, max(0.05, value / peak))
        out[level] = round(attention.get(level, 0.7) ** (1 - tilt) * fitted ** tilt, 4)
    return out


def _with_knobs(config: SimulationConfig, impulse_base: float, attention: dict[int, float]) -> SimulationConfig:
    rule = config.engines.rule_based.model_copy(update={"impulse_base": impulse_base})
    return config.model_copy(update={
        "engines": config.engines.model_copy(update={"rule_based": rule}),
        "perception": config.perception.model_copy(update={"level_attention": attention}),
    })


async def calibrate_surrogate(
    store: Store,
    config: SimulationConfig,
    personas: list[Persona],
    cue_sampler: CueSampler,
    patterns: list[BehaviorPattern],
    pathfinder: PathFinder,
    pilot: list[CustomerResult],
) -> tuple[SimulationConfig, SurrogateCalibration]:
    """Grid-search the rule surrogate's impulse_base scale × level-attention tilt so its impulse
    profile on `personas` matches the VLM `pilot` on the same store. Returns the fitted config."""
    config = config.model_copy(update={"engine_type": EngineType.RULE_BASED})
    target = impulse_profile(store, pilot)

    async def profile(cfg: SimulationConfig) -> ImpulseProfile:
        runner = PerCustomerSimulationRunner(cfg, build_engine(cfg, pathfinder=pathfinder), pathfinder,
                                             cue_sampler, patterns)
        _, customers = await runner.run(store.model_copy(deep=True), personas, max_concurrent=8)
        return impulse_profile(store, customers)

    base = config.engines.rule_based.impulse_base
    attention = dict(config.perception.level_attention)
    before = await profile(config)
    gap_before = profile_gap(before, target)
    best = (gap_before, 0, 0.0, base, attention, before)  # (gap, |log scale| order, tilt, knobs…, profile)
    tilts = _LEVEL_TILTS if target.level_distribution and before.level_distribution else (0.0,)
    points = 1
    for tilt in tilts:
        tilted = _tilted_attention(attention, before, target, tilt)
        for scale in _IMPULSE_SCALES:
            if scale == 1.0 and tilt == 0.0:
                continue
            impulse = round(min(1.0, base * scale), 5)
            fitted = await profile(_with_knobs(config, impulse, tilted))
            points += 1
            gap = profile_gap(fitted, target)
            order = abs(_IMPULSE_SCALES.index(scale) - _IMPULSE_SCALES.index(1.0))
            if (gap, order, tilt) < best[:3]:
                best = (gap, order, tilt, impulse, tilted, fitted)
    gap_after, _, _, impulse_after, attention_after, after = best
    notes: list[str] = []
    if len(pilot) < 30:
        notes.append(f"The VLM pilot has {len(pilot)} customers: the impulse targets are noisy.")
    if target.impulse_rate == 0:
        notes.append("The VLM shoppers made no impulse purchase in the pilot; the fit drives impulse buying down.")
    if gap_after >= gap_before:
        notes.append("No grid point fitted the VLM pilot better than the configured knobs; they are kept.")
    logger.info(f"[optimize] surrogate calibration: gap {gap_before} → {gap_after} "
                f"(impulse_base {base} → {impulse_after}, {points} grid points)")
    calibration = SurrogateCalibration(
        pilot_customers=len(pilot), surrogate_customers=len(personas), target=target, before=before, after=after,
        gap_before=gap_before, gap_after=gap_after, impulse_base_before=base, impulse_base_after=impulse_after,
        level_attention_before=attention, level_attention_after=attention_after, grid_points=points, notes=notes,
    )
    return _with_knobs(config, impulse_after, attention_after), calibration


def _metric(report: ComparisonReport, name: str) -> MetricComparison | None:
    return next((m for m in report.metrics if m.metric == name), None)


def _ranks(values: list[float], maximize: bool) -> list[int]:
    order = sorted(range(len(values)), key=lambda i: (-values[i] if maximize else values[i], i))
    ranks = [0] * len(values)
    for rank, i in enumerate(order, start=1):
        ranks[i] = rank
    return ranks


async def judge_layout_search(
    store: Store,
    spec: OptimizeSpec,
    judge: JudgeSpec,
    *,
    surrogate_config: SimulationConfig,
    vlm_config: SimulationConfig,
    vlm_engine: CustomerBehaviorEngine,
    search_personas: list[Persona],
    vlm_personas: list[Persona],
    cue_sampler: CueSampler,
    patterns: list[BehaviorPattern],
    pathfinder: PathFinder,
    model_label: str = "",
    on_phase: PhaseCallback | None = None,
    on_progress: ProgressCallback | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> OptimizeResult:
    """Calibrate (optional), search with the rule surrogate, then let the VLM shoppers pick the winner.

    Phases reported through `on_phase`: "calibrating", "searching", "judging k/K". `should_stop` is
    polled before every expensive step; a True raises OptimizationCanceled.
    """
    started = time.perf_counter()

    def phase(name: str) -> None:
        if should_stop is not None and should_stop():
            raise OptimizationCanceled(f"canceled before {name}")
        if on_phase is not None:
            on_phase(name)

    vlm = LayoutEvaluator(vlm_config, vlm_personas, cue_sampler, patterns, pathfinder, spec.objective,
                          engine=vlm_engine, max_concurrent=4)
    metric_name = COMPARISON_METRICS[spec.objective]
    maximize = spec.objective.maximize
    runs: dict[str, tuple[float, SimulationSummary, list[CustomerResult], int, int]] = {}
    requests = 0

    async def run_vlm(label: str, layout: Store) -> None:
        nonlocal requests
        score, aggregated, customers = await vlm.simulate(layout)
        planning = vlm.engine_metadata().get("planning")
        errors = cast(dict[str, object], planning).get("plan_errors") if isinstance(planning, dict) else None
        requests += aggregated.token_usage.requests
        runs[label] = (score, aggregated.summary, customers, len(aggregated.diagnostics.failed_customers),
                       errors if isinstance(errors, int) else 0)

    calibration: SurrogateCalibration | None = None
    config = surrogate_config.model_copy(update={"engine_type": EngineType.RULE_BASED})
    if judge.calibrate:
        phase("calibrating")
        await run_vlm("baseline", store)
        config, calibration = await calibrate_surrogate(
            store, config, search_personas, cue_sampler, patterns, pathfinder, runs["baseline"][2],
        )

    phase("searching")
    surrogate = LayoutEvaluator(config, search_personas, cue_sampler, patterns, pathfinder, spec.objective)
    search_spec = spec.model_copy(update={"validation_customers": 0})
    result = await optimize(store, search_spec, surrogate, on_progress=on_progress, keep_top=judge.top_k)
    result = result.model_copy(update={"spec": spec})
    candidates: list[LayoutCandidate] = [
        LayoutCandidate(iteration=0, score=result.baseline_score, moves=[], store=store), *result.top_candidates,
    ]
    total = len(candidates)
    for k, candidate in enumerate(candidates, start=1):
        label = "baseline" if candidate.iteration == 0 else f"#{candidate.iteration}"
        if label in runs:
            continue
        phase(f"judging {k}/{total}")
        await run_vlm(label, candidate.store)

    labels = ["baseline" if c.iteration == 0 else f"#{c.iteration}" for c in candidates]
    base_score, _, base_customers, _, _ = runs["baseline"]
    surrogate_ranks = _ranks([c.score for c in candidates], maximize)
    vlm_scores = [runs[label][0] for label in labels]
    vlm_ranks = _ranks(vlm_scores, maximize)
    judged: list[JudgedCandidate] = []
    reports: dict[str, ComparisonReport] = {}
    for i, (label, candidate) in enumerate(zip(labels, candidates, strict=True)):
        score, summary, customers, failed, plan_errors = runs[label]
        entry = JudgedCandidate(
            label=label, iteration=candidate.iteration, moves=candidate.moves, surrogate_score=candidate.score,
            surrogate_rank=surrogate_ranks[i], vlm_score=score, vlm_rank=vlm_ranks[i],
            relative_improvement=_relative(base_score, score, maximize), failed_customers=failed,
            plan_errors=plan_errors, vlm_summary=summary,
        )
        if label != "baseline":
            report = compare_runs(base_customers, customers, run_a="baseline", run_b=label, seed=spec.seed)
            reports[label] = report
            metric = _metric(report, metric_name)
            if metric is not None:
                entry = entry.model_copy(update={
                    "delta_mean": metric.diff, "delta_ci_low": metric.ci_low, "delta_ci_high": metric.ci_high,
                    "prob_better": metric.prob_b_greater if maximize else metric.prob_b_less,
                })
        judged.append(entry)

    notes: list[str] = []
    # Winner: best VLM objective; ties go to the baseline (no change), then to the surrogate's order.
    winner = min(judged, key=lambda c: (-(c.vlm_score or 0.0) if maximize else (c.vlm_score or 0.0),
                                        c.iteration != 0, c.surrogate_rank))
    if winner.label != "baseline" and (winner.relative_improvement or 0.0) < spec.constraints.min_improvement:
        notes.append(f"The VLM winner {winner.label} improved the objective by {winner.relative_improvement:.2%},"
                     f" below min_improvement {spec.constraints.min_improvement:.2%}; the baseline is kept.")
        winner = judged[0]
    surrogate_winner = min(judged, key=lambda c: c.surrogate_rank)
    judged = [c.model_copy(update={"winner": c.label == winner.label}) for c in judged]
    rho: float | None = None
    if len(judged) >= 3:
        rho = round(spearman(np.array([c.surrogate_score for c in judged]), np.array(vlm_scores)), 4)
    if winner.label == "baseline":
        notes.append(f"No judged candidate beat the baseline for the VLM shoppers on {len(vlm_personas)} customers;"
                     " the baseline is returned.")
    else:
        notes.append(
            f"The VLM shoppers picked {winner.label} ({winner.relative_improvement:+.2%} {spec.objective.value}"
            f" vs baseline on {len(vlm_personas)} paired customers, P(better) {winner.prob_better})."
        )
        if winner.delta_ci_low is not None and winner.delta_ci_high is not None and \
                winner.delta_ci_low <= 0 <= winner.delta_ci_high:
            notes.append("The paired 95% interval of the winner's gain includes zero; judge with more customers"
                         " before acting on it.")
    if winner.label != surrogate_winner.label:
        notes.append(f"The surrogate preferred {surrogate_winner.label}; the VLM shoppers ranked it"
                     f" {surrogate_winner.vlm_rank} of {len(judged)}.")
    if rho is not None:
        notes.append(f"Surrogate–VLM rank correlation over the {len(judged)} judged layouts: Spearman {rho:+.2f}.")
    failures = sum(c.failed_customers for c in judged)
    if failures:
        notes.append(f"{failures} VLM customer simulations failed and were left out of the paired deltas.")

    report = VLMJudgeReport(
        model=model_label, ensemble=vlm_config.ensemble, customers=len(vlm_personas), metric=metric_name,
        candidates=judged, winner=winner.label, surrogate_winner=surrogate_winner.label, spearman=rho,
        calibration=calibration, vlm_requests=requests, seconds=round(time.perf_counter() - started, 3),
        notes=notes,
    )
    best = candidates[labels.index(winner.label)]
    validation = reports.get(winner.label)
    metric = _metric(validation, metric_name) if validation is not None else None
    return result.model_copy(update={
        "baseline_score": base_score,
        "best_score": winner.vlm_score,
        "relative_improvement": winner.relative_improvement or 0.0,
        "best_store": best.store.model_copy(deep=True),
        "applied_moves": list(best.moves),
        "baseline_summary": runs["baseline"][1],
        "best_summary": runs[winner.label][1],
        "validation": validation,
        "validation_metric": metric_name if validation is not None else "",
        "validation_relative_improvement": (round(metric.rel_diff if maximize else -metric.rel_diff, 6)
                                            if metric is not None else None),
        "validation_prob_better": winner.prob_better if validation is not None else None,
        "notes": [*result.notes, *notes],
        "judge": report,
        "top_candidates": [],
        "seconds": round(time.perf_counter() - started, 3),
    })


def _relative(baseline: float, value: float, maximize: bool) -> float:
    if baseline == 0:
        return 0.0
    diff = value - baseline if maximize else baseline - value
    return round(diff / abs(baseline), 6)
