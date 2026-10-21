"""Reviewable changes and committed import records for field observations."""

from typing import Literal

from pydantic import BaseModel

from store_emulator.domain.staff_pitch import Arm

type ObservationField = Literal["enrolled", "delivered", "purchased"]


class ObservationChange(BaseModel):
    assignment_id: str
    staff_id: str
    shift_id: str
    sequence: int
    arm: Arm
    field: ObservationField
    before: bool | None
    after: bool | None


class ObservationDiff(BaseModel):
    changed_assignments: int
    changed_fields: int
    new_values: int
    corrected_values: int
    cleared_values: int
    removed_enrollments: int
    purchase_reversals: int


class ObservationPreview(BaseModel):
    pilot_id: str
    revision: int
    review_token: str
    summary: ObservationDiff
    changes: list[ObservationChange]


class ObservationImportRecord(BaseModel):
    revision: int
    imported_at: str
    reason: str
    source_sha256: str
    summary: ObservationDiff


class ObservationImportAudit(BaseModel):
    record: ObservationImportRecord
    changes: list[ObservationChange]
