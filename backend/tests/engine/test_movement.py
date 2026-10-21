import pytest

from store_emulator.application.movement import parse_tracks
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.movement import TrackPoint
from store_emulator.domain.types import Action
from store_emulator.engine.analysis.movement import aggregate_tracks, movement_report


def point(t: float, x: int = 0, y: int = 0, track: str = "anonymous") -> TrackPoint:
    return TrackPoint(track_id=track, x=x, y=y, timestamp_sec=t)


def test_visitors_and_occupancy_do_not_depend_on_frame_rate() -> None:
    sparse = [point(0), point(5), point(10, x=1), point(20, x=1)]
    dense = [*sparse, point(1), point(2), point(15, x=1)]
    a = aggregate_tracks(sparse, (2, 1), max_gap_seconds=30)
    b = aggregate_tracks(dense[::-1], (2, 1), max_gap_seconds=30)
    assert a.visitors == b.visitors == [[1, 1]]
    assert a.occupancy_seconds == b.occupancy_seconds == [[10, 10]]
    assert a.observed_seconds == 20


def test_duplicates_gaps_and_single_samples_are_accounted_for() -> None:
    samples = [point(0), point(0), point(60), point(61, x=1), point(5, x=1, track="second")]
    report = aggregate_tracks(samples, (2, 1), max_gap_seconds=30)
    assert report.duplicate_samples == 1 and report.single_point_tracks == 1
    assert report.excluded_gaps == 1 and report.excluded_seconds == 60
    assert report.observed_seconds == 1 and report.visitors == [[1, 2]]


def test_same_paths_match_and_axes_are_not_transposed() -> None:
    points = [point(0), point(5, x=1), point(15, x=1, y=1)]
    result = CustomerResult(persona_id="p", day=1, arrival_time="09:00:00", timeline=[
        TimelineEvent(elapsed_sec=int(p.timestamp_sec), x=p.x, y=p.y, action=Action.MOVE) for p in points
    ])
    report = movement_report(points, [result], (3, 2))
    assert report.visitation_similarity == 1 and report.occupancy_similarity == 1
    assert report.observed.visitors == [[1, 1, 0], [0, 1, 0]]
    assert report.observed.occupancy_seconds == [[5, 10, 0], [0, 0, 0]]
    assert all(g.difference == 0 for g in report.largest_gaps)
    assert "anonymous" not in report.model_dump_json()


def test_unavailable_time_or_simulation_has_no_similarity_score() -> None:
    report = movement_report([point(0)], [], (2, 2))
    assert report.visitation_similarity is None and report.occupancy_similarity is None
    assert report.largest_gaps == []


def test_simulated_long_stops_are_not_treated_as_tracking_loss() -> None:
    customer = CustomerResult(persona_id="p", day=1, arrival_time="09:00:00", timeline=[
        TimelineEvent(elapsed_sec=0, x=0, y=0, action=Action.ENTER),
        TimelineEvent(elapsed_sec=90, x=0, y=0, action=Action.EXIT),
    ])
    report = movement_report([point(0), point(90)], [customer], (1, 1))
    assert report.observed.excluded_seconds == 90 and report.simulated.observed_seconds == 90
    assert report.occupancy_similarity is None


@pytest.mark.parametrize("points", [[point(0), point(0, x=1)], [point(0, x=-1)], [point(0, x=2)]])
def test_conflicting_time_or_invalid_coordinates_are_rejected(points: list[TrackPoint]) -> None:
    with pytest.raises(ValueError):
        aggregate_tracks(points, (2, 1), max_gap_seconds=30)


@pytest.mark.parametrize("csv", [
    "track_id,x,y,timestamp_sec\na,0.5,0,1\n", "track_id,x,y,timestamp_sec\na,0,0,nan\n",
    "track_id,x,y,timestamp_sec\n,0,0,1\n", "track_id,x,y,timestamp_sec\na,0,0,-1\n",
    "track_id,x,y\na,0,0\n", "track_id,x,x,y,timestamp_sec\na,0,0,0,1\n",
])
def test_invalid_csv_is_actionable(csv: str) -> None:
    with pytest.raises(ValueError, match="CSV"):
        parse_tracks(csv.encode())


def test_utf8_bom_and_fractional_seconds_are_supported() -> None:
    assert parse_tracks("\ufefftrack_id,x,y,timestamp_sec\na,1,0,0.25\n".encode())[0] == point(0.25, x=1, track="a")
