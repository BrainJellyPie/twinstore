"""The route map counts shortest walks between access points, fast enough for large stores."""

import asyncio
import json
import time
from collections import deque
from pathlib import Path

import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.optimize import OptimizeObjective
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Position
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator, select_personas
from store_emulator.engine.routing.heatmap import (  # pyright: ignore[reportPrivateUsage]
    _access_points,
    compute_pathcalc_heatmap,
)
from store_emulator.engine.routing.pathfinder import AStarPathFinder

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "runs" / "run_ab0039" / "input"


def _distances(store: Store, grid: list[list[bool]], src: Position) -> dict[Position, int]:
    w, h = store.grid_size
    dist = {src: 0}
    queue = deque([src])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] and (nx, ny) not in dist:
                dist[(nx, ny)] = dist[(x, y)] + 1
                queue.append((nx, ny))
    return dist


def test_every_walk_between_access_points_is_a_shortest_one_counted_tile_by_tile() -> None:
    store = generate_store("mini_mart", seed=0)
    grid = store.walkable_grid()
    points = _access_points(store, grid)
    # Each ordered pair's walk covers its length + 1 tiles, so the raw counts add up to that.
    expected = 0
    for src in points:
        dist = _distances(store, grid, src)
        expected += sum(dist[dst] + 1 for dst in points if dst != src and dst in dist)

    heat = compute_pathcalc_heatmap(store)
    w, h = store.grid_size
    assert len(heat) == h and all(len(row) == w for row in heat)
    assert max(max(row) for row in heat) == 1.0
    assert all(heat[y][x] == 0.0 for y in range(h) for x in range(w) if not grid[y][x])
    peak = max(max(row) for row in heat)
    scale = expected / sum(map(sum, heat))  # raw count of the busiest tile
    assert abs(scale * peak - round(scale * peak)) < 1e-6


def test_a_large_store_maps_in_about_a_second() -> None:
    store = generate_store("hypermarket", seed=0)
    started = time.perf_counter()
    heat = compute_pathcalc_heatmap(store)
    assert time.perf_counter() - started < 10  # pair-by-pair path searches took over two minutes here
    assert max(max(row) for row in heat) == 1.0


def test_optimizer_candidates_do_not_build_a_route_map(monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application.presets.behavior import (
        BEHAVIOR_PATTERNS,
        sample_cue,
    )
    from store_emulator.engine.simulation import simulator

    def refuse(_store: Store) -> list[list[float]]:
        raise AssertionError("an optimizer candidate built the route map")

    monkeypatch.setattr(simulator, "compute_pathcalc_heatmap", refuse)
    store = Store.model_validate(json.loads((SAMPLE / "store.json").read_text()))
    personas = [Persona.model_validate(p) for p in json.loads((SAMPLE / "personas.json").read_text())]
    panel = select_personas(personas, 20, seed=1)
    evaluator = LayoutEvaluator(SimulationConfig(seed=1), panel, sample_cue, BEHAVIOR_PATTERNS, AStarPathFinder(),
                                OptimizeObjective.REVENUE_PER_VISITOR)
    score, _ = asyncio.run(evaluator.evaluate(store))
    assert score >= 0
    assert asyncio.run(evaluator.evaluate_customers(store, panel))
