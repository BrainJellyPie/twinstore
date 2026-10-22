from collections import deque

from store_emulator.domain.store import Store
from store_emulator.domain.types import Position

_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))  # 4-connected, like the A* the shoppers walk with


def _access_points(store: Store, grid: list[list[bool]]) -> list[Position]:
    access_points: set[Position] = set()
    for entrance in store.entrances:
        access_points.update(entrance.occupied_positions)
    for ex in store.exits:
        access_points.update(ex.occupied_positions)
    for f in store.product_racks:
        access_points |= f.access_tiles(store.grid_size)
    for counter in store.counters:
        access_points |= counter.service_access_tiles(store.grid_size)
    return sorted(p for p in access_points if grid[p[1]][p[0]])


def compute_pathcalc_heatmap(store: Store) -> list[list[float]]:
    """How often each walkable tile lies on a shortest walk between two access points (entrances,
    exits, rack faces, counters), scaled so the busiest tile is 1.

    One breadth-first search per access point: every other access point's shortest walk from it
    follows the search tree back to the root, so a tile's count is the number of access points in
    its subtree. That is linear in the grid per point, where a path search per pair of points took
    minutes on a large store (hundreds of points, tens of thousands of pairs).
    """
    grid = store.walkable_grid()
    w, h = store.grid_size
    points = _access_points(store, grid)
    is_point = [False] * (w * h)
    for x, y in points:
        is_point[y * w + x] = True

    counts = [0] * (w * h)
    for sx, sy in points:
        root = sy * w + sx
        order = [root]          # tiles in the order the search reached them
        parent = {root: -1}
        queue = deque([(sx, sy)])
        while queue:
            x, y = queue.popleft()
            here = y * w + x
            for dx, dy in _STEPS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and grid[ny][nx]:
                    cell = ny * w + nx
                    if cell not in parent:
                        parent[cell] = here
                        order.append(cell)
                        queue.append((nx, ny))
        below: dict[int, int] = {}
        for cell in reversed(order):  # children before their parents
            walks = below.get(cell, 0) + (1 if is_point[cell] and cell != root else 0)
            if walks:
                counts[cell] += walks
                up = parent[cell]
                if up >= 0:
                    below[up] = below.get(up, 0) + walks

    max_count = max(counts, default=0) or 1
    return [[counts[y * w + x] / max_count for x in range(w)] for y in range(h)]
