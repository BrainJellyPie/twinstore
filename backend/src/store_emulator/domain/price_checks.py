"""Operator-supplied display / checkout observations, not a compliance verdict."""

from datetime import date
from typing import Literal
import unicodedata

from pydantic import BaseModel, Field, field_validator


def _identifier(value: str) -> str:
    if not 1 <= len(value) <= 120 or value != value.strip() or any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("Use 1–120 characters without outer whitespace or controls")
    return value


class PriceCheckScope(BaseModel):
    store_ref: str
    audit_date: date

    @field_validator("store_ref")
    @classmethod
    def identifier(cls, value: str) -> str:
        return _identifier(value)


class PriceObservation(BaseModel):
    check_id: str
    sku: str
    pack_reference: str
    checked_on: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    price_minor: int = Field(strict=True, ge=0, le=1_000_000_000_000)
    terms: Literal["public", "conditional", "unknown"]

    @field_validator("check_id", "sku", "pack_reference")
    @classmethod
    def identifier(cls, value: str) -> str:
        return _identifier(value)


type CheckFlag = Literal["missing_label", "missing_checkout", "sku_mismatch", "pack_mismatch", "currency_mismatch", "outside_audit_date", "terms_unverified"]


class PriceCheck(BaseModel):
    check_id: str
    label: PriceObservation | None
    checkout: PriceObservation | None
    flags: list[CheckFlag]
    difference_minor: int | None
    relation: Literal["checkout_higher", "checkout_lower", "equal", "unavailable"]


class PriceCheckTotals(BaseModel):
    currency: str
    comparable: int
    higher: int
    lower: int
    equal: int
    positive_difference_minor: int
    negative_difference_minor: int
    net_difference_minor: int


class PriceCheckReport(BaseModel):
    method: Literal["observed-price-checks-v1"] = "observed-price-checks-v1"
    scope: PriceCheckScope
    source_sha256: str
    label_count: int
    checkout_count: int
    excluded_count: int
    rows: list[PriceCheck]
    totals: list[PriceCheckTotals]
    notes: list[str]
