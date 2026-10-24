"""Array-formula children need their own saved results, even without an <f>."""

import io
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.application.workbooks import WorkbookLimitError
from tests.engine.test_pos_formula_cells import HEADERS, workbook


def array_workbook(column, child="missing", *, reference=None, child_column=None):
    letter = chr(65 + HEADERS.index(column))
    cached = ("str", "tea") if column == "sku" else ("n", "2")
    source = workbook(column, "=A1:A2", cached=cached)
    output = io.BytesIO()
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with ZipFile(io.BytesIO(source)) as archive, ZipFile(output, "w", ZIP_DEFLATED) as rewritten:
        for info in archive.infolist():
            content = archive.read(info)
            if info.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(content)
                anchor = next(c for c in root.iter(ns + "c") if c.get("r") == letter + "2")
                anchor.find(ns + "f").attrib.update({"t": "array", "ref": reference or f"{letter}2:{letter}3"})
                row = next(r for r in root.iter(ns + "row") if r.get("r") == "3")
                child_letter = chr(65 + HEADERS.index(child_column)) if child_column else letter
                cell = next(c for c in row if c.get("r") == child_letter + "3")
                if child != "saved":
                    for node in list(cell):
                        cell.remove(node)
                    cell.set("t", "n")
                    if child == "absent":
                        row.remove(cell)
                    elif child == "zero":
                        ET.SubElement(cell, ns + "v").text = "0"
                    elif child == "empty_text":
                        cell.set("t", "str")
                        ET.SubElement(cell, ns + "v")
                content = ET.tostring(root)
            rewritten.writestr(info, content)
    return output.getvalue()


@pytest.mark.parametrize("column", ["sku", "quantity", "unit_price", "hour", "date", "store_id"])
@pytest.mark.parametrize("child", ["missing", "absent"])
def test_uncached_array_children_cannot_drop_or_default_pos_values(column, child):
    with pytest.raises(ValueError, match="POS worksheet row 3, column"):
        parse_pos_csv(array_workbook(column, child), "pos.xlsx")


@pytest.mark.parametrize("column", ["sku", "quantity", "unit_price"])
def test_fully_cached_array_children_keep_their_values(column):
    lines = parse_pos_csv(array_workbook(column, "saved"), "pos.xlsx")
    assert len(lines) == 2
    assert (lines[1].sku, lines[1].quantity, lines[1].unit_price) == ("coffee", 1, 300)


@pytest.mark.parametrize("child", ["zero", "empty_text"])
def test_zero_and_explicitly_empty_array_results_are_saved_values(child):
    lines = parse_pos_csv(array_workbook("unit_price", child), "pos.xlsx")
    assert len(lines) == 2 and lines[1].unit_price == 0


def test_empty_cached_array_sku_is_an_intentionally_unused_row():
    lines = parse_pos_csv(array_workbook("sku", "empty_text"), "pos.xlsx")
    assert [line.transaction_id for line in lines] == ["r1"]


def test_uncached_notes_array_is_not_an_imported_pos_column():
    lines = parse_pos_csv(array_workbook("notes"), "pos.xlsx")
    assert len(lines) == 2


def test_an_array_tail_beyond_existing_rows_is_not_silently_omitted():
    with pytest.raises(ValueError, match="POS worksheet row 4, column 2"):
        parse_pos_csv(array_workbook("sku", "saved", reference="B2:B4"), "pos.xlsx")


def test_array_dimensions_are_bounded_before_tracking_cached_cells():
    with pytest.raises(WorkbookLimitError, match="cells"):
        parse_pos_csv(array_workbook("sku", "saved", reference="B2:XFD1048576"), "pos.xlsx")


@pytest.mark.parametrize("reference", ["invalid", "B3:B2", "B0:B3", "B2:C3:D4"])
def test_invalid_array_ranges_cannot_hide_missing_results(reference):
    with pytest.raises(ValueError, match="POS worksheet row 2, column 2"):
        parse_pos_csv(array_workbook("sku", reference=reference), "pos.xlsx")


@pytest.mark.parametrize("child", ["missing", "absent"])
def test_two_dimensional_array_checks_columns_beyond_its_anchor(child):
    with pytest.raises(ValueError, match="POS worksheet row 3, column 4"):
        parse_pos_csv(array_workbook("sku", child, reference="B2:D3", child_column="unit_price"), "pos.xlsx")
