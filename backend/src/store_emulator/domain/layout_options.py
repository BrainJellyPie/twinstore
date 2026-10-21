"""Bounded, reproducible requirements for procedural store layouts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type LayoutStyle = Literal["aisles", "loop", "spine", "free_flow", "perimeter", "showroom"]
type LayoutDensity = Literal["spacious", "balanced", "dense"]
type EntrancePosition = Literal["left", "center", "right"]
type FixtureDesign = Literal["mixed", "a", "b", "c"]


class LayoutOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: LayoutStyle | None = None
    width: int | None = Field(default=None, ge=8, le=40)
    height: int | None = Field(default=None, ge=6, le=40)
    density: LayoutDensity = "balanced"
    entrance: EntrancePosition = "left"
    checkouts: int = Field(default=1, ge=1, le=4)
    fixture_design: FixtureDesign = "mixed"
