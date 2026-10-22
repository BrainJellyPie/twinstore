import asyncio
import json
import random
from pathlib import Path

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.optimize import (
    OptimizeConstraints,
    OptimizeObjective,
    OptimizeResult,
    OptimizeScope,
    OptimizeSpec,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, RackType
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.optimize.evaluate import (
    LayoutEvaluator,
    select_personas,
    store_fingerprint,
)
from store_emulator.engine.optimize.moves import (
    Move,
    MoveRules,
    RelocateRack,
    SlotRef,
    SwapLevels,
    SwapRacks,
    SwapSlots,
    apply_move,
    blocked_skus,
    on_border,
    random_move,
    replay,
)
from store_emulator.engine.optimize.search import optimize
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.validation import validate

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"

# Sample store racks (8×6 grid): fridges on the north and south walls, shelves inside.
DRINK_1 = "r_b5cf7836"      # fridge (2, 0), stocked face S
ICE_CREAM_1 = "r_4f65c40d"  # fridge (2, 5), stocked face N
SNACKS_1 = "r_a3f365d5"     # shelf (3, 2), faces N + S
SNACKS_2 = "r_2c97802a"     # shelf (4, 2), faces N + S
DRINK_3 = "r_5ad00af0"      # shelf (6, 0), face S
FOODS_1 = "r_21861767"      # shelf (6, 4), faces E + W


@pytest.fixture(scope="module")
def store() -> Store:
    return Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))


@pytest.fixture(scope="module")
def personas() -> list[Persona]:
    return [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]


@pytest.fixture(scope="module")
def pathfinder() -> AStarPathFinder:
    return AStarPathFinder()


def _errors(store: Store) -> list[str]:
    return [i.code for i in validate(store) if i.severity == "error"]


def _rack(store: Store, rack_id: str) -> Rack:
    return next(r for r in store.racks if r.id == rack_id)


def _rules(store: Store, scope: OptimizeScope, **constraints: object) -> MoveRules:
    return MoveRules.for_baseline(store, scope, OptimizeConstraints.model_validate(constraints))


def _chain(store: Store, rules: MoveRules, steps: int, seed: int) -> list[Store]:
    rng = random.Random(seed)
    stores = [store]
    for _ in range(steps):
        drawn = random_move(stores[-1], rng, rules)
        assert drawn is not None
        stores.append(drawn[1])
    return stores


def _evaluator(
    personas: list[Persona], pathfinder: AStarPathFinder, n: int,
    objective: OptimizeObjective = OptimizeObjective.REVENUE_PER_VISITOR,
) -> LayoutEvaluator:
    return LayoutEvaluator(
        SimulationConfig(seed=5), select_personas(personas, n, seed=0),
        sample_cue, BEHAVIOR_PATTERNS, pathfinder, objective,
    )


def _run(
    store: Store, spec: OptimizeSpec, personas: list[Persona], pathfinder: AStarPathFinder,
    progress: list[tuple[int, int, float]] | None = None,
) -> OptimizeResult:
    evaluator = _evaluator(personas, pathfinder, spec.eval_customers, spec.objective)

    def callback(done: int, budget: int, best: float) -> None:
        if progress is not None:
            progress.append((done, budget, best))

    return asyncio.run(optimize(store, spec, evaluator, on_progress=callback))


# ---------------------------------------------------------------------------------------------
# Moves
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("scope", list(OptimizeScope))
def test_random_moves_return_new_valid_stores_and_never_mutate_the_input(store: Store, scope: OptimizeScope):
    rules = _rules(store, scope)
    assert blocked_skus(store) == frozenset()
    rng = random.Random(1)
    current = store
    for _ in range(30):
        before = current.model_dump_json()
        drawn = random_move(current, rng, rules)
        assert drawn is not None
        _, new, description = drawn
        assert new is not current and description
        assert current.model_dump_json() == before
        assert _errors(new) == []
        assert blocked_skus(new) == frozenset()
        assert store_fingerprint(new) != store_fingerprint(current)
        current = new


def test_replay_reproduces_a_chain_of_moves(store: Store):
    rules = _rules(store, OptimizeScope.BOTH)
    rng = random.Random(4)
    current, moves = store, list[Move]()
    for _ in range(15):
        drawn = random_move(current, rng, rules)
        assert drawn is not None
        moves.append(drawn[0])
        current = drawn[1]
    replayed, applied, descriptions = replay(store, moves, rules)
    assert applied == moves and len(descriptions) == len(moves)
    assert store_fingerprint(replayed) == store_fingerprint(current)


