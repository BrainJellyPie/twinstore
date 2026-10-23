"""Validate customer CSV structure before allocating a rectangular dataframe."""

import codecs
import csv
import io

from store_emulator.application.csv_tables import (
    CsvError as CustomerCsvError,
    CsvLimitError as CustomerCsvLimitError,
    validate_csv_table,
)

MAX_CUSTOMER_CSV_BYTES = 10 * 1024 * 1024
MAX_CUSTOMER_CSV_CELLS = 2_000_000


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

    validate_csv_table(text, delimiter, label="Customer CSV", max_cells=MAX_CUSTOMER_CSV_CELLS)
    return text, delimiter
