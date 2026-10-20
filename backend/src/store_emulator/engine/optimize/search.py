"""Layout search: simulated annealing, hill climbing with restarts and a small genetic algorithm.

A candidate is a sequence of moves replayed on the baseline (at most `max_moves` long), so
every result can be explained as a short list of edits and the genetic algorithm can recombine
parents by replaying both parents' moves. All randomness comes from one `random.Random`
seeded with `stable_seed(...)` of the spec, and the evaluator uses common random numbers, so a
given (store, spec, personas, config) always produces the same result.

`budget` counts candidate evaluations (the baseline and the final validation are extra).
Proposals that reproduce an already scored layout are redrawn a few times before being
accepted, so the budget is spent on new layouts; repeats are served from the evaluator cache.
"""

import logging
import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from store_emulator.domain.analysis import ComparisonReport
from store_emulator.domain.optimize import (
    CandidateScore,
    LayoutCandidate,
    OptimizeResult,
    OptimizeSpec,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import SimulationSummary
from store_emulator.domain.store import Store
from store_emulator.domain.types import stable_seed
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.validation import validate

from .evaluate import COMPARISON_METRICS, LayoutEvaluator, store_fingerprint
from .moves import Move, MoveRules, random_move, replay

logger = logging.getLogger(__name__)

type ProgressCallback = Callable[[int, int, float], None]  # (evaluations done, budget, best score)

_PROPOSAL_ATTEMPTS = 30
_T_START = 0.005  # annealing temperature as a fraction of |baseline score|: a 0.5 % loss is accepted w.p. 1/e
_T_END = 0.0001
_RESTART_STEPS = 3  # hill climbing restarts from the baseline plus this many random moves
_SEED_STEPS = 3  # genetic seeds carry 1..this many random moves
_MUTATION_RATE = 0.5
_MAX_POPULATION = 10


@dataclass(frozen=True)
class _Candidate:
    moves: tuple[Move, ...]
    descriptions: tuple[str, ...]
    store: Store
    score: float
    summary: SimulationSummary
    iteration: int  # 0 = baseline


@dataclass(frozen=True)
class _Proposal:
    moves: tuple[Move, ...]
    descriptions: tuple[str, ...]
    store: Store
    label: str


class _Search:
    """Budget, history and best-so-far bookkeeping shared by the three algorithms."""

    def __init__(
        self,
        baseline: _Candidate,
        spec: OptimizeSpec,
        evaluator: LayoutEvaluator,
        rules: MoveRules,
        on_progress: ProgressCallback | None,
    ) -> None:
        self.baseline = baseline
        self.spec = spec
        self.evaluator = evaluator
        self.rules = rules
        self.rng = random.Random(stable_seed(
            "optimize", spec.seed, spec.algorithm, spec.scope.value, spec.objective.value,
        ))
        self.on_progress = on_progress
        self.best = baseline
        self.history: list[CandidateScore] = []
        self.notes: list[str] = []
        self.evaluations = 0
        self.cache_hits = 0
        self._seen: set[str] = {store_fingerprint(baseline.store)}
        self.scored: dict[str, _Candidate] = {}  # fingerprint → first candidate with that layout

    @property
    def remaining(self) -> int:
        return self.spec.budget - self.evaluations

    @property
    def max_moves(self) -> int:
        return self.spec.constraints.max_moves

    def gain(self, score: float) -> float:
        """Score oriented so that larger is always better."""
        return score if self.spec.objective.maximize else -score

    def fitter(self, candidate: _Candidate) -> tuple[float, int]:
        """Sort key: best first, earlier (shorter history) first on ties."""
        return -self.gain(candidate.score), candidate.iteration

    async def evaluate(self, proposal: _Proposal) -> _Candidate:
        hits = self.evaluator.cache_hits
        score, summary = await self.evaluator.evaluate(proposal.store)
        self.cache_hits += self.evaluator.cache_hits - hits
        self.evaluations += 1
        key = store_fingerprint(proposal.store)
        self._seen.add(key)
        candidate = _Candidate(proposal.moves, proposal.descriptions, proposal.store, score, summary, self.evaluations)
        self.scored.setdefault(key, candidate)
        return candidate

    def record(self, candidate: _Candidate, accepted: bool, label: str) -> None:
        if self.gain(candidate.score) > self.gain(self.best.score):
            self.best = candidate
        self.history.append(CandidateScore(
            iteration=candidate.iteration, score=candidate.score, accepted=accepted,
            move=label, best_score=self.best.score,
        ))
        if self.on_progress is not None:
            try:
                self.on_progress(self.evaluations, self.spec.budget, self.best.score)
            except Exception as e:  # noqa: BLE001 — progress reporting must never break a search
                logger.warning(f"[optimize] progress callback failed: {e}")

    def _settle(self, store: Store, attempt: int) -> bool:
        """Accept a proposal: new layouts always, an already scored one only on the last attempt."""
        return store_fingerprint(store) not in self._seen or attempt == _PROPOSAL_ATTEMPTS - 1

    def _drop_one(
        self, moves: tuple[Move, ...] | list[Move], descriptions: tuple[str, ...] | list[str],
    ) -> tuple[Store, list[Move], list[str], str]:
        """Replay `moves` without a random one; returns the store, kept moves, descriptions and a label."""
        drop = self.rng.randrange(len(moves))
        store, kept, kept_descriptions = replay(
            self.baseline.store, list(moves[:drop]) + list(moves[drop + 1:]), self.rules,
        )
        return store, kept, kept_descriptions, f"undo [{descriptions[drop]}]; "

    def neighbor(self, current: _Candidate) -> _Proposal | None:
        """`current` plus one random move (replacing a random earlier move at the max_moves cap)."""
        for attempt in range(_PROPOSAL_ATTEMPTS):
            store, moves, descriptions, prefix = current.store, list(current.moves), list(current.descriptions), ""
            if len(moves) >= self.max_moves:
                store, moves, descriptions, prefix = self._drop_one(moves, descriptions)
            drawn = random_move(store, self.rng, self.rules)
            if drawn is None:
                continue
            move, new_store, description = drawn
            if self._settle(new_store, attempt):
                return _Proposal(
                    tuple(moves) + (move,), tuple(descriptions) + (description,), new_store, prefix + description,
                )
        return None

    def random_walk(self, steps: int) -> _Proposal | None:
        """The baseline plus `steps` random moves."""
        for attempt in range(_PROPOSAL_ATTEMPTS):
            store = self.baseline.store
            moves: list[Move] = []
            descriptions: list[str] = []
            for _ in range(steps):
                drawn = random_move(store, self.rng, self.rules)
                if drawn is None:
                    break
                move, store, description = drawn
                moves.append(move)
                descriptions.append(description)
            if moves and self._settle(store, attempt):
                return _Proposal(tuple(moves), tuple(descriptions), store, "; ".join(descriptions))
        return None

    def crossover(self, a: _Candidate, b: _Candidate) -> _Proposal | None:
        """Replay a's moves then b's (trimmed to max_moves at random), mutated with one random move."""
        for attempt in range(_PROPOSAL_ATTEMPTS):
            combined = list(a.moves) + [m for m in b.moves if m not in a.moves]
            if len(combined) > self.max_moves:
                keep = sorted(self.rng.sample(range(len(combined)), self.max_moves))
                combined = [combined[i] for i in keep]
            store, moves, descriptions = replay(self.baseline.store, combined, self.rules)
            label = f"crossover #{a.iteration} x #{b.iteration}"
            if self.rng.random() < _MUTATION_RATE or store_fingerprint(store) in self._seen:
                prefix = ""
                if len(moves) >= self.max_moves:
                    store, moves, descriptions, prefix = self._drop_one(moves, descriptions)
                drawn = random_move(store, self.rng, self.rules)
                if drawn is not None:
                    move, store, description = drawn
                    moves.append(move)
                    descriptions.append(description)
                    label += f"; mutation: {prefix}{description}"
            if moves and self._settle(store, attempt):
                return _Proposal(tuple(moves), tuple(descriptions), store, label)
        return None

    def tournament(self, population: list[_Candidate]) -> _Candidate:
        a, b = self.rng.choice(population), self.rng.choice(population)
        return min(a, b, key=self.fitter)


async def _anneal(search: _Search) -> None:
    current = search.baseline
    scale = abs(search.baseline.score) or 1.0
    t_start, t_end = _T_START * scale, _T_END * scale
    steps = max(1, search.spec.budget - 1)
    while search.remaining > 0:
        temperature = t_start * (t_end / t_start) ** (search.evaluations / steps)
        proposal = search.neighbor(current)
        if proposal is None:
            search.notes.append("Search stopped early: no further feasible move was found.")
            return
        candidate = await search.evaluate(proposal)
        delta = search.gain(candidate.score) - search.gain(current.score)
        accepted = delta >= 0 or search.rng.random() < math.exp(delta / temperature)
        if accepted:
            current = candidate
        search.record(candidate, accepted, proposal.label)


async def _hill_climb(search: _Search) -> None:
    current = search.baseline
    patience = max(4, search.spec.budget // 6)
    stall = 0
    while search.remaining > 0:
        restart = stall >= patience
        proposal = search.random_walk(min(_RESTART_STEPS, search.max_moves)) if restart else search.neighbor(current)
        if proposal is None:
            search.notes.append("Search stopped early: no further feasible move was found.")
            return
        candidate = await search.evaluate(proposal)
        accepted = restart or search.gain(candidate.score) > search.gain(current.score)
        if accepted:
            current = candidate
            stall = 0
        else:
            stall += 1
        search.record(candidate, accepted, ("restart: " if restart else "") + proposal.label)


async def _genetic(search: _Search) -> None:
    """Steady-state GA: one child per evaluation replaces the weakest member if it is fitter."""
    size = max(4, min(_MAX_POPULATION, search.spec.budget // 5))
    population = [search.baseline]
    while len(population) < size and search.remaining > 0:
        proposal = search.random_walk(search.rng.randint(1, min(_SEED_STEPS, search.max_moves)))
        if proposal is None:
            break
        candidate = await search.evaluate(proposal)
        population.append(candidate)
        search.record(candidate, True, "seed: " + proposal.label)
    while search.remaining > 0 and len(population) >= 2:
        proposal = search.crossover(search.tournament(population), search.tournament(population))
        if proposal is None:
            break
        child = await search.evaluate(proposal)
        population = sorted([*population, child], key=search.fitter)[:size]
        search.record(child, any(c is child for c in population), proposal.label)
    if search.remaining > 0:
        search.notes.append("Search stopped early: no further feasible move was found.")


def _prune(baseline: Store, best: _Candidate, rules: MoveRules) -> tuple[tuple[Move, ...], tuple[str, ...], Store]:
    """Drop moves whose removal leaves the best layout unchanged (e.g. a swap and its undo)."""
    target = store_fingerprint(best.store)
    moves = list(best.moves)
    i = 0
    while i < len(moves):
        trial = moves[:i] + moves[i + 1:]
        store, applied, _ = replay(baseline, trial, rules)
        if len(applied) == len(trial) and store_fingerprint(store) == target:
            moves = trial
        else:
            i += 1
    store, applied, descriptions = replay(baseline, moves, rules)
    if store_fingerprint(store) != target:
        return best.moves, best.descriptions, best.store
    return tuple(applied), tuple(descriptions), store


def _relative(spec: OptimizeSpec, baseline: float, best: float) -> float:
    if baseline == 0:
        return 0.0
    diff = best - baseline if spec.objective.maximize else baseline - best
    return round(diff / abs(baseline), 6)


async def optimize(
    store: Store,
    spec: OptimizeSpec,
    evaluator: LayoutEvaluator,
    *,
    validation_personas: list[Persona] | None = None,
    on_progress: ProgressCallback | None = None,
    keep_top: int = 0,
) -> OptimizeResult:
    """Search for a better layout than `store` under `spec`. Never mutates `store`.

    `keep_top` > 0 also returns the best distinct non-baseline layouts of the whole trajectory
    (by score, redundant moves pruned) in `result.top_candidates`, e.g. for a VLM judge.

    `validation_personas` (default: the evaluator's personas) are simulated on baseline and best
    with the next replicate, i.e. fresh shopper randomness, and compared pairwise; that guards
    against picking a layout that only won on the search panel's particular draws. Validation
    is skipped when `spec.validation_size` is 0 or the baseline is kept.
    """
    if evaluator.objective != spec.objective:
        raise ValueError(f"evaluator objective {evaluator.objective} does not match spec objective {spec.objective}")
    errors = [i for i in validate(store) if i.severity == "error"]
    if errors:
        raise ValueError("Baseline layout is infeasible: " + "; ".join(f"[{i.code}] {i.message}" for i in errors))

    started = time.perf_counter()
    rules = MoveRules.for_baseline(store, spec.scope, spec.constraints)
    score, summary = await evaluator.evaluate(store)
    baseline = _Candidate((), (), store, score, summary, 0)
    search = _Search(baseline, spec, evaluator, rules, on_progress)
    logger.info(
        f"[optimize] {spec.algorithm} over {spec.scope} for {spec.objective}: baseline {score},"
        f" budget {spec.budget}, {len(evaluator.personas)} customers per candidate"
    )
    match spec.algorithm:
        case "anneal":
            await _anneal(search)
        case "hill_climb":
            await _hill_climb(search)
        case "genetic":
            await _genetic(search)

    notes = search.notes
    best = search.best
    moves, descriptions, best_store = best.moves, best.descriptions, best.store
    relative = _relative(spec, baseline.score, best.score)
    if best is baseline:
        notes.append("No candidate beat the baseline on the search customers; the baseline is returned.")
    elif relative < spec.constraints.min_improvement:
        notes.append(
            f"The best candidate improved the objective by {relative:.2%}, below min_improvement"
            f" {spec.constraints.min_improvement:.2%}; the baseline is returned."
        )
        best, relative = baseline, 0.0
        moves, descriptions, best_store = (), (), store
    else:
        moves, descriptions, best_store = _prune(store, best, rules)

    report: ComparisonReport | None = None
    metric_name = COMPARISON_METRICS[spec.objective]
    validation_relative: float | None = None
    validation_prob: float | None = None
    if best is not baseline and spec.validation_size > 0:
        personas = validation_personas if validation_personas else evaluator.personas
        replicate = evaluator.config.replicate + 1
        results_a = await evaluator.evaluate_customers(store, personas, replicate=replicate)
        results_b = await evaluator.evaluate_customers(best_store, personas, replicate=replicate)
        report = compare_runs(results_a, results_b, run_a="baseline", run_b="optimized", seed=spec.seed)
        metric = next((m for m in report.metrics if m.metric == metric_name), None)
        if metric is not None:
            maximize = spec.objective.maximize
            validation_relative = round(metric.rel_diff if maximize else -metric.rel_diff, 6)
            validation_prob = round(metric.prob_b_greater if maximize else 1.0 - metric.prob_b_greater, 4)
            excludes_zero = metric.ci_low > 0 if maximize else metric.ci_high < 0
            if validation_relative <= 0:
                notes.append(
                    f"On {report.paired_customers} validation customers with fresh randomness the best layout was"
                    f" not better than the baseline ({metric_name}: {validation_relative:+.2%} improvement);"
                    " the search gain is likely noise."
                )
            elif excludes_zero:
                notes.append(
                    f"Validation on {report.paired_customers} customers with fresh randomness confirms the gain:"
                    f" {metric_name} {validation_relative:+.2%} better than the baseline, 95% interval excludes zero."
                )
            else:
                notes.append(
                    f"Validation on {report.paired_customers} customers: {metric_name} {validation_relative:+.2%}"
                    " better than the baseline, but the 95% interval includes zero; validate with more customers"
                    " before acting on it."
                )

    top: list[LayoutCandidate] = []
    if keep_top > 0:
        baseline_key = store_fingerprint(store)
        ranked = sorted((c for k, c in search.scored.items() if k != baseline_key), key=search.fitter)
        for candidate in ranked[:keep_top]:
            _, pruned_descriptions, pruned_store = _prune(store, candidate, rules)
            top.append(LayoutCandidate(iteration=candidate.iteration, score=candidate.score,
                                       moves=list(pruned_descriptions), store=pruned_store.model_copy(deep=True)))

    seconds = round(time.perf_counter() - started, 3)
    logger.info(
        f"[optimize] done in {seconds}s: {search.evaluations} evaluations, best {best.score}"
        f" ({relative:+.2%}), {len(moves)} moves"
    )
    return OptimizeResult(
        spec=spec,
        baseline_score=baseline.score,
        best_score=best.score,
        relative_improvement=relative,
        best_store=best_store.model_copy(deep=True),
        applied_moves=list(descriptions),
        history=search.history,
        evaluations=search.evaluations,
        cache_hits=search.cache_hits,
        seconds=seconds,
        baseline_summary=baseline.summary,
        best_summary=best.summary,
        validation=report,
        validation_metric=metric_name if report is not None else "",
        validation_relative_improvement=validation_relative,
        validation_prob_better=validation_prob,
        notes=notes,
        top_candidates=top,
    )
