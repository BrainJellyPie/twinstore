import threading
from collections import OrderedDict

from pathfinding.core.diagonal_movement import DiagonalMovement  # type: ignore[reportMissingTypeStubs]
from pathfinding.core.grid import Grid  # type: ignore[reportMissingTypeStubs]
from pathfinding.finder.a_star import AStarFinder  # type: ignore[reportMissingTypeStubs]

from store_emulator.domain.types import Position

_CACHE_SIZE = 200_000

type _GridKey = tuple[tuple[bool, ...], ...]


class AStarPathFinder:
    """A* on the walkable grid, memoized per (grid, start, end).

    Every customer walks between the same few tiles (entrance, rack faces, counter,
    exit), so the same queries repeat thousands of times per run. Results depend
    only on the grid contents, which are part of the cache key, so a changed layout
    can never hit a stale entry. Returned lists are copies.
    """

    def __init__(self) -> None:
        self._finder = AStarFinder(  # type: ignore[reportUnknownMemberType]
            diagonal_movement=DiagonalMovement.never,
        )
        self._cache: OrderedDict[tuple[_GridKey, Position, Position], tuple[Position, ...]] = OrderedDict()
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
                return list(hit)
        matrix = [[int(cell) for cell in row] for row in walkable_grid]
        grid = Grid(matrix=matrix)  # type: ignore[reportUnknownMemberType]
        start_node = grid.node(start[0], start[1])  # type: ignore[reportUnknownMemberType]
        end_node = grid.node(end[0], end[1])  # type: ignore[reportUnknownMemberType]
        path_nodes, _ = self._finder.find_path(start_node, end_node, grid)  # type: ignore[reportUnknownMemberType]
        path: tuple[Position, ...] = tuple((node.x, node.y) for node in path_nodes)  # type: ignore[reportUnknownMemberType]
        with self._lock:
            self._cache[key] = path
            if len(self._cache) > _CACHE_SIZE:
                self._cache.popitem(last=False)
        return list(path)
