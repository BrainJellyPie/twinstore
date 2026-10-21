"""Validate corrected OCR lines without calling a model or changing stored sales."""

import math
from datetime import datetime

from store_emulator.domain.receipt_review import ReceiptIssue, ReceiptReview
from store_emulator.domain.vision_inputs import ReceiptReading
from store_emulator.engine.vision_inputs import receipts_csv


def review_receipts(readings: list[ReceiptReading], products: dict[str, str], currency: str) -> ReceiptReview:
    """`products` maps SKU to name. Client-supplied match flags are never trusted."""
    issues: list[ReceiptIssue] = []
    normalized: list[ReceiptReading] = []
    ids: set[str] = set()
    currency = currency.strip().upper()

    for reading in readings:
        receipt = reading.model_copy(deep=True)
        receipt.receipt_id = receipt.receipt_id.strip()
        receipt.currency = receipt.currency.strip().upper()
        normalized.append(receipt)

        def issue(code: str, message: str, *, line: int | None = None, warning: bool = False) -> None:
            issues.append(ReceiptIssue(receipt_id=receipt.receipt_id, line_index=line,
                                       severity="warning" if warning else "error", code=code, message=message))

        if not receipt.receipt_id or receipt.receipt_id in ids:
            issue("receipt_id", "Each receipt needs a unique, nonempty ID; duplicate IDs would merge baskets.")
        ids.add(receipt.receipt_id)
        if receipt.currency != currency:
            issue("currency", f"Receipt currency must be {currency}; currency conversion is not automatic.")
        if not receipt.lines:
            issue("empty", "No product lines remain. Exclude this receipt or add its purchased products.")
        if receipt.timestamp:
            try:
                stamp = datetime.fromisoformat(receipt.timestamp)
                if len(receipt.timestamp.strip()) <= 10:
                    issue("time_missing", "Only a date was read; supply a time or clear it to omit hourly scoring.")
                elif stamp.utcoffset() is not None:
                    issue("timezone", "Use the store's local time without a timezone offset.")
            except ValueError:
                issue("timestamp", "Use a local ISO date and time, or clear the timestamp.")
        else:
            issue("time_missing", "No transaction time: this batch cannot fully validate hourly sales.", warning=True)

        subtotal = 0.0
        complete = True
        for index, line in enumerate(receipt.lines):
            line.sku = line.sku.strip()
            line.matched = line.sku in products
            if not line.matched:
                issue("sku", "Choose a product from this store or exclude the line.", line=index)
            valid_qty = math.isfinite(line.quantity) and line.quantity > 0
            if not valid_qty:
                issue("quantity", "Quantity must be a finite number greater than zero; exclude returns.", line=index)
            if any(value is not None and value < 0 for value in (line.unit_price, line.line_total)):
                issue("price", "Prices must be nonnegative; exclude refunds and payment lines.", line=index)
            if line.unit_price is None and line.line_total is None:
                issue("price_missing", "Enter a unit price or line total, including zero for a free item.", line=index)
                complete = False
            elif valid_qty:
                amount = line.line_total if line.line_total is not None else (line.unit_price or 0) * line.quantity
                if not math.isfinite(amount) or not math.isfinite(amount / line.quantity):
                    issue("amount", "The computed sales amount is too large.", line=index)
                    complete = False
                else:
                    subtotal += amount
                if line.line_total is not None and line.unit_price is not None:
                    expected = line.unit_price * line.quantity
                    if not math.isfinite(expected) or abs(expected - line.line_total) > 1:
                        issue("line_total", "Unit price × quantity differs from the line total. The line total is used for sales (including discounts).",
                              line=index, warning=True)
            else:
                complete = False
        if receipt.total is not None and receipt.total < 0:
            issue("total", "Receipt total cannot be negative.")
        if not math.isfinite(subtotal):
            issue("amount", "The receipt's sales amount is too large.")
        if complete and receipt.total is not None and abs(subtotal - receipt.total) > 1:
            issue("subtotal", "Included product lines differ from the printed total. Check omissions, tax and discounts; only included lines are scored.", warning=True)

    if not readings:
        issues.append(ReceiptIssue(receipt_id="", severity="error", code="empty", message="Include at least one receipt."))
    ready = not any(issue.severity == "error" for issue in issues)
    return ReceiptReview(receipts=normalized, issues=issues, ready=ready,
                         included_lines=sum(len(r.lines) for r in normalized), currency=currency,
                         csv=receipts_csv(normalized) if ready else "")
