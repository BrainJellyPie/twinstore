import csv
import hashlib
import io
from datetime import date

import pytest

from store_emulator.domain.inventory_review import InventoryPeriod
from store_emulator.engine.analysis.inventory_review import COLUMNS, inventory_csv, inventory_template, review_inventory


def period(**changes):
    return InventoryPeriod.model_validate({"start_date": "2026-10-01", "end_date": "2026-10-31", "currency": "USD", **changes})


def row(**changes):
    return {"sku": "tea", "opening_units": "100", "received_units": "50", "sold_units": "80", "returned_units": "10",
        "other_in_units": "5", "other_out_units": "15", "closing_units": "70", "net_sales_minor": "14000",
        "cogs_minor": "7000", "opening_cost_minor": "10000", "closing_cost_minor": "7000", **changes}


def sheet(rows):
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=COLUMNS); writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def test_reconciles_returns_and_adjustments_and_computes_explicit_period_ratios():
    data = sheet([row()]); result = review_inventory(data, period()); r = result.rows[0]
    assert result.period_days == 31 and result.source_sha256 == hashlib.sha256(data).hexdigest()
    assert r.expected_closing_units == 70 and r.difference_units == 0 and r.reconciled
    assert r.net_sold_units == 70 and r.net_sell_through == pytest.approx(70 / 155)
    assert r.gross_profit_minor == 7000 and r.average_inventory_cost_minor == 8500
    assert r.gmroi == r.inventory_turns == pytest.approx(7000 / 8500) and r.flags == []
    assert result.totals.gmroi == r.gmroi


def test_mismatch_withholds_portfolio_ratios_without_dropping_inputs():
    result = review_inventory(sheet([row(), row(sku="coffee", closing_units="69")]), period())
    assert result.rows[1].difference_units == -1 and result.rows[1].flags == ["stock_mismatch"]
    assert result.rows[1].gmroi is result.rows[1].inventory_turns is result.rows[1].net_sell_through is None
    assert result.totals.sku_count == 2 and result.totals.reconciled_skus == 1
    assert result.totals.gross_profit_minor == 14000 and result.totals.ratios_withheld
    assert result.totals.gmroi is result.totals.inventory_turns is None


def test_portfolio_ratios_use_money_weighting_not_unweighted_sku_means():
    second = row(sku="coffee", net_sales_minor="2000", cogs_minor="1000", opening_cost_minor="100", closing_cost_minor="100")
    result = review_inventory(sheet([row(), second]), period())
    assert result.rows[1].gmroi == 10
    assert result.totals.gmroi == pytest.approx(8000 / 8600)
    assert result.totals.inventory_turns == pytest.approx(8000 / 8600)
    exported = list(csv.DictReader(io.StringIO(inventory_csv(result))))
    assert len(exported) == 3 and exported[-1]["row_type"] == "portfolio"
    assert exported[-1]["net_sales_minor"] == "16000" and exported[-1]["gross_profit_minor"] == "8000"
    assert all(r["source_sha256"] == result.source_sha256 and r["start_date"] == "2026-10-01" for r in exported)
    assert inventory_template().strip().split(",") == COLUMNS


def test_return_heavy_period_retains_negative_profit_but_explains_undefined_turnover_in_export():
    result = review_inventory(sheet([row(opening_units="10", received_units="0", sold_units="0", returned_units="2",
        other_in_units="0", other_out_units="0", closing_units="12", net_sales_minor="-200", cogs_minor="-100",
        opening_cost_minor="1000", closing_cost_minor="1200")]), period())
    r = result.rows[0]
    assert r.reconciled and r.net_sell_through is r.inventory_turns is None
    assert r.gmroi == pytest.approx(-100 / 1100) and set(r.flags) == {"net_returns", "negative_cogs"}
    assert result.totals.inventory_turns is None and result.totals.gmroi == r.gmroi
    exported = list(csv.DictReader(io.StringIO(inventory_csv(result))))
    assert "negative_cogs" in exported[-1]["flags"]
    assert exported[-1]["inventory_turns"] == "" and float(exported[-1]["gmroi"]) < 0


def test_zero_supply_and_inventory_cost_remain_unavailable_not_nan_or_zero():
    data = row(**{key: "0" for key in COLUMNS if key != "sku"})
    result = review_inventory(sheet([data]), period()); r = result.rows[0]
    assert r.reconciled and r.gross_profit_minor == 0
    assert r.net_sell_through is r.gmroi is r.inventory_turns is None
    assert set(r.flags) == {"zero_supply", "zero_inventory_cost"}
    assert result.totals.ratios_withheld and result.totals.gmroi is None
    assert 'NaN' not in result.model_dump_json() and 'Infinity' not in result.model_dump_json()


@pytest.mark.parametrize("changes,flag", [
    ({"sold_units": "1000", "closing_units": "0", "closing_cost_minor": "0"}, "negative_expected_stock"),
    ({"opening_units": "0", "received_units": "150"}, "empty_stock_value"),
    ({"closing_units": "0", "other_out_units": "85"}, "empty_stock_value"),
])
def test_stock_or_valuation_conflict_withholds_all_ratios(changes, flag):
    result = review_inventory(sheet([row(**changes)]), period()); r = result.rows[0]
    assert flag in r.flags and r.net_sell_through is r.gmroi is r.inventory_turns is None
    assert result.totals.ratios_withheld and result.totals.gmroi is None


