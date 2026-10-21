"""Operator-entered quantities and costs for a budgeted restocking worksheet."""

from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

type Units = Annotated[int, Field(strict=True, ge=0, le=1_000_000)]
type Money = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000_000)]


class RestockOrderItem(BaseModel):
    sku: str = Field(min_length=1, max_length=200)
    required_units: Units
    stockroom_units: Units
    pack_size: int = Field(strict=True, ge=1, le=1_000_000)
    pack_cost_minor: Money
    max_packs: Units
    priority: int = Field(strict=True, ge=1, le=1000)


class RestockOrderRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=12)
    budget_minor: Money
    delivery_fee_minor: Money = 0
    items: list[RestockOrderItem] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_skus(self) -> Self:
        if len({item.sku for item in self.items}) != len(self.items):
            raise ValueError("Enter each SKU once across all shelf levels")
        return self


class RestockOrderAction(BaseModel):
    item: RestockOrderItem
    name: str
    levels: list[int]
    stockroom_used: int
    packs_needed: int
    packs_ordered: int
    units_ordered: int
    surplus_units: int
    unfilled_units: int
    cost_minor: int
    supplier_limited: bool
    budget_limited: bool


class RestockOrderPlan(BaseModel):
    audit_id: str
    capture_id: str
    setup_id: str
    rack_id: str
    face: str
    currency: str
    budget_minor: int
    delivery_fee_minor: int
    delivery_charged_minor: int
    goods_cost_minor: int
    total_cost_minor: int
    remaining_budget_minor: int
    omitted_skus: list[str]
    unidentified_findings: int
    actions: list[RestockOrderAction]
    notes: list[str]
