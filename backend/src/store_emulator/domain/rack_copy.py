"""Reuse exact slot assortments without replacing existing products."""
from typing import Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from store_emulator.domain.rack import Slot


class RackCopyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_rack_id: str = Field(min_length=1, max_length=200)
    target_rack_ids: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def targets(self) -> Self:
        if any(not value or len(value) > 200 for value in self.target_rack_ids):
            raise ValueError("Choose valid destination rack identifiers")
        if len(set(self.target_rack_ids)) != len(self.target_rack_ids):
            raise ValueError("Choose each destination only once")
        if self.source_rack_id in self.target_rack_ids:
            raise ValueError("The source cannot also be a destination")
        return self


class RackCopySave(RackCopyRequest):
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class RackCopyChoice(BaseModel):
    id: str
    name: str
    type: str
    placements: int
    reason: str | None = None


class RackCopyOptions(BaseModel):
    source_sha256: str
    currency: str
    source_rack_id: str | None = None
    sources: list[RackCopyChoice]
    targets: list[RackCopyChoice]


class RackCopyPreview(BaseModel):
    source_name: str
    slots: list[Slot]
    targets: list[RackCopyChoice]
    placements_added: int


class RackCopySaved(BaseModel):
    setup_id: str
    placements_added: int


class RackCopyRecord(BaseModel):
    rack_copy_request: RackCopySave
    rack_copy_result: RackCopySaved
