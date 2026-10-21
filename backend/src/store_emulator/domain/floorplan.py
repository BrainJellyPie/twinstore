"""A store floor plan read off an image (hand drawing, CAD export, scanned PDF page).

Fixture rectangles are in plan coordinates normalized to the store's outer outline: (0, 0) is the
outline's top-left corner, (1, 1) its bottom-right, x to the right and y down.
"""

from typing import Literal

from pydantic import BaseModel, Field

type FixtureKind = Literal["shelf", "gondola", "fridge", "freezer", "counter", "entrance"]
type PlanReader = Literal["auto", "classic", "vlm"]


class PlanFixture(BaseModel):
    kind: FixtureKind
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)
    label: str = Field(default="", max_length=60, description='category words on the plan, e.g. "drinks", "snacks"')


class FloorPlanReading(BaseModel):
    width_m: float = Field(gt=0, description="outer width of the store (estimated when the plan has no scale)")
    depth_m: float = Field(gt=0)
    fixtures: list[PlanFixture] = []
    reader: str = ""                       # classic | vlm (model id)
    outline: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)  # outline in image fractions
    notes: list[str] = []
