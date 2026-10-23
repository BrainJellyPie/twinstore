"""POS timestamps and receipt identities must not collapse unrelated visits."""

import io
import random
from collections import Counter
from itertools import permutations

import pandas as pd
import pytest

from store_emulator.application.supplemental import _visit_times_from_frame, traffic_from_supplemental


@pytest.mark.parametrize("misleading", ["order_time", "transaction_datetime", "receipt_timestamp", "invoice_date", "order_total", "transaction_type"])
@pytest.mark.parametrize("id_name", ["receipt_id", "Transaction Number", "주문번호"])
def test_timestamp_amount_and_type_columns_never_replace_the_receipt_id(misleading, id_name):
    columns = {"timestamp": ["2026-10-19 09:00"] * 4, misleading: ["2026-10-19 09:00"] * 4,
               id_name: [1, 1, 2, 2]}
    if misleading == "order_total": columns[misleading] = [1500] * 4
    if misleading == "transaction_type": columns[misleading] = ["sale"] * 4
    for order in permutations(columns):
        frame = pd.DataFrame({key: columns[key] for key in order})
        assert _visit_times_from_frame(frame) == [(1, 9), (1, 9)], order


def test_receipt_numbers_can_restart_on_another_calendar_date():
    frame = pd.DataFrame({"receipt_id": [1, 1, 1, 1],
                          "timestamp": ["2026-10-19 09:00"] * 2 + ["2026-10-20 18:00"] * 2})
    assert _visit_times_from_frame(frame) == [(1, 9), (2, 18)]


@pytest.mark.parametrize("scope", ["register_id", "Terminal Number", "store_id", "매장번호"])
def test_receipt_numbers_can_restart_in_another_register_or_store(scope):
    frame = pd.DataFrame({"receipt_id": [1, 1, 1, 1], "timestamp": ["2026-10-19 09:00"] * 4,
                          scope: ["A", "A", "B", "B"]})
    assert _visit_times_from_frame(frame) == [(1, 9), (1, 9)]


def test_without_receipt_id_each_timestamped_row_remains_a_visit():
    frame = pd.DataFrame({"order_time": ["2026-10-19 09:00"] * 3, "product": ["tea", "coffee", "water"]})
    assert _visit_times_from_frame(frame) == [(1, 9)] * 3


@pytest.mark.parametrize("timestamp", ["2026-10-19 00:00:00", "2026-10-19T00:00:00Z"])
def test_explicit_midnight_timestamps_are_not_confused_with_dates(timestamp):
    frame = pd.DataFrame({"timestamp": [timestamp] * 4, "receipt_id": [1, 1, 2, 2]})
    assert _visit_times_from_frame(frame) == [(1, 0), (1, 0)]


@pytest.mark.parametrize("timestamp", ["2026-10-19", "unreadable", 20261019])
def test_dates_and_non_timestamps_do_not_fabricate_midnight_traffic(timestamp):
    assert _visit_times_from_frame(pd.DataFrame({"date": [timestamp] * 4})) == []


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_generated_exports_keep_date_register_and_receipt_identity(suffix):
    rng = random.Random(231026)
    rows = []
    expected = Counter()
    for day in range(19, 26):
        for register in ("A", "B"):
            for receipt in range(25):
                hour = rng.choice([0, 9, 18, 23])
                expected[(day - 18, hour)] += 1
                for item in range(rng.randint(1, 4)):
                    rows.append({"order_time": f"2026-10-{day} {hour:02d}:00:00", "order_id": receipt,
                                 "terminal_id": register, "order_total": 1500, "product": f"product_{item}"})
    rng.shuffle(rows)
    frame = pd.DataFrame(rows)
    assert Counter(_visit_times_from_frame(frame)) == expected
    if suffix == "csv":
        data = frame.to_csv(index=False).encode("utf-8-sig")
    else:
        output = io.BytesIO()
        frame.to_excel(output, index=False)
        data = output.getvalue()
    profile = traffic_from_supplemental(data, f"visits.{suffix}")
    assert profile is not None
    assert profile.source.endswith("350 visits")
    for (day, hour), count in expected.items():
        assert profile.weights[day][hour] == count + 0.5
