"""Malformed track CSV must not silently change numeric evidence or expand sparse records."""

import csv
import io
from unittest.mock import Mock

import pytest

from store_emulator.application import movement


@pytest.mark.parametrize("row", ["t,1,2,0,10", "t,0,1,2,10", "t,0,0,1,250", "t,0,0,10,",
                               't,0,0,"10'])
def test_extra_fields_and_unterminated_quotes_cannot_change_track_measurements(row):
    with pytest.raises(ValueError, match="fields|quoting"):
        movement.parse_tracks(("track_id,x,y,timestamp_sec\n" + row + "\n").encode())


def sparse_tracks():
    header = ["track_id", "x", "y", "timestamp_sec"] + [f"column_{i}" for i in range(1996)]
    return (",".join(header) + "\n" + "t,0,0,1\n" * 1001).encode()


def test_sparse_track_records_are_bounded_before_point_parsing(monkeypatch):
    data = sparse_tracks()
    assert len(data) < 40_000
    point = Mock(side_effect=AssertionError("Do not materialize padded dictionaries"))
    monkeypatch.setattr(movement.TrackPoint, "model_validate", point)
    with pytest.raises(ValueError, match="cells"):
        movement.parse_tracks(data)
    point.assert_not_called()


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("note", ["optional, note", 'multiple\nlines;\t"quoted"', "x" * 200_000],
                         ids=["comma", "multiline", "long"])
def test_utf8_bom_and_quoted_auxiliary_columns_keep_numeric_values(newline, note):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator=newline)
    writer.writerow(["track_id", "x", "y", "timestamp_sec", "note"])
    writer.writerow(["0001", 0, 1, 0.5, note])
    writer.writerow(["0001", 1, 2, 10.75])  # Missing optional note is allowed.
    points = movement.parse_tracks(stream.getvalue().encode("utf-8-sig"))
    assert [(p.track_id, p.x, p.y, p.timestamp_sec) for p in points] == [
        ("0001", 0, 1, 0.5), ("0001", 1, 2, 10.75)]
