"""Bound spreadsheet expansion before pandas materializes a dense table."""

import io
import re
from xml.etree.ElementTree import ParseError, iterparse
from zipfile import BadZipFile, ZipFile

MAX_WORKBOOK_BYTES = 100 * 1024 * 1024
MAX_WORKBOOK_CELLS = 2_000_000
_CELL_REFERENCE = re.compile(r"([A-Za-z]{1,3})([0-9]+)\Z")


class WorkbookLimitError(ValueError):
    """The compressed file fits the upload limit but its expanded tables do not."""


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
                                    match = _CELL_REFERENCE.fullmatch(reference)
                                    if match is None:
                                        raise ValueError("invalid cell reference")
                                    cell_row = int(match[2])
                                    col = 0
                                    for letter in match[1].upper():
                                        col = col * 26 + ord(letter) - ord("A") + 1
                                max_row, max_col = max(max_row, cell_row), max(max_col, col)
                            elif tag == "f":
                                formula = True
                            if cells + max_row * max_col > MAX_WORKBOOK_CELLS:
                                raise WorkbookLimitError(
                                    "Excel worksheet ranges exceed 2,000,000 cells in total, including empty gaps. "
                                    "Copy only the used data into a new workbook and try again.")
                        cells += max_row * max_col
                except WorkbookLimitError:
                    raise
                except (BadZipFile, ParseError, StopIteration, ValueError):
                    continue  # Binary parts and malformed unrelated XML must not hide the remaining sheets.
    except BadZipFile:
        return {}  # The normal reader reports malformed workbooks using its existing error path.
    return issues
