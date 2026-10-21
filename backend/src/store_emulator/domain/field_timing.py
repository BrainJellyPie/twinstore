"""Anonymous observed staff time, separate from purchase outcomes and cost assumptions."""

from typing import Literal

from pydantic import BaseModel

from store_emulator.domain.staff_pitch import Arm


class TimingRow(BaseModel):
    assignment_id: str
    staff_id: str
    shift_id: str
    arm: Arm
    staff_seconds: float | None


class TimingArm(BaseModel):
    arm: Arm
    planned: int
    timed: int
    mean_seconds: float | None
    max_seconds: float | None


class TimingBlock(BaseModel):
    staff_id: str
    shift_id: str
    planned: int
    timed: int


class PilotTimingReport(BaseModel):
    method: Literal["assigned-encounter-time-v1"] = "assigned-encounter-time-v1"
    pilot_id: str
    revision: int
    source_sha256: str
    source_rows: int
    complete: bool
    planned: int
    timed: int
    a: TimingArm
    b: TimingArm
    difference_seconds: float | None
    blocks: list[TimingBlock]
    rows: list[TimingRow]
    notes: list[str]
