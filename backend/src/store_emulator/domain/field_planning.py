"""Assumptions and reproducible, baseline-free planning for fixed field pilots."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator


class PilotPlanningAssumptions(BaseModel):
    # Absolute conversion difference (0.05 = five percentage points), not relative lift.
    minimum_effect: float = Field(strict=True, ge=0.001, le=1, allow_inf_nan=False)
    target_power: float = Field(strict=True, ge=0.5, le=0.99, allow_inf_nan=False)
    eligible_per_day: float = Field(strict=True, ge=0.1, le=100_000, allow_inf_nan=False)
    available_days: int = Field(strict=True, ge=1, le=3650)


class PilotPlanningRequest(BaseModel):
    assumptions: PilotPlanningAssumptions
    block_counts: list[Annotated[int, Field(strict=True, ge=4, le=2000, multiple_of=2)]] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if not 40 <= sum(self.block_counts) <= 10_000:
            raise ValueError("Plan 40 to 10,000 encounters in total")
        return self


class PilotPlanningResult(BaseModel):
    method: Literal["hoeffding-fixed-v1"] = "hoeffding-fixed-v1"
    assumptions: PilotPlanningAssumptions
    block_counts: list[int]
    planned_encounters: int
    required_encounters: int
    planned_power_lower_bound: float
    planned_ci_half_width: float
    planned_days: int
    required_days: int
    suggested_block_counts: list[int] | None
    notes: list[str]
