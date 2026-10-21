"""Bounded, reproducible requirements for procedural store layouts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from store_emulator.domain.types import ResourceId

type LayoutStyle = Literal["aisles", "loop", "spine", "cross", "plaza", "free_flow", "perimeter", "showroom"]
type LayoutDensity = Literal["spacious", "balanced", "dense"]
type EntrancePosition = Literal["left", "center", "right"]
type ExitPosition = Literal["shared", "left", "center", "right"]
type GateWall = Literal["front", "back", "left", "right"]
type CheckoutPlacement = Literal["auto", "near_entrance", "away_from_entrance"]
type CheckoutWall = Literal["front", "back", "left", "right"]
type SeatingZone = Literal["auto", "front", "back", "left", "right", "center"]
type StoreDesign = Literal["classic", "warm", "minimal", "industrial", "botanical", "luxury", "coastal", "terracotta", "nordic", "retro"]
type FixtureDesign = Literal["mixed", "a", "b", "c"]
type ShelfDirection = Literal["horizontal", "vertical"]
type TemplateCategoryId = Annotated[str, Field(min_length=1, max_length=80)]
type TemplateWeekday = Annotated[int, Field(strict=True, ge=1, le=7)]


class ReservedArea(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=80)
    x: int = Field(ge=1, le=38)
    y: int = Field(ge=1, le=38)
    width: int = Field(ge=1, le=38)
    height: int = Field(ge=1, le=38)


class DiningTableMix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    two_seat: int = Field(default=0, strict=True, ge=0, le=48)
    four_seat: int = Field(default=0, strict=True, ge=0, le=48)
    six_seat: int = Field(default=0, strict=True, ge=0, le=48)

    @property
    def total(self) -> int:
        return self.two_seat + self.four_seat + self.six_seat

    @model_validator(mode="after")
    def _bounded_total(self) -> "DiningTableMix":
        if self.total > 48:
            raise ValueError("Mixed dining tables must total at most 48.")
        return self


class LayoutOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: LayoutStyle | None = None
    width: int | None = Field(default=None, ge=8, le=40)
    height: int | None = Field(default=None, ge=6, le=40)
    density: LayoutDensity = "balanced"
    aisle_width: int | None = Field(default=None, ge=1, le=4)
    max_shelf_run: int | None = Field(default=None, ge=1, le=8)
    shelf_direction: ShelfDirection = "horizontal"
    entrance: EntrancePosition = "left"
    gate_wall: GateWall = "front"
    exit_position: ExitPosition = "shared"
    exit_wall: GateWall | None = None
    checkouts: int | None = Field(default=None, ge=1, le=12)
    checkout_clearance: int = Field(default=0, strict=True, ge=0, le=3)
    checkout_placement: CheckoutPlacement = "auto"
    checkout_wall: CheckoutWall = "front"
    fixture_design: FixtureDesign = "mixed"
    design_theme: StoreDesign | None = None
    dining_tables: int | None = Field(default=None, ge=0, le=48)
    dining_seats: int = Field(default=4, strict=True, ge=2, le=6, multiple_of=2)
    table_mix: DiningTableMix | None = None
    table_rotation: int = Field(default=0, strict=True, ge=0, le=90, multiple_of=90)
    table_clearance: int = Field(default=1, ge=1, le=3)
    seating_zone: SeatingZone = "auto"
    reserved_areas: list[ReservedArea] = Field(default_factory=list[ReservedArea], max_length=8)
    excluded_categories: list[TemplateCategoryId] = Field(default_factory=list[str], max_length=64)
    products_per_category: int | None = Field(default=None, ge=1, le=16)
    open_hour: int | None = Field(default=None, strict=True, ge=0, le=23)
    close_hour: int | None = Field(default=None, strict=True, ge=1, le=24)
    closed_days: list[TemplateWeekday] | None = Field(default=None, max_length=7)

    @model_validator(mode="after")
    def _matching_table_count(self) -> "LayoutOptions":
        if self.table_mix is not None and self.dining_tables is not None and self.dining_tables != self.table_mix.total:
            raise ValueError("Dining table count must match the mixed table total, or be omitted.")
        return self


class TemplateLayoutRequest(LayoutOptions):
    template_id: str
    source_setup_id: ResourceId | None = Field(default=None, max_length=100)
    seed: int = 0
    currency: Literal["USD", "KRW", "JPY"] = "USD"
    name: str | None = Field(default=None, max_length=300)
    requirements: str = Field(default="", max_length=2000)


class LayoutPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["twinstore-layout-options"]
    version: Literal[1]
    layout: TemplateLayoutRequest


class BuildingFloorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=80)
    layout: TemplateLayoutRequest


class BuildingLayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    floors: list[BuildingFloorRequest] = Field(min_length=2, max_length=6)


class BuildingPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["twinstore-building-options"]
    version: Literal[1]
    floors: list[BuildingFloorRequest] = Field(min_length=2, max_length=6)


class BuildingFloorInfo(BaseModel):
    id: str
    name: str
    level: int
    label: str
    floor_count: int
