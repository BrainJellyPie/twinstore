"""A paired, synthetic screening test of two staff scripts; not observed sales."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from store_emulator.domain.marketing import JobStatus

type Arm = Literal["A", "B"]
type PitchMetric = Literal["purchase_intent", "trust", "pressure"]
type Rating = Annotated[int, Field(strict=True, ge=1, le=5)]
type ScriptText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)]


class PitchVariant(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    script: ScriptText


class PitchRequest(BaseModel):
    setup_id: str
    sku: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    name: str = Field(default="", max_length=80)
    variants: tuple[PitchVariant, PitchVariant]
    context: ScriptText
    product_facts: str = Field(default="", max_length=1600)
    panel: int = Field(default=40, ge=20, le=500)
    seed: int = Field(default=1, ge=0, le=2_147_483_647)
    model: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def distinct_variants(self) -> Self:
        a, b = self.variants
        if a.name.casefold() == b.name.casefold():
            raise ValueError("Give the scripts distinct names")
        if " ".join(a.script.split()).casefold() == " ".join(b.script.split()).casefold():
            raise ValueError("The two scripts must differ")
        return self


class PitchProduct(BaseModel):
    sku: str
    name: str
    price: int
    currency: str
    promo: str = ""


class PitchRating(BaseModel):
    purchase_intent: Rating
    trust: Rating
    pressure: Rating
    reply: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]


class PitchAnswer(BaseModel):
    respondent: str
    age_group: str
    gender: str
    first_arm: Arm
    a: PitchRating | None = None
    b: PitchRating | None = None
    error_a: str = ""
    error_b: str = ""


class PitchComparison(BaseModel):
    metric: PitchMetric
    a_mean: float
    b_mean: float
    diff: float  # B minus A, in scale points
    ci_low: float | None
    ci_high: float | None


class PitchSegment(BaseModel):
    segment: str
    pairs: int
    intent_diff: float


class PitchReport(BaseModel):
    pitch_id: str
    name: str
    model: str
    request: PitchRequest
    product: PitchProduct
    attempted: int
    pairs: int
    excluded: int
    comparisons: list[PitchComparison]
    segments: list[PitchSegment]
    screening_leader: Arm | None
    recommendation: str
    answers: list[PitchAnswer]
    notes: list[str]
    seconds: float = 0.0


class PitchView(JobStatus):
    report: PitchReport | None = None
