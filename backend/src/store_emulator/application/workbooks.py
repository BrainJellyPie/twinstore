"""Bound spreadsheet expansion before pandas materializes a dense table."""

import io
import re
from xml.etree.ElementTree import Element, ParseError, iterparse
from zipfile import BadZipFile, ZipFile

MAX_WORKBOOK_BYTES = 100 * 1024 * 1024
MAX_WORKBOOK_CELLS = 2_000_000
_CELL_REFERENCE = re.compile(r"([A-Za-z]{1,3})([0-9]+)\Z")


class WorkbookLimitError(ValueError):
    """The compressed file fits the upload limit but its expanded tables do not."""


def _cell_position(reference: str) -> tuple[int, int]:
    match = _CELL_REFERENCE.fullmatch(reference)
    if match is None or int(match[2]) < 1:
        raise ValueError("invalid cell reference")
    column = 0
    for letter in match[1].upper():
        column = column * 26 + ord(letter) - ord("A") + 1
    return int(match[2]), column


def _array_issues(archive: ZipFile, path: str, ranges: list[tuple[int, int, int, int]],
                  max_row: int, max_col: int) -> list[tuple[int, int]]:
    # The first scan bounds this bitmap and the sum of array areas to two million
    # cells. A second streaming pass also handles children appearing before anchors.
    saved = bytearray(max_row * max_col)
    row = column = cell_row = 0
    cell_type = ""
    cached = False
    with archive.open(path) as stream:
        parents: list[Element] = []
        for event, element in iterparse(stream, events=("start", "end")):
            tag = element.tag.rsplit("}", 1)[-1]
            if event == "start":
                parents.append(element)
                if tag == "row":
                    row, column = int(element.get("r", str(row + 1))), 0
                elif tag == "c":
                    column += 1
                    cell_row = row
                    if reference := element.get("r"):
                        cell_row, column = _cell_position(reference)
                    cell_type, cached = element.get("t", "n"), False
                continue
            if tag == "v":
                cached = element.text is not None or cell_type == "str"
            elif tag == "is" and cell_type == "inlineStr":
                cached = True
            elif tag == "c" and cached and cell_type != "e" and 1 <= cell_row <= max_row and 1 <= column <= max_col:
                saved[(cell_row - 1) * max_col + column - 1] = 1
            parents.pop()
            if parents:
                parents[-1].remove(element)
            element.clear()
    missing: dict[int, int] = {}
    for first_row, first_col, last_row, last_col in ranges:
        for column in range(first_col, last_col + 1):
            for row in range(first_row, last_row + 1):
                if not saved[(row - 1) * max_col + column - 1]:
                    # POS only needs the first unreadable cell in each imported column.
                    missing[column] = min(row, missing.get(column, row))
                    break
    return [(row, column) for column, row in missing.items()]


def validate_xlsx_budget(data: bytes, *, collect_cell_issues: bool = False) -> dict[str, list[tuple[int, int]]]:
    """Bound archive contents and actual sheet ranges, including sparse or misleading dimensions.

    Invalid workbooks and legacy non-ZIP Excel files remain the reader's responsibility. No rows are
    truncated: oversized workbooks must be exported with only the relevant data before importing.
    Optionally collect error/uncached-formula positions by worksheet part, for readers to check
    only the sheet and columns they import. Positions are one-based (row, column).
    """
    issues: dict[str, list[tuple[int, int]]] = {}
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_WORKBOOK_BYTES:
                raise WorkbookLimitError("Excel workbook expands beyond 100 MB. Export only the relevant data and try again.")
            cells = 0
            for info in archive.infolist():
                try:
                    with archive.open(info) as stream:
                        events = iterparse(stream, events=("start", "end"))
                        _, root = next(events)
                        if root.tag.rsplit("}", 1)[-1] != "worksheet":
                            continue
                        row = col = max_row = max_col = 0
                        cell_row = 0
                        cell_type = ""
                        formula = cached = False
                        array_ranges: list[tuple[int, int, int, int]] = []
                        array_cells = 0
                        parents = [root]
                        for event, element in events:
                            tag = element.tag.rsplit("}", 1)[-1]
                            if event == "end":
                                if collect_cell_issues:
                                    if tag == "v":
                                        cached = element.text is not None or cell_type == "str"
                                    elif tag == "is" and cell_type == "inlineStr":
                                        cached = True
                                    elif tag == "c" and (cell_type == "e" or (formula and not cached)):
                                        issues.setdefault(info.filename, []).append((cell_row, col))
                                parents.pop()
                                if parents:
                                    parents[-1].remove(element)
                                element.clear()
                                continue
                            parents.append(element)
                            if tag == "row":
                                row = int(element.get("r", str(row + 1)))
                                col = 0
                                max_row = max(max_row, row)
                            elif tag == "c":
                                cell_type = element.get("t", "n")
                                formula = cached = False
                                col += 1
                                reference = element.get("r")
                                cell_row = row
                                if reference:
                                    cell_row, col = _cell_position(reference)
                                max_row, max_col = max(max_row, cell_row), max(max_col, col)
                            elif tag == "f":
                                formula = True
                                if collect_cell_issues and element.get("t") == "array":
                                    reference = element.get("ref", "")
                                    try:
                                        ends = reference.split(":")
                                        if len(ends) not in (1, 2):
                                            raise ValueError("invalid array reference")
                                        first_row, first_col = _cell_position(ends[0])
                                        last_row, last_col = _cell_position(ends[-1])
                                        if last_row < first_row or last_col < first_col:
                                            raise ValueError("reversed array reference")
                                    except ValueError:
                                        issues.setdefault(info.filename, []).append((cell_row, col))
                                    else:
                                        area = (last_row - first_row + 1) * (last_col - first_col + 1)
                                        if area > 1:
                                            array_ranges.append((first_row, first_col, last_row, last_col))
                                            array_cells += area
                                            max_row, max_col = max(max_row, last_row), max(max_col, last_col)
                                        if array_cells > MAX_WORKBOOK_CELLS:
                                            raise WorkbookLimitError("Excel array formula ranges exceed 2,000,000 cells. Export only the used data.")
                            if cells + max_row * max_col > MAX_WORKBOOK_CELLS:
                                raise WorkbookLimitError(
                                    "Excel worksheet ranges exceed 2,000,000 cells in total, including empty gaps. "
                                    "Copy only the used data into a new workbook and try again.")
                        cells += max_row * max_col
                        if array_ranges:
                            unreadable = _array_issues(archive, info.filename, array_ranges, max_row, max_col)
                            if unreadable:
                                issues.setdefault(info.filename, []).extend(unreadable)
                except WorkbookLimitError:
                    raise
                except (BadZipFile, ParseError, StopIteration, ValueError):
                    continue  # Binary parts and malformed unrelated XML must not hide the remaining sheets.
    except BadZipFile:
        return {}  # The normal reader reports malformed workbooks using its existing error path.
    return issues
