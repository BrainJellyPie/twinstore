"""Reject sparse POS tables before pandas allocates their missing cells."""

import csv
import io
from unittest.mock import Mock

import pytest

from store_emulator.application import pos


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp949"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_sparse_pos_csv_is_bounded_before_dataframe_allocation(monkeypatch, encoding, newline):
    header = ["receipt_id", "sku"] + [f"열{index}" for index in range(1998)]
    data = (newline.join([",".join(header)] + ["receipt,item"] * 1001) + newline).encode(encoding)
    assert len(data) < 50_000
    reader = Mock(side_effect=AssertionError("Do not allocate the padded table"))
    monkeypatch.setattr(pos.pd, "read_csv", reader)
    with pytest.raises(ValueError, match="cells"):
        pos.parse_pos_csv(data)
    reader.assert_not_called()


@pytest.mark.parametrize("rows,allowed", [(1, True), (2, True), (3, False)])
def test_sparse_pos_budget_includes_missing_fields_at_boundary(monkeypatch, rows, allowed):
    monkeypatch.setattr(pos, "MAX_POS_CSV_CELLS", 6, raising=False)
    data = ("receipt_id,sku,quantity\n" + "001,NA\n" * rows).encode()
    if allowed:
        lines = pos.parse_pos_csv(data)
        assert len(lines) == rows
        assert all((line.transaction_id, line.sku, line.quantity) == ("001", "NA", 1) for line in lines)
    else:
        with pytest.raises(ValueError, match="cells"):
            pos.parse_pos_csv(data)


@pytest.mark.parametrize("data,reason", [
    (b"receipt_id,sku\nr1,item,extra\n", "fields"),
    (b'receipt_id,sku\nr1,"unterminated', "quoting"),
    (b"\n  \r\n", "empty"),
])
def test_invalid_pos_structure_is_rejected_before_dataframe_allocation(monkeypatch, data, reason):
    reader = Mock(side_effect=AssertionError("Do not allocate the invalid table"))
    monkeypatch.setattr(pos.pd, "read_csv", reader)
    with pytest.raises(ValueError, match=reason):
        pos.parse_pos_csv(data)
    reader.assert_not_called()


@pytest.mark.parametrize("note", ['first\nsecond\r\nthird', 'x' * 200_000, 'Tea, milk;\t"value"'])
def test_pos_quoted_notes_and_leading_blank_lines_keep_rows_and_prices(monkeypatch, note):
    monkeypatch.setattr(pos, "MAX_POS_CSV_CELLS", 4, raising=False)
    stream = io.StringIO(newline="")
    stream.write("\n  \n")
    writer = csv.writer(stream)
    writer.writerow(["receipt_id", "sku", "note", "unit_price"])
    writer.writerow(["0001", "NULL", note, "1,250"])
    lines = pos.parse_pos_csv(stream.getvalue().encode())
    assert len(lines) == 1
    assert (lines[0].transaction_id, lines[0].sku, lines[0].unit_price) == ("0001", "NULL", 1250)


def test_header_alone_is_subject_to_pos_cell_budget(monkeypatch):
    monkeypatch.setattr(pos, "MAX_POS_CSV_CELLS", 2, raising=False)
    reader = Mock(side_effect=AssertionError("Do not allocate the wide header"))
    monkeypatch.setattr(pos.pd, "read_csv", reader)
    with pytest.raises(ValueError, match="cells"):
        pos.parse_pos_csv(b"receipt_id,sku,quantity\n")
    reader.assert_not_called()
