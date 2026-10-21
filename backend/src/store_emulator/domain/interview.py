"""One shopper's trip, step by step with what they were thinking, and a conversation with that shopper
afterwards ("why didn't you buy it?"), answered in character from the trip itself."""

from typing import Literal

from pydantic import BaseModel, Field

from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action


class ShelfItem(BaseModel):
    sku: str
    name: str
    price: int                        # minor currency unit
    regular_price: int = 0
    promo: str = ""


class JourneyStep(BaseModel):
    index: int                        # what interview answers cite
    time: str                         # wall clock "HH:MM:SS"
    elapsed_sec: int
    action: Action
    rack_id: str = ""
    rack: str = ""                    # rack name
    face: str = ""
    product_sku: str = ""
    product_name: str = ""
    price: int = 0
    quantity: int = 1
    origin: str = ""                  # planned | impulse
    thought: str = ""                 # the engine's description of this step
    duration: int = 0
    x: int = 0
    y: int = 0


class Journey(BaseModel):
    run_id: str
    persona: Persona
    day: int
    arrival_time: str
    leave_time: str
    engine_type: str
    currency: str
    total_spent: int
    units: int
    steps: list[JourneyStep]          # everything except plain walking, in order
    path: list[tuple[int, int, int]]  # (elapsed_sec, x, y) of every position
    shelves: dict[str, list[ShelfItem]] = {}   # rack id → products on the faces the shopper stopped at


class InterviewMessage(BaseModel):
    role: Literal["interviewer", "shopper"]
    text: str
    steps: list[int] = []             # journey steps the shopper refers to
    created_at: str = ""


class Interview(BaseModel):
    run_id: str
    persona_id: str
    model: str = ""
    messages: list[InterviewMessage] = []


class InterviewQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    model: str = Field(default="", description='model reference; "" = the app text model')