def test_fractional_units_and_fractional_minor_average_are_exact_at_reconciliation():
    data = row(opening_units="0.1", received_units="0.2", sold_units="0.1", returned_units="0", other_in_units="0",
        other_out_units="0", closing_units="0.2", opening_cost_minor="1", closing_cost_minor="2", net_sales_minor="2", cogs_minor="1")
    r = review_inventory(sheet([data]), period()).rows[0]
    assert r.reconciled and r.expected_closing_units == 0.2 and r.difference_units == 0
    assert r.average_inventory_cost_minor == 1.5 and r.gmroi == pytest.approx(2 / 3)
    data["closing_units"] = "0.201"
    r = review_inventory(sheet([data]), period()).rows[0]
    assert not r.reconciled and r.difference_units == 0.001


@pytest.mark.parametrize("field,value", [
    ("opening_units", ""), ("returned_units", " "), ("sold_units", "-1"), ("other_in_units", "+1"),
    ("closing_units", "NaN"), ("received_units", "Infinity"), ("sold_units", "1e2"), ("sold_units", "0.0001"),
    ("sold_units", "1,000"), ("sold_units", "１"), ("sold_units", "١"), ("sold_units", "1\x00"),
    ("opening_units", "1000000.001"), ("net_sales_minor", "1.5"), ("net_sales_minor", "1000000000001"),
    ("cogs_minor", "-1000000000001"), ("cogs_minor", "false"), ("opening_cost_minor", "-1"),
    ("closing_cost_minor", ""), ("net_sales_minor", "+100"), ("net_sales_minor", "-NaN"),
    ("sku", ""), ("sku", " tea"), ("sku", "tea "), ("sku", "x\nline"), ("sku", "x\u200b"), ("sku", "x" * 201),
])
def test_invalid_or_missing_input_is_rejected_without_partial_results(field, value):
    with pytest.raises(ValueError, match="Row 3"):
        review_inventory(sheet([row(), row(sku="coffee", **{field: value}) if field != "sku" else row(sku=value)]), period())


def test_utf8_bom_reordered_headers_unicode_sku_and_repeated_sku():
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(reversed(COLUMNS))); writer.writeheader()
    writer.writerow(row(sku="茶,커피 🫖")); data = ("\ufeff" + out.getvalue()).encode()
    r = review_inventory(data, period()).rows[0]
    assert r.inputs.sku == "茶,커피 🫖" and r.reconciled
    with pytest.raises(ValueError, match="duplicate SKU"):
        review_inventory(sheet([row(sku="茶"), row(sku="茶")]), period())


@pytest.mark.parametrize("data,pattern", [
    (b"", "column"), (inventory_template().encode(), "at least one"), (b"sku,sku\n", "column"),
    ((inventory_template() + "too,few\n").encode(), "number of columns"),
    ((inventory_template() + '\n').encode(), "number of columns"),
    ((inventory_template() + '"broken').encode(), "Malformed"), (b"\xff", "UTF-8"),
    (b"x" * (2 * 1024 * 1024 + 1), "2 MB"),
])
def test_file_shape_encoding_and_size_errors(data, pattern):
    with pytest.raises(ValueError, match=pattern): review_inventory(data, period())


def test_period_bounds_including_leap_day_and_zero_length_day():
    from datetime import timedelta
    from pydantic import ValidationError
    start = date(2024, 2, 29)
    one = period(start_date=start, end_date=start)
    assert review_inventory(sheet([row()]), one).period_days == 1
    assert period(start_date=start, end_date=start + timedelta(days=3659))
    for end in [start - timedelta(days=1), start + timedelta(days=3660)]:
        with pytest.raises(ValidationError): period(start_date=start, end_date=end)
    for changes in [{"start_date": "2026-02-29"}, {"currency": "usd"}, {"currency": "USD_CENTS"}]:
        with pytest.raises(ValidationError): period(**changes)


def test_maximum_rows_and_values_preserve_integer_totals_and_reject_an_extra_row():
    inputs = [row(sku=f"item{i}", opening_units="1000000", received_units="0", sold_units="0", returned_units="0",
        other_in_units="0", other_out_units="0", closing_units="1000000", net_sales_minor="1000000000000", cogs_minor="-1000000000000",
        opening_cost_minor="1000000000000", closing_cost_minor="1000000000000") for i in range(2000)]
    result = review_inventory(sheet(inputs), period())
    assert result.totals.sku_count == 2000 and result.totals.reconciled_skus == 2000
    assert result.totals.gross_profit_minor == 4_000_000_000_000_000
    assert result.totals.average_inventory_cost_minor == 2_000_000_000_000_000 and result.totals.gmroi == 2
    assert result.totals.inventory_turns is None
    with pytest.raises(ValueError, match="2,000"):
        review_inventory(sheet([*inputs, row(sku="extra")]), period())


def test_order_invariance_and_export_keeps_input_numbers_but_escapes_formula_text():
    inputs = [row(sku="=SUM(1,1)"), row(sku="@test", net_sales_minor="-2000"), row(sku="'literal")]
    a = review_inventory(sheet(inputs), period()); b = review_inventory(sheet(list(reversed(inputs))), period())
    assert a.totals == b.totals and a.source_sha256 != b.source_sha256
    rows = list(csv.DictReader(io.StringIO(inventory_csv(a))))
    assert rows[0]["sku"] == "'=SUM(1,1)" and rows[1]["sku"] == "'@test" and rows[2]["sku"] == "''literal"
    assert rows[1]["net_sales_minor"] == "-2000" and float(rows[1]["gmroi"]) < 0
    assert all(None not in r and len(r) == len(rows[0]) for r in rows)
