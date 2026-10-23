"""Common spreadsheet exports must reach both summary and traffic extraction intact."""

import codecs
import csv
import io

import pandas as pd
import pytest

from store_emulator.application.supplemental import _load_frames, _stage1_extract, traffic_from_supplemental


def encoded(text, encoding):
    if encoding == "utf-16-be":
        return codecs.BOM_UTF16_BE + text.encode(encoding)
    if encoding == "utf-32-be":
        return codecs.BOM_UTF32_BE + text.encode(encoding)
    return text.encode(encoding)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp949", "utf-16", "utf-16-be", "utf-32", "utf-32-be"])
@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_spreadsheet_csv_dialects_preserve_cells_and_customer_visits(encoding, delimiter, newline):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=delimiter, lineterminator=newline)
    writer.writerow(["timestamp", "receipt_id", "register_id", "상품", "price"])
    for register in range(100):
        for receipt in ["01", "1"]:
            # Two product lines per receipt; delimiters and quotes inside a cell are data.
            for _ in range(2):
                writer.writerow(["2026-10-19 09:00", receipt, f"r{register}", '차, 우유;\t"특가"\n상품', 1250])
    data = encoded(output.getvalue(), encoding)
    frames, metadata, samples = _stage1_extract(data, ".csv")
    assert len(frames) == 1
    frame = frames["data"]
    assert list(frame.columns) == ["timestamp", "receipt_id", "register_id", "상품", "price"]
    assert frame.shape == (400, 5)
    assert frame.iloc[0]["상품"] == '차, 우유;\t"특가"\n상품'
    assert pd.api.types.is_numeric_dtype(frame["price"])
    assert frame["price"].sum() == 500000
    assert metadata and samples
    profile = traffic_from_supplemental(data, "고객.CSV")
    assert profile is not None and profile.source.endswith("200 visits")
    assert profile.hour_shares() == pytest.approx({9: 1.0})


@pytest.mark.parametrize("data,expected", [
    (b'comment\n"apples, pears; tea"\n"milk, eggs; bread"\n', ["apples, pears; tea", "milk, eggs; bread"]),
    (b'comment\napples\npears\n', ["apples", "pears"]),
    (b'comment\n"line one\nline two"\n"a\tb"\n', ["line one\nline two", "a\tb"]),
])
def test_single_column_customer_notes_do_not_get_split(data, expected):
    frames = _load_frames(data, ".csv")
    assert list(frames["data"].columns) == ["comment"]
    assert frames["data"]["comment"].tolist() == expected


def test_semicolon_export_keeps_decimal_commas_as_cell_text():
    data = 'timestamp;receipt_id;amount\n2026-10-19 09:00;01;12,50\n2026-10-19 10:00;02;15,25\n'.encode()
    frame = _load_frames(data, ".csv", preserve_identifiers=True)["data"]
    assert frame["amount"].tolist() == ["12,50", "15,25"]
    assert frame["receipt_id"].tolist() == ["01", "02"]


@pytest.mark.parametrize("data", [b"", b"\xff\xff", codecs.BOM_UTF16_LE + b"a",
                                   codecs.BOM_UTF32_LE + b"a", b'a,b\n"unterminated,field',
                                   b"a,b\n1,2\n3,4,5\n"])
def test_malformed_csv_remains_unusable(data):
    assert _load_frames(data, ".csv") == {}
    assert traffic_from_supplemental(data, "invalid.csv") is None


def test_invalid_workbook_and_unsupported_extensions_remain_unusable():
    assert _load_frames(b"not a workbook", ".xlsx") == {}
    assert _load_frames(b"a,b\n1,2", ".txt") == {}
