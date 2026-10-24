"""Customer traffic must not invent calendar components or midnight visits."""

from collections import Counter
from datetime import datetime

import pandas as pd
import pytest

from store_emulator.application import supplemental
from tests.engine.test_supplemental_pos_parsing import export


@pytest.mark.parametrize("value", [
    "Oct 19 09:00", "2026-10 09:00", "2026 09:00", "19 09:00", "09h30",
    "Oct 19", "2026-10", "2026", "09:00", "9 AM", "2026-02-29 09:00",
    "2026-10 Mon 09:00", "2026-10 Friday 09:00", "2026-10 Sunday 09:00",
])
def test_incomplete_calendar_never_creates_visit_weekdays(value):
    frame = pd.DataFrame({"timestamp": [value] * 5, "receipt_id": range(5)})
    assert supplemental._visit_times_from_frame(frame) == []


@pytest.mark.parametrize("value", ["Oct 19", "2026-10", "2026", "19"])
def test_split_clock_does_not_complete_a_partial_date(value):
    frame = pd.DataFrame({"date": [value] * 5, "time": ["09:00"] * 5, "receipt_id": range(5)})
    assert supplemental._visit_times_from_frame(frame) == []


@pytest.mark.parametrize("value", [
    "2026-10-19T00", "20261019T000000", "20261019000000", "19 Oct 2026 12 AM",
    "10/19/26 00:00", "2026-10-19T00:00:00+09:00", "2026-10-19T00:00:00-04:00",
])
def test_explicit_midnight_is_independent_of_text_format(value):
    frame = pd.DataFrame({"timestamp": [value] * 5, "receipt_id": range(5)})
    assert supplemental._visit_times_from_frame(frame) == [(1, 0)] * 5


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("invalid", ["Oct 20 18:00", "2026-10 18:00", "09h30", "2026-10-20", 123456])
def test_incomplete_rows_cannot_contaminate_an_otherwise_usable_export(suffix, invalid):
    frame = pd.DataFrame({"timestamp": ["2026-10-19 09:00"] * 200 + [invalid] * 50,
                          "receipt_id": range(250)})
    profile = supplemental.traffic_from_supplemental(export(frame, suffix), f"visits.{suffix}")
    assert profile is not None and profile.source.endswith("200 visits")
    assert profile.hour_shares() == pytest.approx({9: 1.0})
    assert profile.weights[1][9] == 200.5


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_invalid_rows_cannot_lift_a_file_over_the_visit_threshold(suffix):
    frame = pd.DataFrame({"timestamp": ["2026-10-19 09:00"] * 199 + ["Oct 20 18:00"],
                          "receipt_id": range(200)})
    assert supplemental.traffic_from_supplemental(export(frame, suffix), f"visits.{suffix}") is None


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_incomplete_dates_do_not_override_the_stores_generated_profile(suffix):
    frame = pd.DataFrame({"timestamp": ["2026-10 09:00"] * 200, "receipt_id": range(200)})
    assert supplemental.traffic_from_supplemental(export(frame, suffix), f"visits.{suffix}") is None


def test_native_excel_midnight_remains_in_a_column_with_established_clock_evidence():
    values = [datetime(2026, 10, 19, 9)] * 4 + [datetime(2026, 10, 20)]
    frame = pd.DataFrame({"timestamp": values, "receipt_id": range(5)})
    assert Counter(supplemental._visit_times_from_frame(frame)) == {(1, 9): 4, (2, 0): 1}


def test_repeated_values_share_bounded_calendar_parsing(monkeypatch):
    original = supplemental.parse_date
    calls = Counter()

    def observed(value, *args, **kwargs):
        calls[value] += 1
        return original(value, *args, **kwargs)

    monkeypatch.setattr(supplemental, "parse_date", observed)
    values = ["2026-10-19 09:00", "2026-10-19 00:00", "Oct 19 18:00", "unreadable"]
    frame = pd.DataFrame({"timestamp": [values[i % 4] for i in range(2000)], "receipt_id": range(2000)})
    supplemental._visit_times_from_frame(frame)
    assert sum(calls.values()) <= 2 * len(values)
