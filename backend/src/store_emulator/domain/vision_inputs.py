"""Inputs read off photos: how inviting a storefront looks, and what a receipt says was bought."""

from typing import Literal

from pydantic import BaseModel, Field

MAX_RECEIPT_AMOUNT = 9_007_199_254_740_991  # minor units, browser-safe integers


class StorefrontAppeal(BaseModel):
    method: Literal["vlm", "image_stats"]
    model: str = ""
    signage: float = Field(ge=0, le=10)      # a visible, legible sign from the street
    entrance: float = Field(ge=0, le=10)     # open, inviting, easy to walk into
    window: float = Field(ge=0, le=10)       # products or a lit interior visible from outside
    upkeep: float = Field(ge=0, le=10)       # bright, clean, well kept
    overall: float = Field(ge=0, le=10)
    attractiveness: float = Field(gt=0)      # Huff pull of the venue (1.0 = typical)
    reasons: str = ""


class ReceiptLine(BaseModel):
    name: str
    quantity: float = Field(default=1.0, allow_inf_nan=False)
    unit_price: int | None = Field(default=None, ge=-MAX_RECEIPT_AMOUNT, le=MAX_RECEIPT_AMOUNT)
    line_total: int | None = Field(default=None, ge=-MAX_RECEIPT_AMOUNT, le=MAX_RECEIPT_AMOUNT)
    sku: str = ""                            # the store's SKU when the name matches one of its products
    matched: bool = False


class ReceiptReading(BaseModel):
    receipt_id: str
    store: str = ""
    timestamp: str = ""                      # ISO date-time as printed (may be date only)
    currency: str = ""
    lines: list[ReceiptLine] = []
    total: int | None = Field(default=None, ge=-MAX_RECEIPT_AMOUNT, le=MAX_RECEIPT_AMOUNT)
    notes: list[str] = []
