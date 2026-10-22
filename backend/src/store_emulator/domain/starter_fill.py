"""Explicit starter categories for empty existing racks; no inferred stock or prices."""
from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from store_emulator.domain.rack import SlotItem


class RackFill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rack_id: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    skus: list[Annotated[str, Field(min_length=1, max_length=200)]] | None = Field(default=None, min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_products(self) -> Self:
        if self.skus is not None and len(set(self.skus)) != len(self.skus):
            raise ValueError("Choose each product only once per rack")
        return self


class StarterAutoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    requirements: str = Field(default="", max_length=2000)
    products_per_slot: int = Field(default=2, ge=1, le=4, strict=True)
    model: str = Field(default="", max_length=200)


class StarterFillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    assignments: list[RackFill] = Field(min_length=1, max_length=100)
    products_per_slot: int = Field(default=2, ge=1, le=4, strict=True)

    @model_validator(mode="after")
    def unique_racks(self) -> Self:
        if len({row.rack_id for row in self.assignments}) != len(self.assignments):
            raise ValueError("Choose each rack only once")
        return self


class StarterFillSave(StarterFillRequest):
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class StarterCategory(BaseModel):
    key: str
    label: str
    products: list[SlotItem]


class StarterRack(BaseModel):
    id: str
    name: str
    type: str
    available_slots: int
    suggested_category: str | None = None
    reason: str | None = None
    reason_code: Literal["occupied", "no_accessible_face"] | None = None


class StarterCatalog(BaseModel):
    source_sha256: str
    currency: str
    categories: list[StarterCategory]
    racks: list[StarterRack]


class FilledRack(BaseModel):
    id: str
    name: str
    category: str
    slots_added: int
    placements_added: int
    products: list[SlotItem]
    reused_skus: list[str]


class StarterPreview(BaseModel):
    racks: list[FilledRack]
    placements_added: int
    new_skus: int
    reused_skus: int


class StarterSaved(BaseModel):
    setup_id: str
    placements_added: int


class StarterRecord(BaseModel):
    starter_fill_request: StarterFillSave
    starter_fill_result: StarterSaved
