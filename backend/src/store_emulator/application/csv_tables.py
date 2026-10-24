"""Validate CSV tables before a reader allocates their rectangular representation."""

import csv
import io

# Allow long quoted fields within the largest supported CSV upload (POS, 50 MB).
csv.field_size_limit(max(csv.field_size_limit(), 50 * 1024 * 1024))


class CsvError(ValueError):
    pass


class CsvLimitError(CsvError):
    pass


def validate_csv_table(text: str, delimiter: str, *, label: str, max_cells: int) -> None:
    if "\0" in text:
        raise CsvError(f"{label} contains NUL characters that can truncate fields. Re-export the file as a text CSV.")
    columns = rows = 0
    try:
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True):
            if not columns:
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue
                columns = len(row)
            else:
                rows += 1
                if len(row) > columns:
                    raise CsvError(
                        f"{label} rows have more fields than the header; quote values containing separators."
                    )
            if columns * max(1, rows) > max_cells:
                raise CsvLimitError(
                    f"{label} exceeds {max_cells:,} cells, including missing fields in short rows."
                )
    except csv.Error as exc:
        raise CsvError(f"{label} has invalid quoting or fields: {exc}") from exc
    if not columns:
        raise CsvError(f"{label} is empty or has no column header.")
