"""POS (point-of-sale) export parsing for fidelity evaluation.

Real exports differ in column names, so common aliases are accepted
(case-insensitive). Required: a transaction id and a SKU. Optional: quantity,
unit price (or line total), and a timestamp/hour column.
"""

import io
from collections.abc import Callable
from datetime import date, datetime, time
from functools import lru_cache

import pandas as pd  # type: ignore[reportMissingTypeStubs]
from dateutil.parser import parse as parse_date

from store_emulator.engine.analysis.fidelity import PosLine

_ALIASES: dict[str, tuple[str, ...]] = {
    "transaction_id": ("transaction_id", "receipt_id", "basket_id", "order_id", "trans_id", "invoice", "invoice_no"),
    "sku": ("sku", "product_id", "item_id", "product_code", "barcode", "upc", "ean"),
    "quantity": ("quantity", "qty", "units", "amount", "count"),
    "unit_price": ("unit_price", "price", "unit_cost"),
    "line_total": ("line_total", "sales_value", "sales", "total", "revenue"),
    "timestamp": ("timestamp", "datetime", "transaction_datetime", "date_time", "time", "trans_time"),
    "hour": ("hour", "order_hour_of_day", "hour_of_day"),
    "date": ("date", "transaction_date", "receipt_date", "order_date", "business_date", "sales_date"),
}

_RECEIPT_SCOPE_COLUMNS = {root + suffix for root in ("store", "shop", "branch", "register", "terminal", "till", "pos")
                          for suffix in ("", "id", "no", "num", "number", "code")}

MAX_POS_BYTES = 50 * 1024 * 1024


def parse_pos_csv(data: bytes, filename: str = "pos.csv") -> list[PosLine]:
    if len(data) > MAX_POS_BYTES:
        raise ValueError(f"POS file too large ({len(data) // (1024 * 1024)} MB > 50 MB)")
    buf = io.BytesIO(data)
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(buf, dtype=object, keep_default_na=False)  # type: ignore[reportUnknownMemberType]
    else:
        try:
            df = pd.read_csv(buf, dtype=str, encoding="utf-8-sig", keep_default_na=False)  # type: ignore[reportUnknownMemberType]
        except UnicodeDecodeError:
            buf.seek(0)
            df = pd.read_csv(buf, dtype=str, encoding="cp949", keep_default_na=False)  # type: ignore[reportUnknownMemberType]
    # Surplus CSV fields can make pandas infer an index and shift every named column.
    if not isinstance(df.index, pd.RangeIndex):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]  # pandas stubs
        raise ValueError("POS CSV rows have more fields than the header; quote values containing commas.")
    columns: list[str] = [str(c) for c in df.columns]  # type: ignore[reportUnknownVariableType, reportUnknownArgumentType]  # pandas stubs
    lower = {c.strip().lower(): c for c in columns}
    scope_columns = [("".join(char for char in c.lower() if char.isalnum()), c) for c in columns]
    scope_columns = sorted((label, col) for label, col in scope_columns if label in _RECEIPT_SCOPE_COLUMNS)
    cols: dict[str, str] = {}
    for key, names in _ALIASES.items():
        for name in names:
            if name in lower:
                cols[key] = lower[name]
                break
    missing = [k for k in ("transaction_id", "sku") if k not in cols]
    if missing:
        raise ValueError(
            f"POS file needs columns for {', '.join(missing)}; accepted names: "
            + "; ".join(f"{k}: {', '.join(_ALIASES[k])}" for k in missing)
        )

    @lru_cache(maxsize=4096)
    def parse_timestamp(text: str) -> tuple[date | None, int | None]:
        # Receipt product lines repeat timestamps; bound retained values to this import's recent clocks.
        try:
            # Different defaults reveal omitted calendar parts or clocks without guessing from punctuation.
            # Both defaults support February 29 and every day-of-month, including partial dates.
            first = parse_date(text, default=datetime(2000, 1, 1, 3))
            second = parse_date(text, default=datetime(2004, 3, 2, 17))
        except (ValueError, OverflowError):
            return None, None
        return (first.date() if first.date() == second.date() else None,
                first.hour if first.hour == second.hour else None)

    lines: list[PosLine] = []
    for raw in df.to_dict(orient="records"):  # type: ignore[reportUnknownMemberType]
        source: dict[str, object] = {str(k): v for k, v in raw.items() if v is not None}  # type: ignore[reportUnknownVariableType]
        row = {k: str(v) for k, v in source.items()}
        tx, sku = row.get(cols["transaction_id"], "").strip(), row.get(cols["sku"], "").strip()
        if not tx or not sku:
            continue
        scope = [(label, row.get(col, "").strip()) for label, col in scope_columns]
        for kind in ("timestamp", "date"):
            text = row.get(cols.get(kind, ""), "").strip()
            if not text:
                continue
            stamp, _ = parse_timestamp(text)
            if stamp is not None:
                scope.append(("date", str(stamp)))
                break
        qty = _num(row.get(cols.get("quantity", ""), ""), 1.0)
        if "unit_price" in cols and row.get(cols["unit_price"], "").strip():
            price = _num(row.get(cols["unit_price"], ""), 0.0)
        elif "line_total" in cols:
            total = _num(row.get(cols["line_total"], ""), 0.0)
            if qty == 0 and total != 0:
                raise ValueError("POS line total must be zero when quantity is zero; a unit price cannot be derived.")
            price = total / qty if qty else 0.0
        else:
            price = 0.0
        lines.append(PosLine(transaction_id=tx, transaction_scope=tuple(scope), sku=sku,
                             quantity=qty, unit_price=price,
                             hour=_hour(row, cols, source.get(cols.get("timestamp", "")), parse_timestamp)))
    if not lines:
        raise ValueError("POS file contains no usable rows")
    return lines


def _num(text: str, default: float) -> float:
    if not text.strip():
        return default
    try:
        return float(text.replace(",", ""))
    except ValueError:
        raise ValueError(f"Invalid numeric POS value: {text!r}") from None


def _hour(row: dict[str, str], cols: dict[str, str], timestamp: object,
          parse_timestamp: Callable[[str], tuple[date | None, int | None]]) -> int | None:
    if "hour" in cols and row.get(cols["hour"]):
        try:
            value = _num(row[cols["hour"]], -1)
        except ValueError:
            return None
        return int(value) if 0 <= value < 24 else None
    if "timestamp" in cols and row.get(cols["timestamp"]):
        text = row[cols["timestamp"]].strip()
        if text.isdigit() and len(text) in (3, 4):  # HHMM, e.g. dunnhumby TRANS_TIME
            hour, minute = divmod(int(text), 100)
            return hour if hour < 24 and minute < 60 else None
        # Excel date-only cells become midnight datetimes; textual midnight or an explicit hour is unambiguous.
        if isinstance(timestamp, date) and (not isinstance(timestamp, datetime) or timestamp.time() == time(0)):
            return None
        _, hour = parse_timestamp(text)
        return hour
    return None
