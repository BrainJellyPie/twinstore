"""POS imports preserve identifier text and reject unusable numeric measurements."""

import io

import pytest
from openpyxl import Workbook

from store_emulator.application.pos import parse_pos_csv


@pytest.mark.parametrize("value", ["NA", "NULL", "N/A", "nan", "NaN"])
@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_pos_identifiers_are_not_treated_as_missing_values(value, extension):
    data = f"receipt_id,sku,quantity\n{value},{value},1\n".encode()
    if extension == "xlsx":
        workbook = Workbook()
        workbook.active.append(["receipt_id", "sku", "quantity"])
        workbook.active.append([value, value, 1])
        buffer = io.BytesIO()
        workbook.save(buffer)
        data = buffer.getvalue()
    lines = parse_pos_csv(data, f"pos.{extension}")
    assert lines[0].transaction_id == value and lines[0].sku == value


@pytest.mark.parametrize("column", ["quantity", "unit_price", "line_total"])
@pytest.mark.parametrize("value", ["Infinity", "-Infinity", "NaN"])
def test_nonfinite_pos_measurements_are_rejected(column, value):
    with pytest.raises(ValueError):
        parse_pos_csv(f"receipt_id,sku,{column}\nreceipt,item,{value}\n".encode())


@pytest.mark.parametrize("timestamp, expected", [("1631", 16), ("930", 9), ("2359", 23), ("2400", None), ("2360", None), ("999", None)])
def test_compact_pos_times_require_valid_hours_and_minutes(timestamp, expected):
    lines = parse_pos_csv(f"receipt_id,sku,trans_time\nreceipt,item,{timestamp}\n".encode())
    assert lines[0].hour == expected


def test_pos_skips_blank_identifiers_and_preserves_optional_numeric_defaults():
    lines = parse_pos_csv(b"receipt_id,sku,quantity,unit_price\n ,item,1,100\nreceipt, ,1,100\n receipt , item ,,\n")
    assert len(lines) == 1
    assert lines[0].transaction_id == "receipt" and lines[0].sku == "item"
    assert lines[0].quantity == 1 and lines[0].unit_price == 0


def test_cp949_fallback_preserves_identifier_text():
    data = "receipt_id,sku,note\nNA,NULL,사과\n".encode("cp949")
    lines = parse_pos_csv(data)
    assert lines[0].transaction_id == "NA" and lines[0].sku == "NULL"
