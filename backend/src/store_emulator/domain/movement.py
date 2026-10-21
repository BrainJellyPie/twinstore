"""Aggregate movement evidence; reports intentionally contain no track identifiers."""

from pydantic import BaseModel, Field


class TrackPoint(BaseModel):
    track_id: str = Field(min_length=1, max_length=80)
    x: int
    y: int
    timestamp_sec: float = Field(ge=0, le=1e12, allow_inf_nan=False)


class MovementSummary(BaseModel):
    tracks: int
    samples: int
    duplicate_samples: int
    single_point_tracks: int
    excluded_gaps: int
    excluded_seconds: float
    observed_seconds: float
    visitors: list[list[int]]
    occupancy_seconds: list[list[float]]


class MovementGap(BaseModel):
    x: int
    y: int
    observed_visit_rate: float
    simulated_visit_rate: float
    difference: float  # observed minus simulated, percentage-point gap = difference × 100


class MovementReport(BaseModel):
    grid_size: tuple[int, int]
    observed: MovementSummary
    simulated: MovementSummary
    visitation_similarity: float | None
    occupancy_similarity: float | None
    largest_gaps: list[MovementGap]
    max_gap_seconds: float
    notes: list[str]
    created_at: str = ""
