"""Layout / planogram optimization driven by synthetic consumers: request and result models."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .analysis import ComparisonReport
from .providers import EnsembleConfig
from .result import SimulationSummary
from .store import Store


class OptimizeObjective(StrEnum):
    REVENUE_PER_VISITOR = "revenue_per_visitor"
    TOTAL_REVENUE = "total_revenue"
    CONVERSION_RATE = "conversion_rate"
    IMPULSE_REVENUE = "impulse_revenue"  # total revenue from impulse lines (minor currency unit)
    UNITS_PER_VISITOR = "units_per_visitor"
    WALKING_DISTANCE = "walking_distance"  # average path tiles per visitor, minimized

    @property
    def maximize(self) -> bool:
        return self is not OptimizeObjective.WALKING_DISTANCE


class OptimizeScope(StrEnum):
    # Racks stay put; items, slots, faces, levels and whole rack contents (with their labels) move.
    PLANOGRAM = "planogram"
    # Racks swap places or move to free tiles; contents travel with the rack.
    PLACEMENT = "placement"
    BOTH = "both"


type OptimizeAlgorithm = Literal["anneal", "hill_climb", "genetic"]


class OptimizeConstraints(BaseModel):
    keep_fridges_on_walls: bool = True  # a moved fridge must end on a border tile
    lock_rack_ids: list[str] = []  # locked racks keep both their position and their contents
    # Maximum number of moves separating the result from the baseline (redundant moves are pruned).
    max_moves: int = Field(default=10, ge=1, le=50)
    # Minimum relative improvement (in the objective's direction) the best layout must show on the
    # search customers to be returned; otherwise the baseline is returned unchanged.
    min_improvement: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)


class OptimizeSpec(BaseModel):
    objective: OptimizeObjective = OptimizeObjective.REVENUE_PER_VISITOR
    scope: OptimizeScope = OptimizeScope.PLANOGRAM
    # hill_climb only accepts paired (common-random-number) improvements, the most noise-robust choice.
    algorithm: OptimizeAlgorithm = "hill_climb"
    budget: int = Field(default=120, ge=1, le=10_000)  # candidate evaluations (baseline excluded)
    eval_customers: int = Field(default=300, ge=10)  # personas simulated per candidate
    # Personas for the final paired baseline-vs-best check. None → 3 × eval_customers; 0 skips it.
    validation_customers: int | None = Field(default=None, ge=0)
    seed: int = 0  # search randomness only; the simulation seed comes from SimulationConfig
    constraints: OptimizeConstraints = OptimizeConstraints()

    @property
    def validation_size(self) -> int:
        return 3 * self.eval_customers if self.validation_customers is None else self.validation_customers


# Who picks the winning layout: the rule surrogate alone, or the VLM shoppers judging the
# surrogate search's best candidates on a common panel.
type OptimizeJudge = Literal["rule", "vlm"]


class JudgeSpec(BaseModel):
    judge: OptimizeJudge = "rule"
    model: str | None = None  # model reference for the VLM shoppers (None = server default)
    ensemble: EnsembleConfig | None = None
    vlm_customers: int = Field(default=60, ge=4, le=400)  # one panel, simulated on every judged layout
    top_k: int = Field(default=4, ge=1, le=8)  # distinct surrogate-best candidates judged (plus the baseline)
    calibrate: bool = True  # fit the surrogate's impulse knobs to a VLM pilot on the baseline first


class ImpulseProfile(BaseModel):
    """What calibration matches between the VLM shoppers and the rule surrogate."""
    impulse_rate: float  # impulse purchase lines per visitor
    impulse_revenue_share: float
    level_distribution: dict[int, float]  # share of impulse picks per shelf level (1 bottom … 4 top)


class SurrogateCalibration(BaseModel):
    pilot_customers: int  # VLM shoppers on the baseline (the judge panel)
    surrogate_customers: int  # rule shoppers per grid point (the search panel)
    target: ImpulseProfile  # VLM pilot
    before: ImpulseProfile  # rule surrogate with the configured knobs
    after: ImpulseProfile  # rule surrogate with the fitted knobs
    # Distance: |Δ rate| / max(rate, 0.05) + 2 |Δ share| + total-variation distance of the levels.
    gap_before: float
    gap_after: float
    impulse_base_before: float
    impulse_base_after: float
    level_attention_before: dict[int, float]
    level_attention_after: dict[int, float]
    grid_points: int
    notes: list[str] = []


class JudgedCandidate(BaseModel):
    label: str  # "baseline" or "#<search iteration>"
    iteration: int  # 0 = baseline
    moves: list[str]
    surrogate_score: float  # objective on the search panel (rule surrogate)
    surrogate_rank: int  # 1 = best among the judged layouts
    vlm_score: float | None = None  # objective on the judge panel (VLM shoppers)
    vlm_rank: int | None = None
    # Paired per-customer difference vs the baseline on the judge panel (candidate − baseline) in the
    # objective's per-customer metric; prob_better is oriented so that > 0.5 means better.
    delta_mean: float | None = None
    delta_ci_low: float | None = None
    delta_ci_high: float | None = None
    prob_better: float | None = None
    relative_improvement: float | None = None  # VLM objective vs baseline, > 0 = better
    failed_customers: int = 0
    plan_errors: int = 0
    vlm_summary: SimulationSummary | None = None
    winner: bool = False


class VLMJudgeReport(BaseModel):
    model: str
    ensemble: EnsembleConfig | None = None
    customers: int
    metric: str  # per-customer metric of the paired deltas (e.g. "spend")
    candidates: list[JudgedCandidate]  # baseline first, then by surrogate rank
    winner: str  # label of the VLM winner ("baseline" when no candidate beat it)
    surrogate_winner: str  # label of the surrogate's best among the judged layouts
    # Rank agreement of surrogate and VLM scores over the judged layouts (None for < 3 layouts).
    spearman: float | None = None
    calibration: SurrogateCalibration | None = None
    vlm_requests: int = 0
    seconds: float = 0.0
    notes: list[str] = []


class CandidateScore(BaseModel):
    iteration: int  # 1-based evaluation index
    score: float  # objective value of the candidate on the search customers
    accepted: bool  # anneal/hill_climb: became the current layout; genetic: survived into the population
    move: str  # what was changed relative to the layout the candidate was derived from
    best_score: float  # best objective value found so far (baseline included)


class LayoutCandidate(BaseModel):
    """A distinct layout the search scored (for judging by another shopper model)."""
    iteration: int
    score: float
    moves: list[str]
    store: Store


class OptimizeResult(BaseModel):
    spec: OptimizeSpec
    baseline_score: float
    best_score: float
    # (best − baseline) / |baseline| in the objective's direction: > 0 always means better.
    # Zero when the baseline is zero; use the score difference in that case.
    relative_improvement: float
    best_store: Store
    applied_moves: list[str]  # human-readable, in application order, redundant moves pruned
    history: list[CandidateScore]
    evaluations: int
    cache_hits: int = 0  # candidates whose score came from the evaluator cache
    seconds: float
    baseline_summary: SimulationSummary | None = None
    best_summary: SimulationSummary | None = None
    # Paired comparison baseline (A) vs best (B) on the validation customers with a fresh replicate.
    validation: ComparisonReport | None = None
    validation_metric: str = ""  # ComparisonReport metric matching the objective (e.g. "spend")
    validation_relative_improvement: float | None = None  # in the objective's direction
    validation_prob_better: float | None = None  # bootstrap probability that best beats baseline
    notes: list[str] = []
    # judge "vlm": the VLM shoppers' verdict. best_store / applied_moves / scores are the VLM winner's
    # and validation is the paired judge-panel comparison of the winner with the baseline.
    judge: VLMJudgeReport | None = None
    # optimize(keep_top=k): the k best distinct layouts of the search (in memory only, never saved).
    top_candidates: list[LayoutCandidate] = Field(default=[], exclude=True)

