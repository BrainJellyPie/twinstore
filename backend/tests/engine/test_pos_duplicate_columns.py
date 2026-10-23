"""Duplicate POS headers must not change receipt identity or sales by column order."""

import csv
import io

from openpyxl import Workbook
import pytest

from store_emulator.application.pos import parse_pos_csv


def data(headers, rows, extension):
    if extension == "xlsx":
        book = Workbook()
        sheet = book.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        output = io.BytesIO()
        book.save(output)
        return output.getvalue()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode()


HEADERS = ["receipt_id", "sku", "quantity", "unit_price", "line_total", "timestamp", "hour", "date", "store_id", "register_id"]
VALUES = ["001", "tea", 2, 250, 500, "2026-10-23 12:30:00", 12, "2026-10-23", "shop", "till"]


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
@pytest.mark.parametrize("column", HEADERS)
@pytest.mark.parametrize("variant", ["exact", "case", "space"])
def test_duplicate_recognized_columns_are_rejected_before_pandas_can_rename_them(extension, column, variant):
    duplicate = column if variant == "exact" else column.upper() if variant == "case" else f" {column} "
    contents = data([*HEADERS, duplicate], [[*VALUES, ""]], extension)
    with pytest.raises(ValueError, match="duplicate.*column"):
        parse_pos_csv(contents, f"pos.{extension}")


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
@pytest.mark.parametrize("name", ["Store ID", "store-id", "storeid", "Store.Id"])
def test_duplicate_scope_keys_cannot_create_an_ambiguous_receipt_identity(extension, name):
    contents = data([*HEADERS, name], [[*VALUES, "other-shop"]], extension)
    with pytest.raises(ValueError, match="duplicate.*column"):
        parse_pos_csv(contents, f"pos.{extension}")


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_distinct_aliases_keep_documented_precedence_and_optional_defaults(extension):
    headers = ["receipt_id", "order_id", "sku", "barcode", "quantity", "qty", "unit_price", "line_total"]
    lines = parse_pos_csv(data(headers, [["001", "different-order", "tea", "other-barcode", .5, 99, "", 125]], extension), f"pos.{extension}")
    assert [(line.transaction_id, line.sku, line.quantity, line.unit_price) for line in lines] == [("001", "tea", .5, 250)]


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_repeated_ignored_notes_and_spacer_columns_do_not_change_products(extension):
    headers = ["receipt_id", "sku", "notes", "notes", " NOTES ", "", "", "quantity"]
    lines = parse_pos_csv(data(headers, [["NULL", "001", "a", "b", "c", "", "", 0]], extension), f"pos.{extension}")
    assert [(line.transaction_id, line.sku, line.quantity) for line in lines] == [("NULL", "001", 0)]


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_header_only_files_remain_an_explicit_error(extension):
    with pytest.raises(ValueError, match="no usable rows"):
        parse_pos_csv(data(["receipt_id", "sku"], [], extension), f"pos.{extension}")