def test_locked_racks_never_change(store: Store):
    locked = [DRINK_1, SNACKS_1, DRINK_3, ICE_CREAM_1]
    rules = _rules(store, OptimizeScope.BOTH, lock_rack_ids=locked)
    for moved in _chain(store, rules, 60, seed=2)[1:]:
        for rack_id in locked:
            assert _rack(moved, rack_id).model_dump() == _rack(store, rack_id).model_dump()


def test_fixed_racks_never_move(store: Store):
    fixed = {r.id: r.position for r in store.racks if r.type in (RackType.ENTRANCE, RackType.EXIT, RackType.COUNTER)}
    rules = _rules(store, OptimizeScope.PLACEMENT)
    for moved in _chain(store, rules, 60, seed=3)[1:]:
        assert {r.id: r.position for r in moved.racks if r.id in fixed} == fixed


def test_fridges_stay_on_walls(store: Store):
    rules = _rules(store, OptimizeScope.PLACEMENT, keep_fridges_on_walls=True)
    for moved in _chain(store, rules, 60, seed=5)[1:]:
        for rack in moved.racks:
            if rack.type == RackType.FRIDGE:
                assert on_border(rack.position, moved.grid_size)

    w, h = store.grid_size
    interior = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1) if store.rack_at(x, y) is None]
    assert all(apply_move(store, RelocateRack(DRINK_1, tile), rules) is None for tile in interior)
    free_rules = _rules(store, OptimizeScope.PLACEMENT, keep_fridges_on_walls=False)
    assert any(apply_move(store, RelocateRack(DRINK_1, tile), free_rules) is not None for tile in interior)


def test_moves_never_strand_products(store: Store):
    rules = _rules(store, OptimizeScope.PLACEMENT)
    # A shelf parked at (3, 1) would wall off the stocked N face of 'Snacks 1' at (3, 2).
    assert apply_move(store, RelocateRack(FOODS_1, (3, 1)), rules) is None
    assert apply_move(store, RelocateRack(FOODS_1, (1, 4)), rules) is not None


def test_moved_racks_turn_to_face_the_floor(store: Store):
    rules = _rules(store, OptimizeScope.PLACEMENT)
    result = apply_move(store, SwapRacks(DRINK_1, ICE_CREAM_1), rules)
    assert result is not None
    moved, description = result
    drink, ice = _rack(moved, DRINK_1), _rack(moved, ICE_CREAM_1)
    assert drink.position == (2, 5) and ice.position == (2, 0)
    assert {s.face for s in drink.slots} == {Face.N} and {s.face for s in ice.slots} == {Face.S}
    assert drink.rotation == 180 and ice.rotation == 180
    assert "Swap rack positions" in description
    assert _rack(store, DRINK_1).position == (2, 0)  # input untouched


def test_planogram_moves(store: Store):
    rules = _rules(store, OptimizeScope.PLANOGRAM)
    result = apply_move(store, SwapLevels(SNACKS_1, 0, Face.N, 1, 3), rules)
    assert result is not None
    moved, description = result
    level = {s.level: s.items for s in _rack(store, SNACKS_1).slots if s.face == Face.N}
    moved_level = {s.level: s.items for s in _rack(moved, SNACKS_1).slots if s.face == Face.N}
    assert moved_level[3] == level[1] and moved_level[1] == level[3]
    assert "L3 (eye)" in description

    # Items stay within their category: snacks never land on the drinks shelf.
    snack_slot = SlotRef(SNACKS_1, 0, Face.N, 1)
    assert apply_move(store, SwapSlots(snack_slot, SlotRef(DRINK_3, 0, Face.S, 1)), rules) is None
    assert apply_move(store, SwapSlots(snack_slot, SlotRef(SNACKS_2, 0, Face.S, 3)), rules) is not None
    # Placement moves are out of scope for a planogram search.
    assert apply_move(store, SwapRacks(SNACKS_1, SNACKS_2), rules) is None


# ---------------------------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------------------------

def test_evaluator_is_deterministic_and_caches(store: Store, personas: list[Persona], pathfinder: AStarPathFinder):
    evaluator = _evaluator(personas, pathfinder, 100)
    score, summary = asyncio.run(evaluator.evaluate(store))
    again, _ = asyncio.run(evaluator.evaluate(store.model_copy(deep=True)))
    assert score == again == summary.revenue_per_visitor > 0
    assert evaluator.evaluations == 1 and evaluator.cache_hits == 1

    fresh, _ = asyncio.run(_evaluator(personas, pathfinder, 100).evaluate(store))
    assert fresh == score

    distance = _evaluator(personas, pathfinder, 100, OptimizeObjective.WALKING_DISTANCE)
    walked, walk_summary = asyncio.run(distance.evaluate(store))
    assert walked == walk_summary.avg_path_tiles > 0


