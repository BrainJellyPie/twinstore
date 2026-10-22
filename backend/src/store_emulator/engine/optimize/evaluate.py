"""Scoring a candidate layout by simulating a fixed panel of synthetic shoppers.

Every candidate is simulated with the same SimulationConfig seed and replicate, so each persona
gets the same cue, arrival time and engine random stream in every layout (common random
numbers). Score differences between candidates then come from the layout, not from resampled
shoppers, which is what lets a few hundred customers rank layouts reliably.
"""

import hashlib
import random
from collections import OrderedDict
from collections.abc import Callable

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.engine import CustomerBehaviorEngine, EngineMetadataSource
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, SimulationSummary
from store_emulator.domain.store import Store
from store_emulator.domain.types import PathFinder, stable_seed
from store_emulator.engine.simulation.factory import build_engine
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner

# Per-customer metric of `engine.analysis.compare` that tracks each objective.
COMPARISON_METRICS: dict[OptimizeObjective, str] = {
    OptimizeObjective.REVENUE_PER_VISITOR: "spend",
    OptimizeObjective.TOTAL_REVENUE: "spend",
    OptimizeObjective.CONVERSION_RATE: "bought",
    OptimizeObjective.IMPULSE_REVENUE: "impulse_spend",
    OptimizeObjective.UNITS_PER_VISITOR: "units",
    OptimizeObjective.WALKING_DISTANCE: "path_tiles",
}


def store_fingerprint(store: Store) -> str:
    """Exact content hash of a layout (rack and slot order included: the engines iterate in that order)."""
    return hashlib.sha256(store.model_dump_json().encode()).hexdigest()


def objective_value(objective: OptimizeObjective, summary: SimulationSummary) -> float:
    match objective:
        case OptimizeObjective.REVENUE_PER_VISITOR:
            value = summary.revenue_per_visitor
        case OptimizeObjective.TOTAL_REVENUE:
            value = float(summary.total_revenue)
        case OptimizeObjective.CONVERSION_RATE:
            value = summary.conversion_rate
        case OptimizeObjective.IMPULSE_REVENUE:
            value = summary.total_revenue * summary.impulse_revenue_share
        case OptimizeObjective.UNITS_PER_VISITOR:
            value = summary.units_sold / summary.total_customers if summary.total_customers else 0.0
        case OptimizeObjective.WALKING_DISTANCE:
            value = summary.avg_path_tiles
    return round(value, 6)


def select_personas(personas: list[Persona], n: int, *, seed: int = 0) -> list[Persona]:
    """Deterministic subsample of `n` personas, kept in input order (all of them when n >= len).

    Customers the model wrote come before their twins (copies filling a day to its visitors): a study panel of
    twins counts the same person as independent respondents (100 picked from a quick-sample store held 63 people).
    """
    if n >= len(personas):
        return list(personas)
    rng = random.Random(stable_seed("optimize-personas", seed, n, len(personas)))
    written = [i for i, p in enumerate(personas) if not p.twin_of]
    if len(written) == len(personas) or n <= len(written):
        keep = set(rng.sample(written, n))   # the same draw as before when nobody is a twin
    else:
        twins = [i for i, p in enumerate(personas) if p.twin_of]
        keep = set(written) | set(rng.sample(twins, n - len(written)))
    return [p for i, p in enumerate(personas) if i in keep]


class LayoutEvaluator:
    """Scores layouts for one objective on a fixed persona panel, with an LRU cache by fingerprint.

    Without an explicit `engine` the config is forced to the rule-based engine (fast, LLM-free).
    Pass an engine (and a matching config) to optimize against another shopper model. Reuse one
    pathfinder: its memo makes planogram-only candidates (unchanged floor grid) much cheaper.
    """

    def __init__(
        self,
        config: SimulationConfig,
        personas: list[Persona],
        cue_sampler: Callable[[random.Random], BehaviorCue],
        patterns: list[BehaviorPattern],
        pathfinder: PathFinder,
        objective: OptimizeObjective,
        *,
        engine: CustomerBehaviorEngine | None = None,
        cache_size: int = 256,
        max_concurrent: int = 8,
        prepare_store: Callable[[Store], Store] | None = None,
    ) -> None:
        if not personas:
            raise ValueError("LayoutEvaluator needs at least one persona")
        if engine is None:
            config = config.model_copy(update={"engine_type": EngineType.RULE_BASED})
            engine = build_engine(config, pathfinder=pathfinder)
        self.config = config
        self.personas = list(personas)
        self.objective = objective
        self._engine = engine
        self._pathfinder = pathfinder
        self._cue_sampler = cue_sampler
        self._patterns = patterns
        self._max_concurrent = max_concurrent
        self._cache_size = cache_size
        # The run's situation applied to each layout before shoppers walk it (promotions priced, stock-outs emptied).
        # Layouts, their fingerprints and the best one kept stay as the user's, without promotion prices.
        self._prepare_store = prepare_store
        self._cache: OrderedDict[str, tuple[float, SimulationSummary]] = OrderedDict()
        self.evaluations = 0  # simulations actually run by `evaluate`
        self.cache_hits = 0

    def _walked(self, store: Store) -> Store:
        # The runner clears unreachable slots in place, so it gets a private copy.
        copy = store.model_copy(deep=True)
        return self._prepare_store(copy) if self._prepare_store is not None else copy

    def _runner(self, replicate: int) -> PerCustomerSimulationRunner:
        config = self.config if replicate == self.config.replicate else self.config.model_copy(update={"replicate": replicate})
        return PerCustomerSimulationRunner(config, self._engine, self._pathfinder, self._cue_sampler, self._patterns)

    async def evaluate(self, store: Store) -> tuple[float, SimulationSummary]:
        """Objective value and run summary of `store` on the evaluator's personas.

        The returned summary may be shared with the cache; treat it as read-only.
        """
        key = store_fingerprint(store)
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            self.cache_hits += 1
            return hit
        aggregated, _ = await self._runner(self.config.replicate).run(
            self._walked(store), self.personas, max_concurrent=self._max_concurrent, path_heatmap=False,
        )
        self.evaluations += 1
        entry = (objective_value(self.objective, aggregated.summary), aggregated.summary)
        self._cache[key] = entry
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return entry

    async def evaluate_customers(
        self, store: Store, personas: list[Persona], *, replicate: int | None = None,
    ) -> list[CustomerResult]:
        """Per-customer results for a paired comparison (not cached).

        `replicate` defaults to the config's; pass another one to draw fresh shopper randomness
        (still shared between the layouts compared with that same replicate).
        """
        rep = self.config.replicate if replicate is None else replicate
        _, customers = await self._runner(rep).run(
            self._walked(store), personas, max_concurrent=self._max_concurrent, path_heatmap=False,
        )
        return customers

    async def simulate(self, store: Store) -> tuple[float, AggregatedResult, list[CustomerResult]]:
        """Objective value, aggregated result and per-customer results of `store` on the evaluator's
        personas (not cached; for expensive shopper models whose every run is kept)."""
        aggregated, customers = await self._runner(self.config.replicate).run(
            self._walked(store), self.personas, max_concurrent=self._max_concurrent,
        )
        self.evaluations += 1
        return objective_value(self.objective, aggregated.summary), aggregated, customers

    def engine_metadata(self) -> dict[str, object]:
        """Run metadata of the evaluator's engine after its last run ({} when it keeps none)."""
        return self._engine.metadata() if isinstance(self._engine, EngineMetadataSource) else {}
