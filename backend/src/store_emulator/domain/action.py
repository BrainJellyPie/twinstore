from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from .types import Action, Face, Position

type NavMode = Literal["path", "area", "leave"]
MAX_ACTION_DWELL = 120


class CustomerAction(BaseModel):
    nav: NavMode
    target: Position | None = None
    face: Face | None = None
    action: Action | None = None
    dwell: int = Field(default=0, json_schema_extra={"minimum": 0, "maximum": MAX_ACTION_DWELL})
    product_sku: str = ""
    description: str = ""
    area: tuple[int, int, int, int] | None = None  # wander bounds: x1, y1, x2, y2
    quantity: int = 1  # units bought (BUY only); clamped by the executor
    # "planned" | "impulse". Set by the engine, never by the LLM — hidden from the response schema.
    origin: SkipJsonSchema[str] = "planned"
    # Engine-selected offer, omitted from model response schemas. Legacy and
    # model-generated actions without these hints still resolve by SKU/stance.
    product_block: SkipJsonSchema[int | None] = None
    product_level: SkipJsonSchema[int | None] = None

    @field_validator("dwell")
    @classmethod
    def _bounded_dwell(cls, value: int) -> int:
        # Normalize raw model times before scenario arithmetic. Internal scaled copies
        # intentionally retain their computed times, including increases beyond 120s.
        return max(0, min(MAX_ACTION_DWELL, value))
