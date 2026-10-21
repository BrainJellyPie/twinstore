"""Preview and replay-safe creation of a combined photographed-shelf draft."""

from typing import Annotated, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from store_emulator.domain.store import Store
from store_emulator.domain.types import RESOURCE_ID_PATTERN

type BatchResourceId = Annotated[
    str, Field(min_length=1, max_length=128, pattern=RESOURCE_ID_PATTERN)
]


class CaptureBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_ids: list[BatchResourceId] = Field(min_length=1, max_length=20)
    setup_id: BatchResourceId

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len(set(self.capture_ids)) != len(self.capture_ids):
            raise ValueError("Choose each photo only once")
        return self


class CaptureBatchSave(CaptureBatchRequest):
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    allow_reduced_facings: bool = Field(default=False, strict=True)
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class CaptureBatchPreview(BaseModel):
    source_sha256: str
    store: Store
    rack_ids: list[str]
    placed_items: int
    placed_facings: int
    requested_facings: int
    reduced_facings: int
    dropped: list[str]
    notes: list[str]
    estimated_prices: int
    unrecognized_items: int


class CaptureBatchSaved(BaseModel):
    setup_id: str
    rack_ids: list[str]
    placed_items: int
    placed_facings: int
    notes: list[str]


class CaptureBatchRecord(BaseModel):
    capture_batch_request: CaptureBatchSave
    capture_batch_result: CaptureBatchSaved