# ---------------------------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------------------------

def test_anneal_respects_budget_and_never_returns_worse(store: Store, personas: list[Persona], pathfinder: AStarPathFinder):
    before = store.model_dump_json()
    spec = OptimizeSpec(
        objective=OptimizeObjective.REVENUE_PER_VISITOR, scope=OptimizeScope.PLANOGRAM, algorithm="anneal",
        budget=12, eval_customers=120, validation_customers=120, seed=1,
    )
    progress: list[tuple[int, int, float]] = []
    result = _run(store, spec, personas, pathfinder, progress)
    assert store.model_dump_json() == before
    assert result.evaluations == len(result.history) == 12
    assert [h.iteration for h in result.history] == list(range(1, 13))
    assert len(progress) == 12 and progress[-1] == (12, 12, result.history[-1].best_score)
    assert result.best_score >= result.baseline_score
    assert result.relative_improvement >= 0
    assert _errors(result.best_store) == []
    assert len(result.applied_moves) <= spec.constraints.max_moves
    if result.best_score > result.baseline_score:
        assert result.applied_moves
        assert result.validation is not None and result.validation.paired_customers == 120
        assert result.validation_metric == "spend" and result.validation_relative_improvement is not None
        assert store_fingerprint(result.best_store) != store_fingerprint(store)
        # The reported moves rebuild the reported layout.
        rescored, _ = asyncio.run(_evaluator(personas, pathfinder, 120).evaluate(result.best_store))
        assert rescored == result.best_score


def test_hill_climb_placement_minimizes_walking(store: Store, personas: list[Persona], pathfinder: AStarPathFinder):
    spec = OptimizeSpec(
        objective=OptimizeObjective.WALKING_DISTANCE, scope=OptimizeScope.PLACEMENT, algorithm="hill_climb",
        budget=8, eval_customers=100, validation_customers=100, seed=2,
    )
    result = _run(store, spec, personas, pathfinder)
    assert result.evaluations == len(result.history) == 8
    assert result.best_score <= result.baseline_score
    assert result.relative_improvement >= 0
    assert _errors(result.best_store) == []
    assert blocked_skus(result.best_store) == frozenset()
    assert all(on_border(r.position, store.grid_size) for r in result.best_store.racks if r.type == RackType.FRIDGE)


def test_genetic_is_deterministic(store: Store, personas: list[Persona], pathfinder: AStarPathFinder):
    spec = OptimizeSpec(
        scope=OptimizeScope.BOTH, algorithm="genetic", budget=10, eval_customers=80, validation_customers=0, seed=3,
    )
    first = _run(store, spec, personas, pathfinder)
    second = _run(store, spec, personas, pathfinder)
    assert first.evaluations == len(first.history) == 10
    assert [(h.score, h.move, h.accepted) for h in first.history] == [(h.score, h.move, h.accepted) for h in second.history]
    assert first.applied_moves == second.applied_moves
    assert first.best_score >= first.baseline_score
    assert first.validation is None
    assert _errors(first.best_store) == []


def test_min_improvement_keeps_the_baseline(store: Store, personas: list[Persona], pathfinder: AStarPathFinder):
    spec = OptimizeSpec(
        budget=4, eval_customers=60, seed=4, constraints=OptimizeConstraints(min_improvement=10.0),
    )
    result = _run(store, spec, personas, pathfinder)
    assert result.evaluations == 4
    assert result.best_score == result.baseline_score and result.relative_improvement == 0
    assert result.applied_moves == [] and result.validation is None
    assert store_fingerprint(result.best_store) == store_fingerprint(store)
    assert result.notes


def test_a_layout_every_shopper_failed_on_is_an_error_not_a_score_of_zero(store, personas, pathfinder, monkeypatch):
    evaluator = _evaluator(personas, pathfinder, 12)

    async def refuse(*args, **kwargs):
        raise RuntimeError("the vision model did not answer: 401 key turned down")

    monkeypatch.setattr(evaluator._engine, "decide_actions", refuse)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(RuntimeError, match=r"Every shopper failed \(12\), so nothing was simulated: .*401 key turned down"):
        asyncio.run(evaluator.evaluate(store))
    with pytest.raises(RuntimeError, match="Every shopper failed"):
        asyncio.run(evaluator.evaluate_customers(store, evaluator.personas))
    assert evaluator.evaluations == 0
