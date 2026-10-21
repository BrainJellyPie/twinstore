"""One shopper's trip, step by step with what they were thinking, and a conversation with that shopper
afterwards ("why didn't you buy it?"), answered in character from the trip itself."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    sees_products: bool = False       # the shelf face of this step holds products (worth showing)
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
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=600)
    model: str = Field(default="", description='model reference; "" = the app text model')


# ── group interviews ────────────────────────────────────────────────────────────

type GroupSegment = Literal["all", "empty_handed", "buyers", "impulse", "top_spenders"]


class GroupInterviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=600)
    segment: GroupSegment = "all"
    persona_ids: list[str] = Field(default_factory=list[str], max_length=40, description="ask exactly these shoppers instead")
    size: int = Field(default=12, ge=2, le=40)
    model: str = Field(default="", description='model reference; "" = the app text model')
    seed: int = 0


class GroupAnswer(BaseModel):
    persona_id: str
    identity: str
    age_group: str
    gender: str
    spent: int
    units: int
    answer: str = ""
    steps: list[int] = []
    theme: int = -1                   # index into GroupInterview.themes, -1 = not coded
    error: str = ""


class Theme(BaseModel):
    label: str
    count: int
    share: float


class GroupInterview(BaseModel):
    group_id: str
    run_id: str
    question: str
    segment: GroupSegment
    model: str = ""
    created_at: str = ""
    answers: list[GroupAnswer] = []
    themes: list[Theme] = []
    errors: int = 0
