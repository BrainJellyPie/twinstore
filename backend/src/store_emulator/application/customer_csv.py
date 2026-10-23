"""Validate customer CSV structure before allocating a rectangular dataframe."""

import codecs
import csv
import io

MAX_CUSTOMER_CSV_BYTES = 10 * 1024 * 1024
MAX_CUSTOMER_CSV_CELLS = 2_000_000
# Python's default 128 KiB field limit would reject otherwise supported long notes.
csv.field_size_limit(max(csv.field_size_limit(), MAX_CUSTOMER_CSV_BYTES))


class CustomerCsvError(ValueError):
    pass


class CustomerCsvLimitError(CustomerCsvError):
    pass


def validate_customer_csv(data: bytes) -> tuple[str, str]:
    """Return decoded text and separator after checking column alignment and cell budget."""
    if len(data) > MAX_CUSTOMER_CSV_BYTES:
        raise CustomerCsvLimitError("Customer CSV exceeds the 10 MB upload limit.")
    try:
        if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            text = data.decode("utf-32")
        elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            text = data.decode("utf-16")
        else:
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = data.decode("cp949")
    except UnicodeError as exc:
        raise CustomerCsvError("Customer CSV text could not be decoded; use UTF-8, Unicode or Korean Excel CSV.") from exc

    try:
        delimiter = csv.Sniffer().sniff(text[:65536], delimiters=",;\t").delimiter
    except csv.Error:
        # Unequal record widths defeat Sniffer; retain the header's separator so
        # malformed semicolon/tab exports do not masquerade as one-column notes.
        header = next((line for line in io.StringIO(text) if line.strip()), "")
        try:
            delimiter = csv.Sniffer().sniff(header, delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","

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
                    raise CustomerCsvError(
                        "Customer CSV rows have more fields than the header; quote values containing separators."
                    )
            if columns * max(1, rows) > MAX_CUSTOMER_CSV_CELLS:
                raise CustomerCsvLimitError(
                    "Customer CSV exceeds 2,000,000 cells, including missing fields in short rows."
                )
    except csv.Error as exc:
        raise CustomerCsvError(f"Customer CSV has invalid quoting or fields: {exc}") from exc
    if not columns:
        raise CustomerCsvError("Customer CSV is empty or has no column header.")
    return text, delimiter
