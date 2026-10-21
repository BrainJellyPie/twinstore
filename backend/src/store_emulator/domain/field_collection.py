"""Outcome-free collection diagnostics and follow-up tasks for a fixed field pilot."""

from typing import Literal

from pydantic import BaseModel

from store_emulator.domain.staff_pitch import Arm

type CollectionIssue = Literal["purchase_unknown", "delivery_unknown", "enrollment_gap", "unused_before_enrolled"]


class CollectionCounts(BaseModel):
    planned: int
    enrolled: int
    unused: int
    unrecorded: int
    complete_enrolled: int
    missing_purchase: int
    missing_delivery: int
    known_delivery: int
    not_delivered: int
    purchase_missing_rate: float | None
    non_delivery_rate: float | None


class CollectionBlock(BaseModel):
    staff_id: str
    shift_id: str
    counts: CollectionCounts
    a: CollectionCounts
    b: CollectionCounts
    last_recorded_sequence: int | None
    recording_gaps: int
    unused_before_enrolled: int
    unrecorded_tail: int
    purchase_missing_gap: float | None


class CollectionTask(BaseModel):
    assignment_id: str
    staff_id: str
    shift_id: str
    sequence: int
    arm: Arm
    issues: list[CollectionIssue]


class CollectionGuidance(BaseModel):
    issue: CollectionIssue
    title: str
    action: str


class PilotCollectionReport(BaseModel):
    pilot_id: str
    name: str
    revision: int
    updated_at: str
    finalized_at: str
    outcome_window: str
    counts: CollectionCounts
    recording_gaps: int
    unused_before_enrolled: int
    unrecorded_tail: int
    can_finalize: bool
    target_completed: bool
    blocks: list[CollectionBlock]
    tasks: list[CollectionTask]
    guidance: list[CollectionGuidance]
    notes: list[str]
