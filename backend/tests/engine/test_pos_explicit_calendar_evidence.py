"""Complete calendar/time fields are recognized independently of formatting."""

from datetime import datetime, timedelta, timezone

import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.engine.analysis.fidelity import fidelity_report
from tests.engine.test_fidelity_receipt_scope import export
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("column", ["timestamp", "date"])
@pytest.mark.parametrize("hour", [0, 12])
@pytest.mark.parametrize("fmt", [
    "%m/%d/%y %H:%M", "%d/%m/%y %H:%M", "%d %b %Y %H:%M", "%B %d, %Y %I:%M %p",
    "%d-%b-%y %H:%M", "%Y%m%dT%H%M%S", "%Y%m%d%H%M%S", "%Y-%m-%dT%H%M%S%z",
    "%a, %d %b %Y %H:%M:%S %z",
])
def test_complete_calendar_forms_keep_receipts_separate(suffix, column, hour, fmt):
    stamps = [datetime(2026, 10, day, hour, 0, tzinfo=timezone(timedelta(hours=9))) for day in (22, 23)]
    rows = [{"receipt_id": "001", "sku": sku, "quantity": 1, "unit_price": price, column: stamp.strftime(fmt)}
            for stamp in stamps for sku, price in [("chips", 300), ("nuts", 350)]]
    pos = parse_pos_csv(export(rows, suffix), f"pos.{suffix}")
    assert [p.transaction_scope for p in pos] == [(("date", str(stamp.date())),) for stamp in stamps for _ in range(2)]
    assert {p.hour for p in pos} == {hour if column == "timestamp" else None}
    report = fidelity_report(_store(), [_shopper(f"p{i}", f"{hour:02}:00:00", [("chips", 1), ("nuts", 1)])
                                       for i in range(2)], pos)
    assert report.real_transactions == 2
    metrics = {m.name: m.value for m in report.metrics}
    assert metrics["basket_units_mean_ratio"] == metrics["basket_value_mean_ratio"] == 1


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("text,hour", [
    ("Oct 23 12:30", 12), ("Oct 2026", None), ("2026-10", None), ("23", None), ("Thursday", None),
    ("Feb 29 12:30", 12), ("12:30", 12), ("12 AM", 0), ("12 PM", 12), ("NaT", None),
    ("999999999999999999999999999999999999", None),
])
def test_missing_calendar_parts_do_not_borrow_an_import_date(suffix, text, hour):
    lines = parse_pos_csv(export([{"receipt_id": "1", "sku": "chips", "timestamp": text}], suffix), f"pos.{suffix}")
    assert not lines[0].transaction_scope
    assert lines[0].hour == hour


@pytest.mark.parametrize("month", range(1, 13))
@pytest.mark.parametrize("day", [1, 2, 28])
def test_named_month_calendar_dates_do_not_invent_a_clock(month, day):
    value = datetime(2024, month, day)
    text = value.strftime("%d %B %Y")
    line = parse_pos_csv(export([{"receipt_id": "1", "sku": "chips", "timestamp": text}], "csv"))[0]
    assert line.transaction_scope == (("date", str(value.date())),)
    assert line.hour is None
