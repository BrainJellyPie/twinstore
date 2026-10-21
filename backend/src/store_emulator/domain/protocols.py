"""Research plans and locally recorded amendment history; no outcome estimates."""

from typing import Annotated, Literal
import unicodedata

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

type PlanText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]
type DataStage = Literal["not_collected", "collected_unseen", "results_seen"]
type Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type ProtocolId = Annotated[str, StringConstraints(pattern=r"^protocol_[0-9a-f]{32}$")]


class ProtocolPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    evidence_type: Literal["synthetic", "observed"]
    question: PlanText
    population: PlanText
    design: PlanText
    primary_outcome: PlanText
    analysis_unit: PlanText
    planned_sample_size: int = Field(strict=True, ge=1, le=1_000_000)
    exclusions_and_missing: PlanText
    stopping_rule: PlanText
    analysis_plan: PlanText

    @field_validator("title", "question", "population", "design", "primary_outcome", "analysis_unit", "exclusions_and_missing", "stopping_rule", "analysis_plan")
    @classmethod
    def text(cls, value: str) -> str:
        value = value.strip()
        if not value or any(unicodedata.category(c).startswith("C") and c not in "\n\t" for c in value):
            raise ValueError("Use nonblank text without control characters except line breaks and tabs")
        return value


class CreateProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    plan: ProtocolPlan
    data_stage: DataStage


class AmendProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_head: Digest
    plan: ProtocolPlan
    data_stage: DataStage
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def text(cls, value: str) -> str:
        return ProtocolPlan.text(value)


class ProtocolRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(strict=True, ge=1, le=50)
    recorded_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=1000)
    data_stage: DataStage
    plan: ProtocolPlan
    previous_sha256: Digest | None
    sha256: Digest


class ProtocolLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format_version: Literal["protocol-ledger-v1"]
    project_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    protocol_id: ProtocolId
    revisions: list[ProtocolRevision] = Field(min_length=1, max_length=50)


class ProtocolChange(BaseModel):
    field: str
    before: str | int | None
    after: str | int


class RevisionReview(BaseModel):
    revision: int
    changes: list[ProtocolChange]


class ProtocolView(BaseModel):
    ledger: ProtocolLedger
    reviews: list[RevisionReview]
    head_sha256: str
    changed_from_original: list[str]
    planned_sample_delta: int | None
    revisions_with_results_seen: int
    notes: list[str]


class ProtocolSummary(BaseModel):
    protocol_id: str
    title: str
    revision: int
    data_stage: DataStage
    evidence_type: Literal["synthetic", "observed"]
    updated_at: AwareDatetime


class ProtocolListing(BaseModel):
    protocols: list[ProtocolSummary]
    unavailable_ids: list[str]
