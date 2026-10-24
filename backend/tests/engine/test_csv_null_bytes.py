"""NUL cannot silently truncate pandas headers, IDs or numeric evidence."""

import csv
import io
from unittest.mock import Mock

import pytest

from store_emulator.application import pos, supplemental
from store_emulator.application.csv_tables import CsvError, validate_csv_table
from store_emulator.application.customer_csv import validate_customer_csv
from tests.engine.test_supplemental_csv_formats import encoded


@pytest.mark.parametrize("field", ["receipt_id", "sku", "quantity", "unit_price", "timestamp"])
@pytest.mark.parametrize("quoted", [False, True])
def test_null_in_pos_values_cannot_change_receipts_products_or_prices(field, quoted):
    row = {"receipt_id": "001", "sku": "tea", "quantity": "1", "unit_price": "3", "timestamp": "2026-10-19 09:00"}
    row[field] += "\0suffix"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL if quoted else csv.QUOTE_MINIMAL)
    writer.writerow(row)
    writer.writerow(row.values())
    with pytest.raises(CsvError, match="NUL"):
        pos.parse_pos_csv(stream.getvalue().encode())


@pytest.mark.parametrize("text", [
    "receipt_id\0ignored,sku\nr1,tea\n",
    "receipt_id,sku\0ignored\nr1,tea\n",
    "receipt_id,sku,note\nr1,tea,\0\n",
    "receipt_id,sku\nr1,tea\n\0",
])
def test_header_note_and_trailing_nulls_fail_before_pandas(monkeypatch, text):
    reader = Mock(side_effect=AssertionError("Invalid text must not reach pandas"))
    monkeypatch.setattr(pos.pd, "read_csv", reader)
    with pytest.raises(CsvError, match="NUL"):
        pos.parse_pos_csv(text.encode())
    reader.assert_not_called()


@pytest.mark.parametrize("encoding", ["utf-8-sig", "cp949", "utf-16", "utf-32-be"])
@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_customer_encoding_and_delimiter_cannot_hide_a_null(encoding, delimiter):
    text = delimiter.join(["timestamp", "receipt_id"]) + "\n" + delimiter.join(["2026-10-19 09:00", "001\0A"]) + "\n"
    data = encoded(text, encoding)
    with pytest.raises(CsvError, match="NUL"):
        validate_customer_csv(data)
    assert supplemental._load_frames(data, ".csv", preserve_identifiers=True) == {}


@pytest.mark.parametrize("text", [
    "receipt_id,sku\n001,NULL\n", "note\nvisible ␀ symbol\n", "note\nliteral \\0 text\n",
    'note\n"commas, tabs\tand\nnewlines"\n',
])
def test_textual_null_labels_and_legitimate_controls_remain_text(text):
    validate_csv_table(text, ",", label="Test CSV", max_cells=100)
