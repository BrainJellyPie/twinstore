import threading
from collections import OrderedDict
from sys import getsizeof

from pathfinding.core.diagonal_movement import DiagonalMovement  # type: ignore[reportMissingTypeStubs]
from pathfinding.core.grid import Grid  # type: ignore[reportMissingTypeStubs]
from pathfinding.finder.a_star import AStarFinder  # type: ignore[reportMissingTypeStubs]

from store_emulator.domain.types import Position

_CACHE_SIZE = 200_000
_CACHE_BYTES = 64 * 1024 * 1024

type _GridKey = tuple[tuple[bool, ...], ...]


class AStarPathFinder:
    """A* on the walkable grid, memoized per (grid, start, end).

    Every customer walks between the same few tiles (entrance, rack faces, counter,
    exit), so the same queries repeat thousands of times per run. Results depend
    only on the grid contents, which are part of the cache key, so a changed layout
    can never hit a stale entry. Returned lists are copies.
    """

    def __init__(self, *, diagonal: bool = False) -> None:
        # diagonal: 8-connected steps that never cut a corner (both side tiles must be walkable),
        # so walks between stops are close to straight lines instead of staircases.
        self.diagonal = diagonal
        self._finder = AStarFinder(  # type: ignore[reportUnknownMemberType]
            diagonal_movement=DiagonalMovement.only_when_no_obstacle if diagonal else DiagonalMovement.never,
        )
        self._cache: OrderedDict[tuple[_GridKey, Position, Position], tuple[tuple[Position, ...], int]] = OrderedDict()
        self._cache_bytes = 0
        self._lock = threading.Lock()

    def find_path(
        self,
        walkable_grid: list[list[bool]],
        start: Position,
        end: Position,
    ) -> list[Position]:
        key = (tuple(tuple(row) for row in walkable_grid), start, end)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return list(hit[0])
        matrix = [[int(cell) for cell in row] for row in walkable_grid]
        grid = Grid(matrix=matrix)  # type: ignore[reportUnknownMemberType]
        start_node = grid.node(start[0], start[1])  # type: ignore[reportUnknownMemberType]
        end_node = grid.node(end[0], end[1])  # type: ignore[reportUnknownMemberType]
        path_nodes, _ = self._finder.find_path(start_node, end_node, grid)  # type: ignore[reportUnknownMemberType]
        path: tuple[Position, ...] = tuple((node.x, node.y) for node in path_nodes)  # type: ignore[reportUnknownMemberType]
        # Full-map keys dominate large layouts. Include tuple/container costs, plus conservative entry overhead.
        size = (getsizeof(key) + getsizeof(key[0]) + sum(getsizeof(row) for row in key[0])
                + getsizeof(start) + getsizeof(end) + getsizeof(path) + sum(getsizeof(step) for step in path) + 256)
        with self._lock:
            if size <= _CACHE_BYTES:
                previous = self._cache.pop(key, None)
                if previous is not None:  # another thread may have finished this same path meanwhile
                    self._cache_bytes -= previous[1]
                self._cache[key] = (path, size)
                self._cache_bytes += size
                while len(self._cache) > _CACHE_SIZE or self._cache_bytes > _CACHE_BYTES:
                    _, (_, removed_size) = self._cache.popitem(last=False)
                    self._cache_bytes -= removed_size
        return list(path)
