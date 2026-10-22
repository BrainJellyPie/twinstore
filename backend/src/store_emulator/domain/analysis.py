"""Report models for run-vs-run comparison and simulation-vs-reality fidelity."""

from pydantic import BaseModel


class MetricComparison(BaseModel):
    metric: str
    mean_a: float
    mean_b: float
    diff: float           # mean_b - mean_a (per customer)
    rel_diff: float       # diff / mean_a (0 when mean_a == 0)
    ci_low: float         # paired-bootstrap percentile CI of diff
    ci_high: float
    prob_b_greater: float  # share of bootstrap draws with diff > 0
    sd_paired_diff: float
    n_for_5pct_effect: int  # customers needed to detect a 5% relative change (α=0.05, power=0.8)
    prob_b_less: float | None = None  # share of draws with diff < 0; absent in older saved reports


class ComparisonReport(BaseModel):
    run_a: str
    run_b: str
    paired_customers: int
    unpaired_a: int
    unpaired_b: int
    n_bootstrap: int
    confidence: float
    metrics: list[MetricComparison]
    notes: list[str] = []
    # ISO code of both runs' money (spend values are in its minor unit: cents for USD, won for KRW); "" = unknown
    currency: str = ""


class FidelityMetric(BaseModel):
    name: str
    value: float | None  # None when the metric is undefined for this data (e.g. no baskets)
    better: str  # "higher" | "lower" | "closer to 1"
    description: str = ""


class FidelityReport(BaseModel):
    sim_customers: int
    real_transactions: int
    matched_skus: int
    metrics: list[FidelityMetric]
    notes: list[str] = []
