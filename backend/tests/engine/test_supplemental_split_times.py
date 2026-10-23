"""Traffic fitting needs an explicit calendar date, including exports with separate clock columns."""

from collections import Counter
from datetime import time

import pandas as pd
import pytest

from store_emulator.application.supplemental import _visit_times_from_frame, traffic_from_supplemental
from tests.engine.test_supplemental_pos_parsing import export


@pytest.mark.parametrize("clocks", [["09:00", "18:00"], ["9 AM", "6 PM"], [time(9), time(18)],
                                    ["09:00:30.123", "18:00:40"], ["09:00+09:00", "18:00Z"]])
def test_clock_only_values_never_borrow_the_execution_date(clocks):
    frame = pd.DataFrame({"time": clocks, "receipt_id": [1, 2]})
    assert _visit_times_from_frame(frame) == []


@pytest.mark.parametrize("dates", [["2026-10-19", "2026-10-20"], [pd.Timestamp("2026-10-19"), pd.Timestamp("2026-10-20")]])
@pytest.mark.parametrize("clocks", [["09:00", "18:00"], ["9 AM", "6 PM"], [time(9), time(18)], ["00:00", "23:59:59"]])
def test_separate_date_and_clock_columns_are_combined_by_row(dates, clocks):
    frame = pd.DataFrame({"거래일자": dates, "거래시간": clocks, "receipt_id": [1, 1]})
    expected_hours = [0, 23] if clocks == ["00:00", "23:59:59"] else [9, 18]
    expected = [(1, expected_hours[0]), (2, expected_hours[1])]
    assert _visit_times_from_frame(frame) == expected
    assert _visit_times_from_frame(frame[["거래시간", "receipt_id", "거래일자"]]) == expected


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_split_exports_use_real_dates_and_receipt_days(suffix):
    frame = pd.DataFrame([{"date": date, "time": clock, "receipt_id": receipt}
                          for date, clock in [("2026-10-19", "09:00"), ("2026-10-20", "18:00")]
                          for receipt in range(100) for _ in range(2)])
    profile = traffic_from_supplemental(export(frame, suffix), f"split.{suffix}")
    assert profile is not None and profile.source.endswith("200 visits")
    assert profile.weights[1][9] == profile.weights[2][18] == 100.5
    assert profile.weights[5][9] == profile.weights[5][18] == 0.5


def test_partial_time_only_values_do_not_contaminate_complete_timestamps():
    values = ["2026-10-19 09:00"] * 8 + ["18:00", "19:00"]
    frame = pd.DataFrame({"timestamp": values, "receipt_id": range(10)})
    assert Counter(_visit_times_from_frame(frame)) == {(1, 9): 8}


def test_a_complete_timestamp_takes_precedence_over_separate_columns():
    frame = pd.DataFrame({"date": ["2026-10-20"] * 2, "time": ["18:00"] * 2,
                          "timestamp": ["2026-10-19 09:00"] * 2, "receipt_id": [1, 2]})
    assert _visit_times_from_frame(frame) == [(1, 9), (1, 9)]


def test_unmatched_dates_and_times_do_not_shift_valid_rows():
    frame = pd.DataFrame({"date": ["2026-10-19"] * 8 + ["bad", "2026-10-20"],
                          "time": ["09:00"] * 8 + ["18:00", "bad"], "receipt_id": range(10)},
                         index=list(range(20, 30)))
    assert _visit_times_from_frame(frame) == [(1, 9)] * 8


@pytest.mark.parametrize("date_label,time_label", [("birth_date", "time"), ("date", "duration")])
def test_unrelated_dates_or_durations_are_not_combined_as_visits(date_label, time_label):
    frame = pd.DataFrame({date_label: ["2026-10-19"] * 2, time_label: ["09:00"] * 2, "receipt_id": [1, 2]})
    assert _visit_times_from_frame(frame) == []
