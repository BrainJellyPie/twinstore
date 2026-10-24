"""Malformed and sparse CSV input must not become shifted customer evidence."""

import json
from unittest.mock import Mock

import pytest

from store_emulator.application import supplemental
from store_emulator.application import customer_csv
from tests.engine.test_supplemental_csv_formats import encoded
from tests.server.test_project_templates import _meta, client


@pytest.mark.parametrize("encoding", ["utf-8-sig", "cp949", "utf-16", "utf-32-be"])
@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
@pytest.mark.parametrize("extra", ["value", "empty", "prefix"])
def test_extra_fields_cannot_silently_shift_named_columns(encoding, delimiter, extra):
    rows = [["timestamp", "receipt_id", "amount"]]
    for index in range(3):
        row = ["2026-10-19 20:00", str(index), "500"]
        rows.append((["고객"] + row) if extra == "prefix" else row + (["고객"] if extra == "value" else [""]))
    data = encoded("\n".join(delimiter.join(row) for row in rows), encoding)
    assert supplemental._load_frames(data, ".csv") == {}
    assert supplemental._load_frames(data, ".csv", preserve_identifiers=True) == {}


@pytest.mark.parametrize("data", [
    b"timestamp,receipt_id,amount\n2026-10-19,01,1,500\n2026-10-20,02,2,600\n",
    b'a,b\n1,2\n3,4,5\n', b'a,b\n"unterminated,field',
    b'timestamp,receipt_id\n2026-10-19 09:00,001\0A\n',
    b'timestamp,receipt_id\0ignored\n2026-10-19 09:00,001\n',
])
def test_bad_csv_is_reported_before_any_project_or_generation(client, data):
    api, generation = client
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(_meta())},
                        files={"supplemental": ("customers.csv", data, "text/csv")})
    assert response.status_code == 400 and "CSV" in response.text
    generation.assert_not_called()
    assert api.get("/api/projects").json() == before


def sparse_csv():
    return (",".join(f"column_{n}" for n in range(2000)) + "\n" + "1\n" * 1001).encode()


def test_small_sparse_csv_is_bounded_before_dataframe_allocation(monkeypatch):
    data = sparse_csv()
    assert len(data) < 30_000
    reader = Mock(side_effect=AssertionError("Do not allocate the padded table"))
    monkeypatch.setattr(supplemental.pd, "read_csv", reader)
    assert supplemental._load_frames(data, ".csv") == {}
    reader.assert_not_called()


def test_sparse_csv_budget_is_reported_before_project_creation(client):
    api, generation = client
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(_meta())},
                        files={"supplemental": ("customers.CSV", sparse_csv(), "text/csv")})
    assert response.status_code == 413 and "cells" in response.text
    generation.assert_not_called()
    assert api.get("/api/projects").json() == before


@pytest.mark.parametrize("rows,allowed", [(2, True), (3, True), (4, False)])
def test_cell_budget_includes_missing_fields_at_the_exact_boundary(monkeypatch, rows, allowed):
    monkeypatch.setattr(customer_csv, "MAX_CUSTOMER_CSV_CELLS", 6)
    data = ("one,two\n" + "1\n" * rows).encode()
    if allowed:
        frame = supplemental._load_frames(data, ".csv")["data"]
        assert frame.shape == (rows, 2) and frame["two"].isna().all()
    else:
        with pytest.raises(customer_csv.CustomerCsvLimitError):
            customer_csv.validate_customer_csv(data)


@pytest.mark.parametrize("note", ['a\nb\nc', 'x' * 200_000, 'Tea, milk;\t"value"'])
def test_quoted_notes_are_not_counted_as_extra_rows_or_fields(note):
    import csv
    import io
    stream = io.StringIO(newline="")
    stream.write("\n  \n")
    writer = csv.writer(stream)
    writer.writerow(["note", "amount"])
    writer.writerow([note, 500])
    frame = supplemental._load_frames(stream.getvalue().encode(), ".csv")["data"]
    assert frame.shape == (1, 2) and frame.iloc[0]["note"] == note and frame.iloc[0]["amount"] == 500
