"""Finite POS fields must not produce infinite aggregates or persisted scores."""

import itertools
import json
import math

import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.engine.analysis.fidelity import fidelity_report
from tests.engine.test_shared_store import _shopper, _store


OVERFLOW_ROWS = [
    "r,chips,1e200,1e200\n",
    "r,chips,1,1e308\nr,chips,1,1e308\n",
    "a,chips,1,1e308\nb,chips,1,1e308\n",
    "r,chips,1e308,0\nr,chips,1e308,0\n",
    "a,chips,1e308,0\nb,nuts,1e308,0\n",
    "r,chips,-1,1e308\nr,chips,-1,1e308\n",
]


def csv_data(rows):
    return ("receipt_id,sku,quantity,unit_price\n" + rows).encode()


def score(rows):
    return fidelity_report(_store(), [_shopper("p", "10:00:00", [("chips", 1)])], parse_pos_csv(csv_data(rows)))


@pytest.mark.parametrize("rows", OVERFLOW_ROWS)
def test_unrepresentable_line_receipt_or_dataset_totals_are_rejected(rows):
    with pytest.raises(ValueError, match="POS totals exceed"):
        score(rows)


@pytest.mark.parametrize("quantities", list(set(itertools.permutations(["1e308", "1e308", "-1e308"]))))
def test_cancelling_extreme_sales_and_returns_do_not_depend_on_row_order(quantities):
    rows = "".join(f"r,chips,{quantity},0\n" for quantity in quantities)
    with pytest.raises(ValueError, match="POS totals exceed"):
        score(rows)


@pytest.mark.parametrize("rows,metric", [
    ("r,chips,1e-310,1\n", "basket_units_mean_ratio"),
    ("r,chips,1,1e-310\n", "basket_value_mean_ratio"),
])
def test_ratios_outside_float_range_are_unavailable_in_valid_json(rows, metric):
    report = score(rows)
    values = {item.name: item.value for item in report.metrics}
    assert values[metric] is None
    assert all(value is None or math.isfinite(value) for value in values.values())
    json.dumps(report.model_dump(), allow_nan=False)


@pytest.mark.parametrize("rows,expected", [
    ("r,chips,1,1e200\n", 1e200),
    ("r,chips,2,100\nr,chips,-1,100\n", 200),
    ("r,chips,0.5,250\n", 175),
    ("r,chips,1,0\n", 300),
    ("r,chips,1,300\nunknown,unknown-sku,1e200,1e200\n", 0),
])
def test_representable_large_fractional_refunded_free_and_unmatched_sales_keep_scores(rows, expected):
    report = score(rows)
    assert next(metric.value for metric in report.metrics if metric.name == "basket_value_w1") == pytest.approx(expected)
    json.dumps(report.model_dump(), allow_nan=False)
