"""Sorting receipt product lines must not shift customer-generation visit hours."""

from collections import Counter

import pandas as pd
import pytest

from store_emulator.application.supplemental import _visit_times_from_frame, traffic_from_supplemental
from tests.engine.test_supplemental_pos_parsing import export


@pytest.mark.parametrize("kind", ["timestamp", "offset", "split", "native"])
@pytest.mark.parametrize("seed", [0, 3, 17])
def test_receipts_use_earliest_local_time_without_merging_scope_or_dates(kind, seed):
    rows = []
    for date in ["2026-10-19", "2026-10-20"]:
        for register in ["01", "1", ""]:
            for clock in ["10:59:59", "11:00:00", "11:01:00"]:
                row = {"receipt_id": "001", "register_id": register}
                timestamp = f"{date} {clock}"
                if kind == "split":
                    row.update(date=date, time=clock)
                elif kind == "offset":
                    row["timestamp"] = timestamp + ("+09:00" if clock.startswith("10") else "-07:00")
                elif kind == "native":
                    row["timestamp"] = pd.Timestamp(timestamp)
                else:
                    row["timestamp"] = timestamp
                rows.append(row)
    frame = pd.DataFrame(rows).sample(frac=1, random_state=seed)
    before = frame.copy(deep=True)
    assert Counter(_visit_times_from_frame(frame)) == {(1, 10): 3, (2, 10): 3}
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("seed", [0, 3, 17])
def test_bad_timestamp_lines_do_not_replace_the_receipts_valid_start(seed):
    rows = [{"receipt_id": "r", "timestamp": stamp} for stamp in [
        "unreadable", "2026-10-19 00:00:01", "2026-10-19 01:00:00", "2026-10-19 01:01:00", "2026-10-19 01:02:00",
    ]]
    assert _visit_times_from_frame(pd.DataFrame(rows).sample(frac=1, random_state=seed)) == [(1, 0)]


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("seed", [0, 3, 17])
def test_fitted_customer_traffic_is_invariant_to_product_row_order(suffix, seed):
    rows = [{"receipt_id": f"{receipt:03d}", "timestamp": f"2026-10-19 {clock}", "product": product}
            for receipt in range(200) for clock, product in [("10:59:59", "Tea"), ("11:00:00", "Bread")]]
    frame = pd.DataFrame(rows).sample(frac=1, random_state=seed)
    profile = traffic_from_supplemental(export(frame, suffix), f"visits.{suffix}")
    assert profile is not None and profile.source.endswith("200 visits")
    assert profile.hour_shares() == pytest.approx({10: 1})
    assert profile.weights[1] == {10: 200.5}


def test_records_without_receipt_ids_keep_each_observed_visit():
    frame = pd.DataFrame({"timestamp": ["2026-10-19 11:00", "2026-10-19 10:59", "2026-10-19 11:00"]})
    assert Counter(_visit_times_from_frame(frame)) == {(1, 10): 1, (1, 11): 2}
