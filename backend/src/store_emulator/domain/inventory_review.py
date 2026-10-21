"""Supplied period inventory records and descriptive, explicitly defined ratios."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
import unicodedata

from pydantic import BaseModel, Field, field_validator, model_validator

type Quantity = Annotated[Decimal, Field(ge=0, le=1_000_000, max_digits=10, decimal_places=3, allow_inf_nan=False)]
type ValueAtCost = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000_000)]
type NetMoney = Annotated[int, Field(strict=True, ge=-1_000_000_000_000, le=1_000_000_000_000)]
type InventoryFlag = Literal["stock_mismatch", "negative_expected_stock", "empty_stock_value", "net_returns", "zero_supply", "zero_inventory_cost", "negative_cogs"]


class InventoryPeriod(BaseModel):
    start_date: date
    end_date: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if not 0 <= (self.end_date - self.start_date).days < 3660:
            raise ValueError("Use an inclusive period of 1 to 3660 days with end on or after start")
        return self


class InventoryInput(BaseModel):
    sku: str = Field(min_length=1, max_length=200)
    opening_units: Quantity
    received_units: Quantity
    sold_units: Quantity
    returned_units: Quantity
    other_in_units: Quantity
    other_out_units: Quantity
    closing_units: Quantity
    net_sales_minor: NetMoney
    cogs_minor: NetMoney
    opening_cost_minor: ValueAtCost
    closing_cost_minor: ValueAtCost

    @field_validator("sku")
    @classmethod
    def check_sku(cls, value: str) -> str:
        if value != value.strip() or any(unicodedata.category(c).startswith("C") for c in value):
            raise ValueError("SKU must not contain outer whitespace or control characters")
        return value


class InventoryResult(BaseModel):
    inputs: InventoryInput
    expected_closing_units: float
    difference_units: float
    net_sold_units: float
    reconciled: bool
    gross_profit_minor: int
    average_inventory_cost_minor: float
    net_sell_through: float | None
    inventory_turns: float | None
    gmroi: float | None
    flags: list[InventoryFlag]


class InventoryTotals(BaseModel):
    sku_count: int
    reconciled_skus: int
    net_sales_minor: int
    cogs_minor: int
    gross_profit_minor: int
    average_inventory_cost_minor: float
    inventory_turns: float | None
    gmroi: float | None
    ratios_withheld: bool


class InventoryReport(BaseModel):
    method: Literal["period-inventory-review-v1"] = "period-inventory-review-v1"
    period: InventoryPeriod
    period_days: int
    source_sha256: str
    rows: list[InventoryResult]
    totals: InventoryTotals
    notes: list[str]
