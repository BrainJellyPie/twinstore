from typing import Literal

from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema

from .types import Action, Face, Position

type NavMode = Literal["path", "area", "leave"]


class CustomerAction(BaseModel):
    nav: NavMode
    target: Position | None = None
    face: Face | None = None
    action: Action | None = None
    dwell: int = 0
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
