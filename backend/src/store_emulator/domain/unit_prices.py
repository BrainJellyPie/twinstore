"""Operator-supplied offers and descriptive comparisons; no inferred demand."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
import unicodedata

from pydantic import BaseModel, Field, field_validator, model_validator


def checked_label(value: str) -> str:
    if not 1 <= len(value) <= 120 or value != value.strip() or any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("Identifiers need 1–120 characters without outer whitespace or control characters")
    return value


class PriceScope(BaseModel):
    focal_retailer: str
    as_of: date
    max_age_days: int = Field(ge=0, le=365)

    @field_validator("focal_retailer")
    @classmethod
    def label(cls, value: str) -> str:
        return checked_label(value)


class ObservedOffer(BaseModel):
    offer_id: str
    comparison_group: str
    retailer: str
    observed_on: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    pack_count: int = Field(strict=True, ge=1, le=1000)
    quantity_per_pack: Annotated[Decimal, Field(gt=0, le=1_000_000, max_digits=10, decimal_places=3, allow_inf_nan=False)]
    unit: Literal["g", "kg", "ml", "l", "item"]
    price_minor: int = Field(strict=True, ge=0, le=1_000_000_000_000)
    availability: Literal["in_stock", "out_of_stock", "unknown"]
    terms: Literal["public", "conditional"]

    @field_validator("offer_id", "comparison_group", "retailer")
    @classmethod
    def label(cls, value: str) -> str:
        return checked_label(value)


    @model_validator(mode="after")
    def whole_items(self) -> Self:
        if self.unit == "item" and self.quantity_per_pack != self.quantity_per_pack.to_integral_value():
            raise ValueError("Item quantities must be whole counts; use mass or volume units for divisible goods")
        return self


type PriceFlag = Literal["future", "stale", "out_of_stock", "unknown_availability", "conditional_offer"]
type PriceBasis = Literal["kg", "l", "item"]


class OfferReview(BaseModel):
    inputs: ObservedOffer
    basis: PriceBasis
    quantity_in_basis: str
    unit_price_minor: str
    unit_price_exact: str
    flags: list[PriceFlag]


class PriceComparison(BaseModel):
    comparison_group: str
    currency: str
    basis: PriceBasis
    focal_count: int
    competitor_count: int
    competitor_retailers: int
    focal_min_minor: str | None
    competitor_min_minor: str | None
    gap_minor: str | None
    gap_exact: str | None
    gap_percent: str | None
    relation: Literal["below", "equal", "above", "unavailable"]
    focal_offer_ids: list[str]
    competitor_offers: list[tuple[str, str]]


class UnitPriceReport(BaseModel):
    method: Literal["observed-unit-prices-v1"] = "observed-unit-prices-v1"
    scope: PriceScope
    source_sha256: str
    rows: list[OfferReview]
    comparisons: list[PriceComparison]
    notes: list[str]
