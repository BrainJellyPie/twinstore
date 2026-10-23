"""Receipt numbers can restart on another day, in another store or at another register."""

import io

import pandas as pd
import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.domain.types import Weekday
from store_emulator.engine.analysis.fidelity import fidelity_report
from tests.engine.test_shared_store import _shopper, _store


def export(rows, suffix):
    frame = pd.DataFrame(rows)
    if suffix == "csv":
        return frame.to_csv(index=False).encode()
    out = io.BytesIO()
    frame.to_excel(out, index=False)
    return out.getvalue()


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("scope", ["timestamp", "date", "store_id", "register_id", "terminal_id", "till_no", "branch_id"])
def test_restarted_receipt_numbers_do_not_inflate_real_baskets(suffix, scope):
    values = ["2026-10-19 10:00", "2026-10-20 10:00"] if scope == "timestamp" else (
        ["2026-10-19", "2026-10-20"] if scope == "date" else ["01", "1"])
    rows = [{"receipt_id": "001", "sku": sku, "quantity": 1, "unit_price": price, scope: value}
            for value in values for sku, price in [("chips", 300), ("nuts", 350)]]
    pos = parse_pos_csv(export(rows, suffix), f"receipts.{suffix}")
    results = [_shopper(f"p{i}", "10:00:00", [("chips", 1), ("nuts", 1)], day=Weekday(i + 1)) for i in range(2)]
    report = fidelity_report(_store(), results, pos)
    metrics = {metric.name: metric.value for metric in report.metrics}
    assert report.real_transactions == 2
    assert metrics["basket_units_mean_ratio"] == metrics["basket_value_mean_ratio"] == 1.0
    assert metrics["basket_units_w1"] == metrics["basket_value_w1"] == 0.0
    assert {line.transaction_id for line in pos} == {"001"}


def test_date_and_register_scope_combine_without_splitting_receipt_lines_by_seconds():
    rows = []
    for day in ["2026-10-19", "2026-10-20"]:
        for register in ["01", "1"]:
            for second, sku, price in [(0, "chips", 300), (1, "nuts", 350)]:
                rows.append({"receipt_id": "r", "sku": sku, "quantity": 1, "unit_price": price,
                             "timestamp": f"{day} 10:00:0{second}+09:00", "register_id": register})
    pos = parse_pos_csv(export(rows, "csv"))
    results = [_shopper(f"p{i}", "10:00:00", [("chips", 1), ("nuts", 1)]) for i in range(4)]
    report = fidelity_report(_store(), results, pos)
    assert report.real_transactions == 4
    assert next(m.value for m in report.metrics if m.name == "basket_value_w1") == 0


@pytest.mark.parametrize("time", ["10:00", "1000", "10:00:00+09:00", "unknown", ""])
def test_time_only_or_missing_dates_do_not_invent_a_calendar_scope(time):
    pos = parse_pos_csv(f"receipt_id,sku,timestamp\nr,chips,{time}\nr,nuts,{time}\n".encode())
    assert all(not line.transaction_scope for line in pos)
    assert fidelity_report(_store(), [], pos).real_transactions == 1


def test_scope_values_cannot_collide_through_delimiter_concatenation():
    rows = [{"receipt_id": tx, "sku": "chips", "register_id": register} for tx, register in [("a|b", "c"), ("a", "b|c")]]
    pos = parse_pos_csv(export(rows, "csv"))
    assert fidelity_report(_store(), [], pos).real_transactions == 2


@pytest.mark.parametrize("date", ["2026-10-19", "2026/10/19", "20261019", "2026-10-19T00:00:00+09:00"])
def test_calendar_dates_are_normalized_before_receipt_grouping(date):
    rows = [{"receipt_id": "r", "sku": "chips", "date": value} for value in [date, "2026-10-19"]]
    pos = parse_pos_csv(export(rows, "csv"))
    assert pos[0].transaction_scope == pos[1].transaction_scope
    assert fidelity_report(_store(), [], pos).real_transactions == 1
