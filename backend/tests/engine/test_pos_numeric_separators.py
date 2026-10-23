"""Only valid thousands grouping may be removed from POS numbers."""

import csv
import io

import pytest
from openpyxl import Workbook

from store_emulator.application.pos import parse_pos_csv


def upload(column, value, extension):
    rows = [["receipt_id", "sku", column], ["001", "tea", value]]
    if extension == "xlsx":
        book = Workbook()
        for row in rows:
            book.active.append(row)
        output = io.BytesIO()
        book.save(output)
        return output.getvalue()
    output = io.StringIO()
    csv.writer(output).writerows(rows)
    return output.getvalue().encode()


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
@pytest.mark.parametrize("column", ["quantity", "unit_price", "line_total"])
@pytest.mark.parametrize("value", ["0,5", "12,50", "1.234,56", "1,,234", ",123", "123,",
                                    "12,34,567", "1234,567", "1e1,0", "1,234.5,6", "-0,25"])
def test_non_grouping_commas_cannot_inflate_pos_quantities_or_prices(extension, column, value):
    with pytest.raises(ValueError, match="numeric POS value"):
        parse_pos_csv(upload(column, value, extension), f"sales.{extension}")


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
@pytest.mark.parametrize("value,expected", [
    ("1,250", 1250), ("1,234,567.89", 1234567.89), ("-1,250.5", -1250.5),
    ("+12,345", 12345), ("1,234e-2", 12.34), (" 1,234.50 ", 1234.5),
    ("0.5", .5), ("-0.25", -.25), ("1e3", 1000),
])
def test_valid_grouping_and_existing_decimal_numbers_keep_their_value(extension, value, expected):
    line = parse_pos_csv(upload("quantity", value, extension), f"sales.{extension}")[0]
    assert line.quantity == pytest.approx(expected)
    assert line.transaction_id == "001"


def test_ambiguous_optional_hour_does_not_get_turned_into_another_clock():
    line = parse_pos_csv(upload("hour", "1,2", "csv"))[0]
    assert line.hour is None
