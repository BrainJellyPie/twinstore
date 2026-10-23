"""Imported transaction IDs are labels; timezone offsets must not move local visits."""

import io
from collections import Counter

import pandas as pd
import pytest

from store_emulator.application.supplemental import _stage1_extract, _visit_times_from_frame, traffic_from_supplemental


def export(frame, suffix):
    if suffix == "csv":
        return frame.to_csv(index=False).encode("utf-8-sig")
    output = io.BytesIO()
    frame.to_excel(output, index=False)
    return output.getvalue()


@pytest.mark.parametrize("times", [
    ["2026-10-24T09:00:00+01:00", "2026-10-25T09:00:00+00:00"],
    ["2026-10-24 09:00:00", "2026-10-25T09:00:00+00:00"],
    ["2026-10-24T09:00:00+09:00", "2026-10-25 09:00:00"],
    ["2026-10-24T09:00:00-07:00", "2026-10-25T09:00:00+09:00"],
])
@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_mixed_offset_exports_keep_local_weekdays_and_hours(times, suffix):
    rows = [{"timestamp": timestamp, "receipt_id": f"r{i}"} for timestamp in times for i in range(100)]
    frame = pd.DataFrame(rows)
    assert Counter(_visit_times_from_frame(frame)) == {(6, 9): 100, (7, 9): 100}
    profile = traffic_from_supplemental(export(frame, suffix), f"mixed.{suffix}")
    assert profile is not None and profile.source.endswith("200 visits")
    assert profile.hour_shares() == {9: 1.0}
    assert profile.weights[6][9] == profile.weights[7][9] == 100.5


@pytest.mark.parametrize("ids", [["01", "1"], ["0001", "1", "001"], ["NA", "N/A", "NULL", "null"],
                                ["9007199254740992", "9007199254740993", ""]])
@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_identifier_text_survives_spreadsheet_and_csv_inference(ids, suffix):
    rows = []
    for register in range(100):
        for ident in ids:
            # Repeated product lines in each receipt, including missing-ID rows to exercise numeric inference.
            rows.extend({"timestamp": "2026-10-19 09:00:00", "receipt_id": ident,
                         "register_id": f"register_{register}", "price": 10} for _ in range(2))
    frame = pd.DataFrame(rows)
    count = sum(bool(ident) for ident in ids) * 100
    profile = traffic_from_supplemental(export(frame, suffix), f"ids.{suffix}")
    assert profile is not None and profile.source.endswith(f"{count} visits")
    assert profile.weights[1][9] == count + 0.5


def test_register_identifiers_also_keep_significant_leading_zeros():
    frame = pd.DataFrame([{"timestamp": "2026-10-19 09:00", "receipt_id": i, "register_id": register}
                          for i in range(100) for register in ["01", "1"]])
    profile = traffic_from_supplemental(export(frame, "csv"), "registers.csv")
    assert profile is not None and profile.source.endswith("200 visits")


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_traffic_string_preservation_does_not_change_numeric_summary_data(suffix):
    frame = pd.DataFrame({"timestamp": ["2026-10-19 09:00"] * 2, "receipt_id": ["01", "1"], "price": [10, 20]})
    frames, metadata, _ = _stage1_extract(export(frame, suffix), "." + suffix)
    assert metadata
    assert pd.api.types.is_numeric_dtype(next(iter(frames.values()))["price"])
    assert next(iter(frames.values()))["price"].sum() == 30


@pytest.mark.parametrize("dates", [["2026-10-19"] * 200, [pd.Timestamp("2026-10-19")] * 200])
def test_excel_date_only_values_remain_without_a_visit_time(dates):
    frame = pd.DataFrame({"timestamp": dates, "receipt_id": range(200)})
    assert traffic_from_supplemental(export(frame, "xlsx"), "dates.xlsx") is None
