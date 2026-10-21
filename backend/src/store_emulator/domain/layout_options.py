"""Bounded, reproducible requirements for procedural store layouts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type LayoutStyle = Literal["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"]
type LayoutDensity = Literal["spacious", "balanced", "dense"]
type EntrancePosition = Literal["left", "center", "right"]
type ExitPosition = Literal["shared", "left", "center", "right"]
type CheckoutPlacement = Literal["auto", "near_entrance", "away_from_entrance"]
type SeatingZone = Literal["auto", "front", "back", "left", "right", "center"]
type StoreDesign = Literal["classic", "warm", "minimal", "industrial", "botanical", "luxury"]
type FixtureDesign = Literal["mixed", "a", "b", "c"]
type ShelfDirection = Literal["horizontal", "vertical"]


class ReservedArea(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=80)
    x: int = Field(ge=1, le=38)
    y: int = Field(ge=1, le=38)
    width: int = Field(ge=1, le=38)
    height: int = Field(ge=1, le=38)


class LayoutOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: LayoutStyle | None = None
    width: int | None = Field(default=None, ge=8, le=40)
    height: int | None = Field(default=None, ge=6, le=40)
    density: LayoutDensity = "balanced"
    shelf_direction: ShelfDirection = "horizontal"
    entrance: EntrancePosition = "left"
    exit_position: ExitPosition = "shared"
    checkouts: int | None = Field(default=None, ge=1, le=12)
    checkout_placement: CheckoutPlacement = "auto"
    fixture_design: FixtureDesign = "mixed"
    design_theme: StoreDesign | None = None
    dining_tables: int | None = Field(default=None, ge=0, le=12)
    table_clearance: int = Field(default=1, ge=1, le=3)
    seating_zone: SeatingZone = "auto"
    reserved_areas: list[ReservedArea] = Field(default_factory=list[ReservedArea], max_length=8)


class TemplateLayoutRequest(LayoutOptions):
    template_id: str
    source_setup_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    seed: int = 0
    currency: Literal["USD", "KRW", "JPY"] = "USD"
    name: str | None = Field(default=None, max_length=300)
    requirements: str = Field(default="", max_length=2000)


class BuildingFloorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=80)
    layout: TemplateLayoutRequest


class BuildingLayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    floors: list[BuildingFloorRequest] = Field(min_length=2, max_length=6)


class BuildingFloorInfo(BaseModel):
    id: str
    name: str
    level: int
    label: str
    floor_count: int
