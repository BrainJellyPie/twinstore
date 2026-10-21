"""A reviewable receipt batch before it becomes sales-validation evidence."""

from typing import Literal

from pydantic import BaseModel

from store_emulator.domain.vision_inputs import ReceiptReading


class ReceiptIssue(BaseModel):
    receipt_id: str
    line_index: int | None = None
    severity: Literal["error", "warning"]
    code: str
    message: str


class ReceiptReview(BaseModel):
    receipts: list[ReceiptReading]
    issues: list[ReceiptIssue]
    ready: bool
    included_lines: int
    currency: str
    csv: str = ""
