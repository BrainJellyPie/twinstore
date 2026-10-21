"""Precommitted, blocked field pilots of two saved employee scripts."""

from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from store_emulator.domain.field_observations import ObservationImportRecord
from store_emulator.domain.field_planning import PilotPlanningAssumptions, PilotPlanningResult
from store_emulator.domain.staff_pitch import Arm, PitchProduct, PitchVariant

type Alias = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")]
type RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]


class PilotBlock(BaseModel):
    staff_id: Alias
    shift_id: Alias
    encounters: int = Field(strict=True, ge=4, le=2000, multiple_of=2)


class PilotRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    eligibility: RequiredText
    outcome_window: RequiredText
    blocks: list[PilotBlock] = Field(min_length=1, max_length=30)
    seed: int = Field(default=1, strict=True, ge=0, le=2_147_483_647)
    planning: PilotPlanningAssumptions | None = None

    @model_validator(mode="after")
    def validate_design(self) -> Self:
        keys = [(b.staff_id, b.shift_id) for b in self.blocks]
        if len(set(keys)) != len(keys):
            raise ValueError("Each staff and shift pair must appear once")
        if not 40 <= sum(b.encounters for b in self.blocks) <= 10000:
            raise ValueError("Plan 40 to 10,000 encounters in total")
        return self


class PilotAssignment(BaseModel):
    assignment_id: str
    staff_id: str
    shift_id: str
    sequence: int
    arm: Arm
    enrolled: bool | None = None
    delivered: bool | None = None
    purchased: bool | None = None


class FieldPilot(BaseModel):
    pilot_id: str
    pitch_id: str
    created_at: str
    updated_at: str
    finalized_at: str = ""
    revision: int = 0
    design: PilotRequest
    product: PitchProduct
    variants: tuple[PitchVariant, PitchVariant]
    context: str
    product_facts: str
    assignments: list[PilotAssignment]
    planning: PilotPlanningResult | None = None
    history_start_revision: int | None = None
    import_history: list[ObservationImportRecord] = Field(default_factory=list[ObservationImportRecord])


class PilotArmSummary(BaseModel):
    arm: Arm
    planned: int
    enrolled: int
    unused: int
    unrecorded: int
    observed: int
    purchases: int
    missing_outcomes: int
    not_delivered: int
    delivery_unknown: int
    observed_rate: float | None
    missing_bound_low: float | None
    missing_bound_high: float | None


class PilotBlockSummary(BaseModel):
    staff_id: str
    shift_id: str
    a: PilotArmSummary
    b: PilotArmSummary
    observed_diff: float | None


class PilotAnalysis(BaseModel):
    a: PilotArmSummary
    b: PilotArmSummary
    blocks: list[PilotBlockSummary]
    target_completed: bool
    can_finalize: bool
    inference_ready: bool
    difference: float | None
    ci_low: float | None
    ci_high: float | None
    interpretation: str
    notes: list[str]


class PilotView(BaseModel):
    pilot: FieldPilot
    analysis: PilotAnalysis


class PilotSummary(BaseModel):
    pilot_id: str
    pitch_id: str
    name: str
    created_at: str
    finalized_at: str
    planned: int
    enrolled: int


class PilotRevision(BaseModel):
    revision: int = Field(strict=True, ge=0)
