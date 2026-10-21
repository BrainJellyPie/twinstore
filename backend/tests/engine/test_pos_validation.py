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


@pytest.mark.parametrize("column", ["quantity", "unit_price", "line_total"])
@pytest.mark.parametrize("value", ["not a number", "$2.50"])
def test_invalid_numeric_pos_cells_are_not_silently_defaulted(column, value):
    with pytest.raises(ValueError, match="numeric"):
        parse_pos_csv(f"receipt_id,sku,{column}\nreceipt,item,{value}\n".encode())


@pytest.mark.parametrize("hour", ["unknown", "", "NaN"])
def test_optional_unknown_hours_remain_optional(hour):
    lines = parse_pos_csv(f"receipt_id,sku,quantity,unit_price,hour\nreceipt,item,1,0,{hour}\n".encode())
    assert lines[0].hour is None
    assert lines[0].unit_price == 0


def test_numeric_pos_cells_support_weighed_items_refunds_and_grouped_prices():
    lines = parse_pos_csv(b'receipt_id,sku,quantity,unit_price\nsale,item,0.5,"1,250"\nrefund,item,-1,250\n')
    assert [(line.quantity, line.unit_price) for line in lines] == [(0.5, 1250), (-1, 250)]


@pytest.mark.parametrize("price,expected", [("", 250), ("  ", 250), ("0", 0), ("125", 125)])
def test_line_total_fills_missing_unit_prices_without_replacing_explicit_zero(price, expected):
    data = f"receipt_id,sku,quantity,unit_price,line_total\nr1,tea,2,{price},500\n".encode()
    lines = parse_pos_csv(data)
    assert lines[0].unit_price == expected


def test_price_fallback_is_per_row_and_supports_weighed_goods():
    data = b"receipt_id,sku,quantity,unit_price,line_total\nr1,tea,2,125,250\nr2,tea,0.5,,125\n"
    lines = parse_pos_csv(data)
    assert [line.unit_price for line in lines] == [125, 250]


@pytest.mark.parametrize("total", ["100", "-100", "NaN", "Infinity", "not a number"])
def test_zero_quantity_does_not_hide_an_invalid_or_nonzero_line_total(total):
    with pytest.raises(ValueError):
        parse_pos_csv(f"receipt_id,sku,quantity,line_total\nr1,tea,0,{total}\n".encode())


@pytest.mark.parametrize("total", ["0", "", "0.0"])
def test_zero_quantity_with_no_charge_keeps_a_zero_value(total):
    lines = parse_pos_csv(f"receipt_id,sku,quantity,line_total\nr1,tea,0,{total}\n".encode())
    assert lines[0].quantity == 0 and lines[0].unit_price == 0


@pytest.mark.parametrize("data_row", ["r1,tea,2,1,250", "r1,tea,2,100,250", "r1,tea,2,100,200,300", "0,100,2,1,250"])
def test_extra_csv_fields_cannot_shift_transaction_and_product_ids(data_row):
    with pytest.raises(ValueError, match="fields"):
        parse_pos_csv(f"receipt_id,sku,quantity,unit_price\n{data_row}\n".encode())


@pytest.mark.parametrize("index_column", [False, True])
def test_quoted_grouped_prices_keep_identifiers_with_or_without_an_exported_index(index_column):
    header = "receipt_id,sku,quantity,unit_price"
    data_row = 'r1,tea,2,"1,250"'
    if index_column:
        header, data_row = "," + header, "0," + data_row
    lines = parse_pos_csv(f"{header}\n{data_row}\n".encode())
    assert (lines[0].transaction_id, lines[0].sku, lines[0].quantity, lines[0].unit_price) == ("r1", "tea", 2, 1250)
