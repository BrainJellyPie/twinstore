"""Reviewable POS evidence for fixed staff-script field assignments."""

from typing import Literal

from pydantic import BaseModel

type PosMatchStatus = Literal[
    "proposed_purchase", "already_recorded", "conflicting_purchase", "not_enrolled",
    "no_target_evidence", "unknown_assignment", "unlinked",
]


class PosMatch(BaseModel):
    assignment_id: str
    transaction_ids: list[str]
    target_units: float
    status: PosMatchStatus
    staff_id: str | None
    shift_id: str | None
    sequence: int | None


class PilotPosPreview(BaseModel):
    pilot_id: str
    revision: int
    target_sku: str
    outcome_window: str
    source_sha256: str
    source_rows: int
    transactions: int
    linked_assignments: int
    enrolled_without_evidence: int
    proposed_purchases: int
    matches: list[PosMatch]
    candidate_csv: str
    notes: list[str]
