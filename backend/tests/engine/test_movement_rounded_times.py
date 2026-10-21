import pytest

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.movement import TrackPoint
from store_emulator.domain.types import Action
from store_emulator.engine.analysis.movement import movement_report


@pytest.mark.parametrize("second_timestamp", [0, 1])
def test_rounded_timestamps_preserve_every_visited_cell(second_timestamp: int) -> None:
    customer = CustomerResult(
        persona_id="p", day=1, arrival_time="09:00:00",
        timeline=[
            TimelineEvent(elapsed_sec=0, x=0, y=0, action=Action.ENTER),
            TimelineEvent(elapsed_sec=0, x=1, y=0, action=Action.MOVE),
            TimelineEvent(elapsed_sec=0, x=1, y=0, action=Action.BROWSE),
            TimelineEvent(elapsed_sec=second_timestamp, x=2, y=0, action=Action.EXIT),
        ],
    )
    observed = [TrackPoint(track_id="a", timestamp_sec=x, x=x, y=0) for x in range(3)]

    report = movement_report(observed, [customer, customer], (3, 1))

    assert report.simulated.visitors == [[2, 2, 2]]
    assert report.visitation_similarity == 1
    assert report.simulated.occupancy_seconds == [[0, 2 * second_timestamp, 0]]
    assert all(gap.difference == 0 for gap in report.largest_gaps)
