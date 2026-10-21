"""Compare anonymous, grid-aligned tracks with simulated customer movement.

Count a visitor once per cell, independently of sampling frequency. Assign each
interval to its starting cell (zero-order hold); never extrapolate after the last
sample or across a long tracking gap. Simulated timelines are complete, so their
long stops are retained. No interpolation invents passages through racks.
"""

from collections import defaultdict

import numpy as np

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.movement import MovementGap, MovementReport, MovementSummary, TrackPoint
from store_emulator.domain.types import Position
from store_emulator.engine.analysis.fidelity import js_divergence


def aggregate_tracks(points: list[TrackPoint], grid_size: Position, *, max_gap_seconds: float | None,
                     allow_same_time_moves: bool = False) -> MovementSummary:
    width, height = grid_size
    visitors = [[0] * width for _ in range(height)]
    occupancy = [[0.0] * width for _ in range(height)]
    tracks: dict[str, dict[float, TrackPoint]] = defaultdict(dict)
    visited: dict[str, set[Position]] = defaultdict(set)
    duplicates = 0
    for point in points:
        if not (0 <= point.x < width and 0 <= point.y < height):
            raise ValueError(f"Track coordinates must fit the {width} × {height} store grid.")
        previous = tracks[point.track_id].get(point.timestamp_sec)
        if previous is not None:
            if (previous.x, previous.y) != (point.x, point.y):
                if not allow_same_time_moves:
                    raise ValueError("A track has different positions at the same timestamp; correct the source data.")
            else:
                duplicates += 1
        tracks[point.track_id][point.timestamp_sec] = point
        visited[point.track_id].add((point.x, point.y))
    gaps, excluded, singles = 0, 0.0, 0
    for track_id, by_time in tracks.items():
        ordered = sorted(by_time.values(), key=lambda p: p.timestamp_sec)
        if len(ordered) == 1:
            singles += 1
        for x, y in visited[track_id]:
            visitors[y][x] += 1
        for first, second in zip(ordered, ordered[1:]):
            duration = second.timestamp_sec - first.timestamp_sec
            if max_gap_seconds is not None and duration > max_gap_seconds:
                gaps += 1
                excluded += duration
                continue
            occupancy[first.y][first.x] += duration
    return MovementSummary(tracks=len(tracks), samples=len(points), duplicate_samples=duplicates,
                           single_point_tracks=singles, excluded_gaps=gaps, excluded_seconds=excluded,
                           observed_seconds=sum(map(sum, occupancy)), visitors=visitors, occupancy_seconds=occupancy)


def movement_report(points: list[TrackPoint], results: list[CustomerResult], grid_size: Position,
                    *, max_gap_seconds: float = 30) -> MovementReport:
    if not points:
        raise ValueError("The track file contains no samples.")
    if not 0 < max_gap_seconds <= 300:
        raise ValueError("Maximum tracking gap must be greater than zero and at most 300 seconds.")
    observed = aggregate_tracks(points, grid_size, max_gap_seconds=max_gap_seconds)
    simulated_points: list[TrackPoint] = []
    for index, customer in enumerate(results):
        for event in customer.timeline:
            simulated_points.append(TrackPoint(track_id=str(index), x=event.x, y=event.y, timestamp_sec=event.elapsed_sec))
    # Rounded timeline times can share a timestamp. Count every visited cell,
    # while the final position at that time supplies the next occupancy interval.
    simulated = aggregate_tracks(simulated_points, grid_size, max_gap_seconds=None, allow_same_time_moves=True)

    def similarity(a: list[list[int]] | list[list[float]], b: list[list[int]] | list[list[float]]) -> float | None:
        av, bv = np.asarray(a, dtype=float).ravel(), np.asarray(b, dtype=float).ravel()
        if av.sum() <= 0 or bv.sum() <= 0:
            return None
        return round(1 - js_divergence(av, bv), 6)

    width, height = grid_size
    gaps: list[MovementGap] = []
    if simulated.tracks:
        for y in range(height):
            for x in range(width):
                real = observed.visitors[y][x] / observed.tracks
                sim = simulated.visitors[y][x] / simulated.tracks
                if real or sim:
                    gaps.append(MovementGap(x=x, y=y, observed_visit_rate=real, simulated_visit_rate=sim, difference=real - sim))
    gaps.sort(key=lambda g: (-abs(g.difference), g.y, g.x))
    notes = [
        "Coordinates are zero-based store grid cells: x increases right, y increases down. Matrices are [y][x].",
        "Visitors count each track once per cell. Occupancy assigns each sample interval to its starting cell; the final sample adds no time.",
        "Compare the same layout and comparable operating periods. Track fragmentation and camera coverage can bias these metrics.",
        "Similarity is 1 minus Jensen–Shannon divergence of normalized maps; it does not establish forecasting accuracy or a causal effect.",
    ]
    if observed.excluded_gaps:
        notes.append(f"Excluded {observed.excluded_gaps} tracking gaps ({observed.excluded_seconds:g} seconds). Occupancy comparisons cover only retained intervals.")
    if observed.single_point_tracks:
        notes.append(f"{observed.single_point_tracks} tracks have only one distinct timestamp and contribute no occupancy time.")
    if not simulated.tracks:
        notes.append("This run has no simulated movement; comparison metrics are unavailable.")
    return MovementReport(grid_size=grid_size, observed=observed, simulated=simulated,
                          visitation_similarity=similarity(observed.visitors, simulated.visitors),
                          occupancy_similarity=similarity(observed.occupancy_seconds, simulated.occupancy_seconds),
                          largest_gaps=gaps[:10], max_gap_seconds=max_gap_seconds, notes=notes)
