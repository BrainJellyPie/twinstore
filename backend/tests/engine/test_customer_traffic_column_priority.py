"""Unrelated account timestamps cannot outrank a named transaction/visit clock."""

import pandas as pd
import pytest

from store_emulator.application.supplemental import _visit_times_from_frame, traffic_from_supplemental
from tests.engine.test_supplemental_pos_parsing import export


@pytest.mark.parametrize("columns", [
    ("transaction_datetime",), ("receipt_timestamp",), ("timestamp",), ("Date Time",),
    ("거래일시",), ("방문일시",), ("transaction_date", "transaction_time"), ("거래일자", "거래시간"),
])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("partial", [False, True])
def test_named_visit_clock_wins_over_unrelated_more_complete_timestamps(columns, reverse, partial):
    data = {"customer_registered_at": ["2025-04-06 08:30:00"] * 5,
            "receipt_id": [str(i) for i in range(5)]}
    if len(columns) == 1:
        data[columns[0]] = ["2026-10-19 17:00:00"] * 5
    else:
        data[columns[0]] = ["2026-10-19"] * 5
        data[columns[1]] = ["17:00:00"] * 5
    if partial:
        data[columns[-1]][0] = "unknown"
    if reverse:
        data = dict(reversed(list(data.items())))
    assert _visit_times_from_frame(pd.DataFrame(data)) == [(1, 17)] * (4 if partial else 5)


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("split", [False, True])
def test_customer_traffic_upload_uses_sale_time_instead_of_account_creation(suffix, split):
    data = {"customer_registered_at": ["2025-04-06 08:30:00"] * 250,
            "receipt_id": [f"{i:03d}" for i in range(250)]}
    if split:
        data.update(transaction_date=["2026-10-19"] * 250, transaction_time=["unknown"] * 50 + ["00:00:00"] * 200)
    else:
        data["transaction_datetime"] = ["unknown"] * 50 + ["2026-10-19 00:00:00"] * 200
    profile = traffic_from_supplemental(export(pd.DataFrame(data), suffix), f"visits.{suffix}")
    assert profile is not None and profile.source.endswith("200 visits")
    assert profile.hour_shares() == pytest.approx({0: 1})
    assert profile.weights[1] == {0: 200.5}


@pytest.mark.parametrize("named", [None, "unreadable", "2026-10-19"])
def test_unknown_column_fallback_remains_when_no_named_column_has_a_usable_clock(named):
    data = {"observed_at": ["2026-10-19 17:00:00"] * 5, "receipt_id": list(range(5))}
    if named is not None:
        data["timestamp"] = [named] * 5
    assert _visit_times_from_frame(pd.DataFrame(data)) == [(1, 17)] * 5
