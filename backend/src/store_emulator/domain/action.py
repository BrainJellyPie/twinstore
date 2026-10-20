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
