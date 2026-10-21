"""Marketing studio: A/B tests of price, promotion, placement and packaging on the twin, and survey-style
concept tests answered by synthetic respondents.

Prices are in the currency's minor unit (US cents, KRW won), like everywhere else in the store model.
"""

from typing import Literal

from pydantic import BaseModel, Field

from store_emulator.domain.analysis import MetricComparison

type ChangeKind = Literal["price", "discount", "promo", "move", "package", "category_price"]
type ExperimentEngine = Literal["rule", "vlm"]
type JobState = Literal["pending", "running", "completed", "failed"]


class VariantChange(BaseModel):
    """One change a variant makes to the control layout.

    price           set the SKU's shelf price (`price`), as a new everyday price
    discount        cut the SKU's price by `percent` and keep the old one as the "was" price on the tag
    promo           hang a promotion sign (`promo`, e.g. "1+1", "SALE", "-30%") on the SKU
    move            move the SKU to `rack_id` / `face` / `level` (level 3 = eye level on a 4-level rack)
    package         show the SKU in a new package (`asset_id`, a product image) — vision shoppers only
    category_price  change every price in `category` by `percent`, optionally ending in .99 (`charm`)
    """
    kind: ChangeKind
    sku: str = ""
    price: int | None = Field(default=None, ge=0)
    percent: float | None = Field(default=None, ge=-90, le=300, description="-20 = 20 % cheaper")
    promo: str = Field(default="", max_length=24)
    rack_id: str = ""
    face: Literal["N", "S", "E", "W"] | None = None
    level: int | None = Field(default=None, ge=1, le=4)
    asset_id: str = ""
    category: str = ""
    charm: bool = False


class Variant(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    changes: list[VariantChange] = Field(min_length=1, max_length=20)


class ExperimentRequest(BaseModel):
    setup_id: str = Field(description="the control layout; every variant starts from it")
    name: str = Field(default="", max_length=80)
    variants: list[Variant] = Field(min_length=1, max_length=6)
    focus_skus: list[str] = Field(default_factory=list[str], max_length=20, description="products whose sales the test is about")
    engine: ExperimentEngine = Field(default="rule", description="rule: fast, sees prices and placement; vlm: vision shoppers, also see packages and signs")
    model: str = Field(default="", description='vision model reference for engine "vlm"; "" = the app vision model')
    panel: int = Field(default=300, ge=20, le=3000, description="shoppers per variant (the same people in every variant)")
    seed: int = 1


class FocusOutcome(BaseModel):
    """Per-visitor sales of the focus products in one variant, and the paired difference to control."""
    sku: str                          # "*" = all focus products together
    name: str
    metric: Literal["units", "spend", "buyers"]
    control: float
    variant: float
    diff: float
    rel_diff: float
    ci_low: float
    ci_high: float
    prob_better: float


class SkuSales(BaseModel):
    sku: str
    name: str
    units: int
    revenue: int
    buyers: int


class VariantResult(BaseModel):
    name: str
    applied: list[str] = []           # what changed, in words
    warnings: list[str] = []
    revenue_per_visitor: float = 0.0
    conversion: float = 0.0
    units_per_visitor: float = 0.0
    vs_control: list[MetricComparison] = []   # spend, units, bought … (empty for the control)
    focus: list[FocusOutcome] = []
    top_skus: list[SkuSales] = []


class ExperimentReport(BaseModel):
    experiment_id: str
    name: str
    setup_id: str
    engine: ExperimentEngine
    model: str = ""
    panel_size: int
    currency: str
    visitors_per_day: float
    focus_skus: list[str] = []
    control: VariantResult
    variants: list[VariantResult]
    winner: str = ""                  # the variant with the best revenue per visitor whose CI is above zero
    notes: list[str] = []
    seconds: float = 0.0


class MarketingInfo(BaseModel):
    currency: str                     # ISO code of shelf prices (minor units) in this app


class JobStatus(BaseModel):
    job_id: str
    kind: Literal["experiment", "survey"]
    name: str = ""
    status: JobState
    stage: str = ""
    progress: float = 0.0
    error: str = ""
    created_at: str = ""
    finished_at: str = ""


# ── surveys ─────────────────────────────────────────────────────────────────────

type QuestionKind = Literal["purchase_intent", "appeal", "value", "uniqueness", "price_vw", "preference", "open"]


class SurveyRequest(BaseModel):
    name: str = Field(default="", max_length=80)
    stimuli: list[str] = Field(min_length=1, max_length=4, description="product image ids, shown side by side as A, B, C, D")
    stimulus_names: list[str] = Field(default_factory=list[str], max_length=4)
    questions: list[QuestionKind] = Field(min_length=1, max_length=7)
    context: str = Field(default="", max_length=300, description='what respondents are told, e.g. "a new iced tea, 500 ml"')
    reference_price: int | None = Field(default=None, ge=0, description="price shown with the product, minor units")
    currency: str = "USD"
    panel: int = Field(default=60, ge=5, le=1000, description="respondents (a deterministic sample of the project's personas)")
    age_groups: list[str] = Field(default_factory=list[str], description="quota: only these age groups (empty = all)")
    genders: list[str] = Field(default_factory=list[str], description="quota: only these genders (empty = all)")
    model: str = Field(default="", description='model reference; "" = the app vision model')
    seed: int = 0


class SurveyAnswer(BaseModel):
    """One respondent's answers (scales 1–5; prices in minor units)."""
    respondent: str
    age_group: str
    gender: str
    purchase_intent: list[int] = []   # per stimulus
    appeal: list[int] = []
    value: list[int] = []
    uniqueness: list[int] = []
    too_cheap: int | None = None      # Van Westendorp, for stimulus A
    cheap: int | None = None
    expensive: int | None = None
    too_expensive: int | None = None
    preferred: int | None = None      # index of the preferred stimulus
    why: str = ""
    error: str = ""


class ScaleSummary(BaseModel):
    question: QuestionKind
    stimulus: int
    n: int
    mean: float
    ci_low: float
    ci_high: float
    top2: float                       # share answering 4 or 5
    distribution: list[int]           # counts of 1..5


class SegmentRow(BaseModel):
    segment: str                      # "age 20대", "gender 여" …
    n: int
    values: dict[str, float]          # "purchase_intent·A" → mean


class PriceRange(BaseModel):
    """Van Westendorp price sensitivity: the acceptable range and its optimal point."""
    n: int
    point_of_marginal_cheapness: int | None
    optimal_price_point: int | None
    indifference_price_point: int | None
    point_of_marginal_expensiveness: int | None
    curve: list[tuple[int, float, float, float, float]] = []   # price, too cheap, cheap, expensive, too expensive (shares)


class PreferenceShare(BaseModel):
    stimulus: int
    name: str
    share: float
    ci_low: float
    ci_high: float


class SurveyReport(BaseModel):
    survey_id: str
    name: str
    model: str
    stimuli: list[str]
    stimulus_names: list[str]
    questions: list[QuestionKind]
    currency: str
    respondents: int
    errors: int
    scales: list[ScaleSummary] = []
    segments: list[SegmentRow] = []
    price: PriceRange | None = None
    preference: list[PreferenceShare] = []
    verbatims: list[str] = []
    answers: list[SurveyAnswer] = []
    notes: list[str] = []
    seconds: float = 0.0
