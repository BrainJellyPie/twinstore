"""Large maps and optimization candidates cannot retain unbounded full-map cache keys."""

import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from store_emulator.engine.routing import pathfinder


def retained_size(finder):
    seen = set()

    def size(value):
        if id(value) in seen:
            return 0
        seen.add(id(value))
        result = sys.getsizeof(value)
        if isinstance(value, dict):
            result += sum(size(k) + size(v) for k, v in value.items())
        elif isinstance(value, tuple):
            result += sum(size(item) for item in value)
        return result

    return size(finder._cache)


@pytest.mark.parametrize("shape", [(64, 64), (128, 2), (2, 128)])
@pytest.mark.parametrize("diagonal", [False, True])
def test_cache_eviction_bounds_retained_memory_without_changing_routes(monkeypatch, shape, diagonal):
    budget = 128 * 1024
    monkeypatch.setattr(pathfinder, "_CACHE_BYTES", budget, raising=False)
    finder = pathfinder.AStarPathFinder(diagonal=diagonal)
    width, height = shape
    grid = [[True] * width for _ in range(height)]
    routes = []
    for n in range(80):
        x, y = n % (width - 1), n // (width - 1)
        if y >= height:
            break
        route = finder.find_path(grid, (x, y), (x + 1, y))
        assert route == [(x, y), (x + 1, y)]
        routes.append(((x, y), (x + 1, y), route))
    # Include Python container overhead and allow a small allocator-sized margin.
    assert retained_size(finder) <= budget + 4096
    for start, end, expected in reversed(routes):
        assert finder.find_path(grid, start, end) == expected
    assert retained_size(finder) <= budget + 4096


def test_a_single_oversized_entry_is_not_retained_and_mutated_maps_are_not_stale(monkeypatch):
    monkeypatch.setattr(pathfinder, "_CACHE_BYTES", 128, raising=False)
    finder = pathfinder.AStarPathFinder()
    grid = [[True] * 4 for _ in range(3)]
    assert finder.find_path(grid, (0, 1), (3, 1)) == [(0, 1), (1, 1), (2, 1), (3, 1)]
    assert not finder._cache
    grid[1][1] = False
    route = finder.find_path(grid, (0, 1), (3, 1))
    assert route[0] == (0, 1) and route[-1] == (3, 1) and (1, 1) not in route
    assert not finder._cache


def test_concurrent_cache_inserts_and_returned_list_edits_preserve_the_bound(monkeypatch):
    budget = 32 * 1024
    monkeypatch.setattr(pathfinder, "_CACHE_BYTES", budget, raising=False)
    finder = pathfinder.AStarPathFinder()
    grid = [[True] * 20 for _ in range(20)]

    def find(n):
        start, end = (n % 19, n // 19), (n % 19 + 1, n // 19)
        result = finder.find_path(grid, start, end)
        assert result == [start, end]
        result.clear()
        assert finder.find_path(grid, start, end) == [start, end]

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(find, list(range(60)) * 2))
    assert retained_size(finder) <= budget + 4096
