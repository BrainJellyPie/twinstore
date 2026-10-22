"""Paired run-vs-run comparison (layout A/B tests, test–retest noise floors).

Customers are paired by persona id. Because the simulator derives every random
stream from (seed, replicate, persona id), two layouts run with the same seed see
the same customers in the same states, so the paired difference isolates the
layout effect. The uncertainty is a percentile bootstrap over personas.
"""

import math

import numpy as np

from store_emulator.domain.analysis import ComparisonReport, MetricComparison
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.types import Action

# Per-customer outcomes compared between runs.
CUSTOMER_METRICS: tuple[str, ...] = ("spend", "units", "bought", "impulse_spend", "visit_sec", "path_tiles")

_Z_ALPHA = 1.959964  # two-sided α = 0.05
_Z_POWER = 0.841621  # power = 0.8


def customer_metrics(result: CustomerResult) -> dict[str, float]:
    impulse = sum(e.price * e.quantity for e in result.purchases if e.origin == "impulse")
    return {
        "spend": float(result.total_spent),
        "units": float(result.units_bought),
        "bought": 1.0 if result.purchases else 0.0,
        "impulse_spend": float(impulse),
        "visit_sec": float(result.duration_sec),
        "path_tiles": float(sum(1 for e in result.timeline if e.action == Action.MOVE)),
    }


def required_n(sd_diff: float, mean_a: float, rel_effect: float = 0.05) -> int:
    """Customers needed to detect a `rel_effect` relative change of the mean (paired z-test)."""
    delta = abs(mean_a) * rel_effect
    if delta == 0 or sd_diff == 0:
        return 0
    return math.ceil(((_Z_ALPHA + _Z_POWER) * sd_diff / delta) ** 2)


def _records_origin(results: list[CustomerResult]) -> bool:
    """Whether a run's purchases say if they were planned or impulse buys (runs before that did not)."""
    purchases = [e for r in results for e in r.purchases]
    return not purchases or any(e.origin for e in purchases)


def compare_runs(
    results_a: list[CustomerResult],
    results_b: list[CustomerResult],
    *,
    run_a: str = "A",
    run_b: str = "B",
    n_bootstrap: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> ComparisonReport:
    a = {r.persona_id: customer_metrics(r) for r in results_a}
    b = {r.persona_id: customer_metrics(r) for r in results_b}
    ids = sorted(set(a) & set(b))
    notes: list[str] = []
    if len(ids) < len(a) or len(ids) < len(b):
        notes.append(
            f"{len(a) - len(ids)} customers only in {run_a} and {len(b) - len(ids)} only in {run_b} "
            "were excluded (failed or different persona sets)."
        )
    if len(ids) < 30:
        notes.append("Fewer than 30 paired customers: intervals are unreliable.")

    # A run made before purchases recorded their origin has no impulse spend to compare (it read as a drop to 0).
    unrecorded = [run for run, results in ((run_a, results_a), (run_b, results_b)) if not _records_origin(results)]
    if unrecorded:
        notes.append(f"Impulse spend is not compared: {' and '.join(unrecorded)} was made by an older version that did "
                     "not record which purchases were impulse buys. Re-run it to compare impulse spend.")

    rng = np.random.default_rng(abs(seed))
    n = len(ids)
    lo_q, hi_q = (1 - confidence) / 2 * 100, (1 + confidence) / 2 * 100
    metrics: list[MetricComparison] = []
    for name in CUSTOMER_METRICS:
        if name == "impulse_spend" and unrecorded:
            continue
        xa = np.array([a[i][name] for i in ids], dtype=float)
        xb = np.array([b[i][name] for i in ids], dtype=float)
        if n == 0:
            continue
        d = xb - xa
        boot = _bootstrap_means(d, n_bootstrap, rng)
        mean_a, mean_b = float(xa.mean()), float(xb.mean())
        sd = float(d.std(ddof=1)) if n > 1 else 0.0
        metrics.append(MetricComparison(
            metric=name,
            mean_a=round(mean_a, 6),
            mean_b=round(mean_b, 6),
            diff=round(mean_b - mean_a, 6),
            rel_diff=round((mean_b - mean_a) / mean_a, 6) if mean_a else 0.0,
            ci_low=round(float(np.percentile(boot, lo_q)), 6),
            ci_high=round(float(np.percentile(boot, hi_q)), 6),
            prob_b_greater=round(float((boot > 0).mean()), 4),
            prob_b_less=round(float((boot < 0).mean()), 4),
            sd_paired_diff=round(sd, 6),
            n_for_5pct_effect=required_n(sd, mean_a),
        ))
    return ComparisonReport(
        run_a=run_a, run_b=run_b, paired_customers=n,
        unpaired_a=len(a) - n, unpaired_b=len(b) - n,
        n_bootstrap=n_bootstrap, confidence=confidence,
        metrics=metrics, notes=notes,
    )


def _bootstrap_means(d: np.ndarray, n_bootstrap: int, rng: np.random.Generator) -> np.ndarray:
    """Means of `n_bootstrap` resamples of `d`, computed in chunks to bound memory."""
    n = len(d)
    out = np.empty(n_bootstrap, dtype=float)
    chunk = max(1, min(n_bootstrap, 4_000_000 // max(1, n)))
    for start in range(0, n_bootstrap, chunk):
        size = min(chunk, n_bootstrap - start)
        idx = rng.integers(0, n, size=(size, n))
        out[start:start + size] = d[idx].mean(axis=1)
    return out
