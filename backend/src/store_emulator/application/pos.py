"""POS (point-of-sale) export parsing for fidelity evaluation.

Real exports differ in column names, so common aliases are accepted
(case-insensitive). Required: a transaction id and a SKU. Optional: quantity,
unit price (or line total), and a timestamp/hour column.
"""

import io

import pandas as pd  # type: ignore[reportMissingTypeStubs]

from store_emulator.engine.analysis.fidelity import PosLine

_ALIASES: dict[str, tuple[str, ...]] = {
    "transaction_id": ("transaction_id", "receipt_id", "basket_id", "order_id", "trans_id", "invoice", "invoice_no"),
    "sku": ("sku", "product_id", "item_id", "product_code", "barcode", "upc", "ean"),
    "quantity": ("quantity", "qty", "units", "amount", "count"),
    "unit_price": ("unit_price", "price", "unit_cost"),
    "line_total": ("line_total", "sales_value", "sales", "total", "revenue"),
    "timestamp": ("timestamp", "datetime", "transaction_datetime", "date_time", "time", "trans_time"),
    "hour": ("hour", "order_hour_of_day", "hour_of_day"),
}

MAX_POS_BYTES = 50 * 1024 * 1024


def parse_pos_csv(data: bytes, filename: str = "pos.csv") -> list[PosLine]:
    if len(data) > MAX_POS_BYTES:
        raise ValueError(f"POS file too large ({len(data) // (1024 * 1024)} MB > 50 MB)")
    buf = io.BytesIO(data)
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(buf, dtype=str, keep_default_na=False)  # type: ignore[reportUnknownMemberType]
    else:
        try:
            df = pd.read_csv(buf, dtype=str, encoding="utf-8-sig", keep_default_na=False)  # type: ignore[reportUnknownMemberType]
        except UnicodeDecodeError:
            buf.seek(0)
            df = pd.read_csv(buf, dtype=str, encoding="cp949", keep_default_na=False)  # type: ignore[reportUnknownMemberType]
    columns: list[str] = [str(c) for c in df.columns]  # type: ignore[reportUnknownVariableType, reportUnknownArgumentType]  # pandas stubs
    lower = {c.strip().lower(): c for c in columns}
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

    lines: list[PosLine] = []
    for raw in df.to_dict(orient="records"):  # type: ignore[reportUnknownMemberType]
        row: dict[str, str] = {str(k): str(v) for k, v in raw.items() if v is not None}  # type: ignore[reportUnknownVariableType]
        tx, sku = row.get(cols["transaction_id"], "").strip(), row.get(cols["sku"], "").strip()
        if not tx or not sku:
            continue
        qty = _num(row.get(cols.get("quantity", ""), ""), 1.0)
        if "unit_price" in cols:
            price = _num(row.get(cols["unit_price"], ""), 0.0)
        elif "line_total" in cols:
            price = _num(row.get(cols["line_total"], ""), 0.0) / qty if qty else 0.0
        else:
            price = 0.0
        lines.append(PosLine(transaction_id=tx, sku=sku, quantity=qty, unit_price=price, hour=_hour(row, cols)))
    if not lines:
        raise ValueError("POS file contains no usable rows")
    return lines


def _num(text: str, default: float) -> float:
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return default


def _hour(row: dict[str, str], cols: dict[str, str]) -> int | None:
    if "hour" in cols and row.get(cols["hour"]):
        value = _num(row[cols["hour"]], -1)
        return int(value) if 0 <= value < 24 else None
    if "timestamp" in cols and row.get(cols["timestamp"]):
        text = row[cols["timestamp"]].strip()
        if text.isdigit() and len(text) in (3, 4):  # HHMM, e.g. dunnhumby TRANS_TIME
            hour, minute = divmod(int(text), 100)
            return hour if hour < 24 and minute < 60 else None
        ts = pd.to_datetime(text, errors="coerce")  # type: ignore[reportUnknownMemberType]
        if not pd.isna(ts):  # type: ignore[reportUnknownMemberType]
            return int(ts.hour)  # type: ignore[reportUnknownMemberType]
    return None
