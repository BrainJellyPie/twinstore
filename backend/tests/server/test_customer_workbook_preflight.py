"""Unreadable customer workbooks must fail before any model work or project creation."""

import io
import json
from unittest.mock import Mock
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook

from store_emulator.application import projects, supplemental
from tests.server.test_project_templates import _meta, client


def workbook(kind):
    if kind == "empty_file":
        return b""
    if kind == "text":
        return b"timestamp,receipt_id\n2026-10-24 09:00,001\n"
    if kind == "truncated_zip":
        return b"PK\x03\x04broken"
    book = Workbook()
    sheet = book.active
    if kind != "blank_book":
        sheet.append(["timestamp", "receipt_id"])
        if kind != "headers_only":
            sheet.append(["2026-10-24 09:00", "001"])
    if kind in ("bad_second_sheet", "blank_second_sheet", "missing_second_sheet"):
        other = book.create_sheet("Other")
        if kind == "missing_second_sheet":
            other.append(["receipt_id", "amount"])
            other.append(["002", 500])
    output = io.BytesIO()
    book.save(output)
    modified = io.BytesIO()
    with ZipFile(io.BytesIO(output.getvalue())) as source, ZipFile(modified, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            name = entry.filename
            data = source.read(entry)
            if kind == "missing_workbook" and name == "xl/workbook.xml":
                continue
            if kind == "missing_sheet" and name == "xl/worksheets/sheet1.xml":
                continue
            if kind == "missing_second_sheet" and name == "xl/worksheets/sheet2.xml":
                continue
            if kind == "bad_sheet" and name == "xl/worksheets/sheet1.xml":
                data = b"<worksheet><sheetData><row>"
            if kind == "bad_second_sheet" and name == "xl/worksheets/sheet2.xml":
                data = b"<worksheet><sheetData><row>"
            if kind == "invalid_number" and name == "xl/worksheets/sheet1.xml":
                data = data.replace(b'<c r="B2" t="inlineStr"><is><t>001</t></is></c>', b'<c r="B2" t="n"><v>not-a-number</v></c>')
            target.writestr(name, data)
        if kind == "unrelated_xml":
            target.writestr("customXml/extra.xml", "<broken")
    return modified.getvalue()


@pytest.mark.parametrize("kind", ["empty_file", "text", "truncated_zip", "missing_workbook", "missing_sheet",
                                  "bad_sheet", "bad_second_sheet", "missing_second_sheet", "invalid_number", "blank_book"])
@pytest.mark.parametrize("filename", ["customers.xlsx", "customers.XLSX"])
def test_bad_workbook_is_rejected_before_products_customers_or_project(client, monkeypatch, kind, filename):
    api, generation = client
    selection = Mock(side_effect=AssertionError("Invalid evidence must be rejected before model calls"))
    monkeypatch.setattr(projects, "select_initial_assortment", selection)
    before = api.get("/api/projects").json()
    meta = {**_meta(), "starter_selection": "automatic", "layout": {"template_id": "community_pharmacy"}}
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(meta)},
                        files={"supplemental": (filename, workbook(kind))})
    assert response.status_code == 400, response.text[:300]
    assert "Excel workbook" in response.text
    generation.assert_not_called()
    selection.assert_not_called()
    assert api.get("/api/projects").json() == before


@pytest.mark.parametrize("kind", ["normal", "headers_only", "blank_second_sheet", "unrelated_xml"])
def test_readable_workbook_is_kept_for_customer_generation(client, kind):
    api, generation = client
    data = workbook(kind)
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(_meta())},
                        files={"supplemental": ("customers.xlsx", data)})
    assert response.status_code == 200, response.text[:300]
    assert generation.call_args.kwargs["supplemental_bytes"] == data
    assert generation.call_args.kwargs["supplemental_filename"] == "customers.xlsx"
    frames = supplemental._load_frames(data, ".xlsx", preserve_identifiers=True)
    assert list(frames["Sheet"].columns) == ["timestamp", "receipt_id"]
    if kind != "headers_only":
        assert frames["Sheet"].iloc[0]["receipt_id"] == "001"
