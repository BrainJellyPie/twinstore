"""Descriptive group deletion diagnostics for a completed, locked field pilot."""

from typing import Literal

from pydantic import BaseModel

type SensitivityScope = Literal["staff", "shift", "block"]


class GroupDeletion(BaseModel):
    scope: SensitivityScope
    staff_id: str
    shift_id: str
    removed_blocks: int
    removed_encounters: int
    removed_weight: float
    remaining_encounters: int
    difference: float | None
    change: float | None
    opposite_sign: bool | None


class SensitivitySummary(BaseModel):
    scope: SensitivityScope
    groups: int
    estimable: int
    minimum: float | None
    maximum: float | None
    max_absolute_change: float | None
    opposite_sign_count: int


class PilotSensitivityReport(BaseModel):
    method: Literal["fixed-block-deletion-v1"] = "fixed-block-deletion-v1"
    pilot_id: str
    revision: int
    finalized_at: str
    target_sku: str
    planned_encounters: int
    blocks: int
    difference: float
    groups: list[GroupDeletion]
    summaries: list[SensitivitySummary]
    notes: list[str]
