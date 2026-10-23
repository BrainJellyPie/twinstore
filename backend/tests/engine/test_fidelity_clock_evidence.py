"""Calendar dates and receipt row order cannot manufacture or erase hourly accuracy."""

from datetime import date, datetime, time

import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.engine.analysis.fidelity import fidelity_report
from tests.engine.test_fidelity_receipt_scope import export
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("timestamp", ["2026-10-19", "2026/10/19", "20261019", "19 Oct 2026", "", "unknown"])
def test_date_only_exports_do_not_claim_that_shoppers_came_at_midnight(suffix, timestamp):
    rows = [{"receipt_id": "r", "sku": "chips", "timestamp": timestamp}]
    lines = parse_pos_csv(export(rows, suffix), f"pos.{suffix}")
    assert lines[0].hour is None
    report = fidelity_report(_store(), [_shopper("p", "10:00:00", [("chips", 1)])], lines)
    assert "hourly_js_similarity" not in {metric.name for metric in report.metrics}
    assert any("no hour information" in note for note in report.notes)


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("timestamp,hour", [("2026-10-19 00:00", 0), ("2026-10-19T00:00:00+09:00", 0),
    ("00:00", 0), ("12 AM", 0), ("9 PM", 21), ("2026-10-19 12 AM", 0), ("930", 9), ("0000", 0)])
def test_explicit_clocks_including_midnight_remain_valid(suffix, timestamp, hour):
    lines = parse_pos_csv(export([{"receipt_id": "r", "sku": "chips", "timestamp": timestamp}], suffix), f"pos.{suffix}")
    assert lines[0].hour == hour


@pytest.mark.parametrize("timestamp,hour", [(date(2026, 10, 19), None), (datetime(2026, 10, 19), None),
    (datetime(2026, 10, 19, 9, 30), 9), (time(0), 0), (time(23, 59), 23)])
def test_native_excel_cells_preserve_clock_evidence(timestamp, hour):
    rows = [{"receipt_id": "r", "sku": "chips", "timestamp": timestamp}]
    lines = parse_pos_csv(export(rows, "xlsx"), "pos.xlsx")
    assert lines[0].hour == hour


def test_explicit_hour_column_disambiguates_native_excel_midnight():
    rows = [{"receipt_id": "r", "sku": "chips", "timestamp": datetime(2026, 10, 19), "hour": 0}]
    assert parse_pos_csv(export(rows, "xlsx"), "pos.xlsx")[0].hour == 0


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("clocks", [["", "10:00"], ["2026-10-19", "10:00"], ["10:59", "11:00"]])
@pytest.mark.parametrize("reverse", [False, True])
def test_receipts_use_the_earliest_available_clock_independent_of_line_order(suffix, clocks, reverse):
    rows = [{"receipt_id": "r", "sku": sku, "date": "2026-10-19", "timestamp": clock}
            for sku, clock in zip(["chips", "nuts"], clocks)]
    if reverse:
        rows.reverse()
    pos = parse_pos_csv(export(rows, suffix), f"pos.{suffix}")
    report = fidelity_report(_store(), [_shopper("p", "10:00:00", [("chips", 1), ("nuts", 1)])], pos)
    scores = {metric.name: metric.value for metric in report.metrics}
    assert report.real_transactions == 1
    assert scores.get("hourly_js_similarity") == 1
