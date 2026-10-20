"""Layout / planogram optimization driven by synthetic consumers: request and result models."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .analysis import ComparisonReport
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
    min_improvement: float = Field(default=0.0, ge=0.0)


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


class CandidateScore(BaseModel):
    iteration: int  # 1-based evaluation index
    score: float  # objective value of the candidate on the search customers
    accepted: bool  # anneal/hill_climb: became the current layout; genetic: survived into the population
    move: str  # what was changed relative to the layout the candidate was derived from
    best_score: float  # best objective value found so far (baseline included)


class OptimizeResult(BaseModel):
    spec: OptimizeSpec
    baseline_score: float
    best_score: float
    # (best − baseline) / |baseline| in the objective's direction: > 0 always means better.
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
