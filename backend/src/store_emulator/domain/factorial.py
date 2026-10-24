"""Minimal paired synthetic outcomes and exploratory price × sign contrasts."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from store_emulator.domain.marketing import ExperimentRequest, VariantChange
from store_emulator.domain.types import ResourceId

type Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
type ArmName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
type OutcomeMetric = Literal["spend", "units", "bought"]


class PairedOutcome(BaseModel):
    persona_id: str = Field(min_length=1, pattern=r"\S")
    spend: int = Field(strict=True, ge=0, le=1_000_000_000_000)
    units: int = Field(strict=True, ge=0, le=1_000_000_000)
    bought: bool = Field(strict=True)

    @model_validator(mode="after")
    def check_purchase(self) -> Self:
        if self.bought != (self.units > 0) or (not self.bought and self.spend != 0):
            raise ValueError("Inconsistent purchase indicator, units and spend")
        return self


class PairedArm(BaseModel):
    name: ArmName
    store_sha256: Digest
    warnings: list[str] = []
    outcomes: list[PairedOutcome] = Field(max_length=3000)


class PairedSnapshot(BaseModel):
    version: Literal[1] = 1
    experiment_id: ResourceId
    currency: str = Field(min_length=1, max_length=16)
    request: ExperimentRequest
    panel_ids: list[str] = Field(min_length=1, max_length=3000)
    arms: list[PairedArm] = Field(min_length=2, max_length=7)

    @model_validator(mode="after")
    def check_identity(self) -> Self:
        if any(not identifier.strip() for identifier in self.panel_ids):
            raise ValueError("Sampled shopper identities must not be blank")
        ids = set(self.panel_ids)
        if len(ids) != len(self.panel_ids):
            raise ValueError("Duplicate sampled shopper identity")
        if len(ids) > self.request.panel:
            raise ValueError("Sample exceeds the requested panel")
        if [a.name for a in self.arms] != ["Control", *[v.name for v in self.request.variants]]:
            raise ValueError("Snapshot arms do not match the saved request")
        for arm in self.arms:
            observed = [r.persona_id for r in arm.outcomes]
            if len(set(observed)) != len(observed) or not set(observed) <= ids:
                raise ValueError("Duplicate or foreign shopper outcome")
        return self


class FactorialRequest(BaseModel):
    source_sha256: Digest
    price_arm: ArmName
    sign_arm: ArmName
    combined_arm: ArmName
    metric: OutcomeMetric

    @model_validator(mode="after")
    def distinct_arms(self) -> Self:
        names = [self.price_arm.casefold(), self.sign_arm.casefold(), self.combined_arm.casefold()]
        if len(set(names)) != 3 or "control" in names:
            raise ValueError("Choose three distinct non-control arms")
        return self


class FactorialSource(BaseModel):
    available: bool
    reason: str = ""
    source_sha256: str = ""
    price_arms: list[str] = []
    sign_arms: list[str] = []
    combined_arms: list[str] = []


class FactorialCell(BaseModel):
    cell: str
    arm: str
    available: int
    mean: float | None
    changes: list[VariantChange]


class FactorialContrast(BaseModel):
    name: str
    formula: str
    estimate: float | None
    ci_low: float | None
    ci_high: float | None


class FactorialRow(BaseModel):
    persona_id: str
    complete: bool
    values: list[float | None]


class FactorialReport(BaseModel):
    method: Literal["paired-price-sign-v1"] = "paired-price-sign-v1"
    experiment_id: str
    request: FactorialRequest
    currency: str
    engine: str
    model: str
    simulation_seed: int
    requested_panel: int
    sampled_panel: int
    complete_panel: int
    intervals_available: bool
    bootstrap_resamples: int = 4000
    bootstrap_seed: int = 0
    family_size: int = 3
    cells: list[FactorialCell]
    contrasts: list[FactorialContrast]
    rows: list[FactorialRow]
    notes: list[str]
