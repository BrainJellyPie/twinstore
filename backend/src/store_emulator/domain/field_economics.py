"""Explicit cost assumptions applied to a completed staff-script field pilot."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

type CostMinor = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]


class PilotEconomicsRequest(BaseModel):
    revision: int = Field(strict=True, ge=0)
    currency: str = Field(min_length=3, max_length=12)
    contribution_per_conversion_minor: CostMinor
    labor_per_hour_minor: CostMinor
    seconds_per_encounter_a: int = Field(strict=True, ge=0, le=3600)
    seconds_per_encounter_b: int = Field(strict=True, ge=0, le=3600)
    eligible_encounters_per_day: int = Field(strict=True, ge=0, le=1_000_000)


class ConditionalContribution(BaseModel):
    estimate_minor: float
    low_minor: float
    high_minor: float


class PilotEconomicsReport(BaseModel):
    method: Literal["fixed-pilot-cost-scenario-v1"] = "fixed-pilot-cost-scenario-v1"
    pilot_id: str
    finalized_at: str
    target_sku: str
    planned_encounters: int
    assumptions: PilotEconomicsRequest
    conversion_difference: float
    conversion_ci_low: float
    conversion_ci_high: float
    incremental_labor_minor: float
    break_even_difference: float | None
    per_encounter: ConditionalContribution
    per_day: ConditionalContribution
    notes: list[str]
