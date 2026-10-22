"""Marketing studio: A/B tests of price, promotion, placement and packaging on the twin, and survey-style
concept tests answered by synthetic respondents.

Prices are in the currency's minor unit (US cents, KRW won), like everywhere else in the store model.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.types import ResourceId

type ChangeKind = Literal["price", "discount", "promo", "move", "package", "category_price"]
type ExperimentEngine = Literal["rule", "vlm"]
type JobState = Literal["pending", "running", "completed", "failed"]


class VariantChange(BaseModel):
    """One change a variant makes to the control layout.

    price           set the SKU's shelf price (`price`), as a new everyday price (or against the current one, `keep_reference`)
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
    keep_reference: bool = Field(default=False, description="price: shoppers keep the current price as the usual one "
                                 "(reference price), as just after a change; a cut then shows the was-price")


class Variant(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    changes: list[VariantChange] = Field(min_length=1, max_length=20)


class ExperimentRequest(BaseModel):
    setup_id: ResourceId = Field(description="the control layout; every variant starts from it")
    name: str = Field(default="", max_length=80)
    variants: list[Variant] = Field(min_length=1, max_length=6)
    focus_skus: list[str] = Field(default_factory=list[str], max_length=20, description="products whose sales the test is about")
    engine: ExperimentEngine = Field(default="rule", description="rule: fast, sees prices and placement; vlm: vision shoppers, also see packages and signs")
    model: str = Field(default="", description='vision model reference for engine "vlm"; "" = the app vision model')
    panel: int = Field(default=300, ge=20, le=3000, description="shoppers per variant (the same people in every variant)")
    seed: int = 1
    operations: OperationsConfig | None = Field(
        default=None, description="every arm's shoppers share the store run this way; omitted: the layout's saved "
                                  "settings, if any (a promotion that empties its shelf then pays for it)")
    shared_store: bool | None = Field(default=None, description="false: each shopper has the store alone")

    @model_validator(mode="after")
    def validate_variant_names(self) -> Self:
        names = [variant.name.casefold() for variant in self.variants]
        if "control" in names:
            raise ValueError("The variant name 'Control' is reserved for the original layout")
        if len(names) != len(set(names)):
            raise ValueError("Give each variant a unique name (ignoring case and surrounding whitespace)")
        return self


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


class SegmentLift(BaseModel):
    """A variant's paired difference to control within one shopper segment."""
    segment: str                      # "age 20s", "gender Female"
    n: int
    metric: Literal["spend", "focus_units"]   # store revenue per visitor, or units of the tracked products per visitor
    control: float
    variant: float
    diff: float
    ci_low: float
    ci_high: float


class VariantResult(BaseModel):
    name: str
    customers: int | None = Field(default=None, ge=0)  # analyzed common cohort; unknown in older reports
    applied: list[str] = []           # what changed, in words
    warnings: list[str] = []
    revenue_per_visitor: float = 0.0
    conversion: float = 0.0
    units_per_visitor: float = 0.0
    vs_control: list[MetricComparison] = []   # spend, units, bought … (empty for the control)
    focus: list[FocusOutcome] = []
    top_skus: list[SkuSales] = []
    prices: dict[str, int] = {}       # shelf price of each tracked product in this arm (lowest facing)
    segments: list[SegmentLift] = []  # paired differences by age group and gender (segments of 20+ shoppers)
    # Shared store: units wanted but sold out (not replaced), shoppers who left the till line, average wait there.
    lost_units: int = 0
    left_line: int = 0
    avg_wait_sec: float = 0.0


class PricePoint(BaseModel):
    arm: str
    price: int
    units: float                      # units of the product per visitor
    units_low: float                  # 95 % interval (paired difference to control, shifted by the control level)
    units_high: float
    revenue: float                    # the product's revenue per visitor (minor units)


class PriceResponse(BaseModel):
    """Demand for one product across the prices the arms set for it."""
    sku: str
    name: str
    points: list[PricePoint]          # sorted by price
    elasticity: float | None = None   # slope of log units on log price across the arms
    best_price: int | None = None     # the tested price with the most product revenue per visitor


class ExperimentReport(BaseModel):
    experiment_id: str
    name: str
    setup_id: str
    engine: ExperimentEngine
    model: str = ""
    panel_size: int
    currency: str
    visitors_per_day: float                     # what per-day money scales by: the estimated traffic when known
    simulated_visitors_per_day: float = 0.0     # customers simulated a day (a sample of it); 0 = same as above
    focus_skus: list[str] = []
    control: VariantResult
    variants: list[VariantResult]
    winner: str = ""                  # the variant with the best revenue per visitor whose CI is above zero
    price_response: PriceResponse | None = None   # when a tracked product has three or more prices across the arms
    notes: list[str] = []
    seconds: float = 0.0
    operations: OperationsConfig | None = None   # the arms' shoppers shared a store run this way


class MarketingInfo(BaseModel):
    currency: str                     # ISO code of shelf prices (minor units) in this app


class JobStatus(BaseModel):
    job_id: str
    kind: Literal["experiment", "survey", "pitch", "shelf", "conjoint"]
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


# ── shelf tests ─────────────────────────────────────────────────────────────────

class ShelfTestRequest(BaseModel):
    """Shelf impact test: the same respondents see the control shelf face and the changed one."""
    name: str = Field(default="", max_length=80)
    setup_id: ResourceId
    rack_id: str
    face: Literal["N", "S", "E", "W"] | None = Field(default=None, description="None = the face where the target stands")
    target_sku: str = Field(min_length=1, description="the product whose pick share and stand-out the test is about")
    changes: list[VariantChange] = Field(min_length=1, max_length=10, description="what the test shelf changes: package, price, sign, placement")
    panel: int = Field(default=60, ge=10, le=400)
    age_groups: list[str] = Field(default_factory=list[str])
    genders: list[str] = Field(default_factory=list[str])
    model: str = Field(default="", description='vision model reference; "" = the app vision model')
    seed: int = 0


class ShelfChoice(BaseModel):
    respondent: str
    age_group: str
    gender: str
    arm: Literal["control", "test"]
    pick_sku: str = ""                # "" = would not take anything
    pick_name: str = ""
    noticed: list[str] = []           # SKUs that caught the eye first (up to three, in order)
    why: str = ""
    error: str = ""


class ShareComparison(BaseModel):
    metric: Literal["pick", "noticed", "noticed_first"]
    control: float
    test: float
    diff: float
    ci_low: float
    ci_high: float
    prob_better: float


class SkuShare(BaseModel):
    sku: str
    name: str
    control: float
    test: float


class ShelfTestReport(BaseModel):
    test_id: str
    name: str
    setup_id: str
    rack_id: str
    rack_name: str
    face: str
    target_sku: str
    target_name: str
    model: str
    currency: str
    respondents: int = Field(description="Respondents with a successful answer in both arms; all metrics use this paired panel")
    errors: int
    applied: list[str] = []
    warnings: list[str] = []
    comparisons: list[ShareComparison] = []
    picks: list[SkuShare] = []
    choices: list[ShelfChoice] = []
    notes: list[str] = []
    seconds: float = 0.0


class ShelfPreviewRequest(BaseModel):
    setup_id: ResourceId
    rack_id: str
    target_sku: str = ""
    face: Literal["N", "S", "E", "W"] | None = None
    changes: list[VariantChange] = Field(default_factory=list[VariantChange], max_length=10)


class ShelfPreview(BaseModel):
    face: str
    control: str                      # PNG data URL
    test: str
    applied: list[str] = []
    warnings: list[str] = []


# ── conjoint ────────────────────────────────────────────────────────────────────

type Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class ConjointAttribute(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    levels: list[Label] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def validate_levels(self) -> Self:
        if len({level.casefold() for level in self.levels}) != len(self.levels):
            raise ValueError(f"Give the levels of '{self.name}' different names")
        return self


class ConjointRequest(BaseModel):
    """Choice-based conjoint: each respondent chooses between a few versions of a product (or none) in several
    choice tasks, and a logit model over all choices says what each attribute level is worth."""
    name: str = Field(default="", max_length=80)
    product: str = Field(min_length=1, max_length=160, description='what is being chosen, e.g. "a 500 ml bottle of iced tea"')
    context: str = Field(default="", max_length=300, description="anything else respondents are told")
    attributes: list[ConjointAttribute] = Field(min_length=1, max_length=6)
    prices: list[int] = Field(default_factory=list[int], max_length=6,
                              description="price levels in minor units (empty = no price attribute); estimated as one price slope")
    currency: str = "USD"
    tasks: int = Field(default=8, ge=3, le=15, description="choice tasks per respondent")
    options: int = Field(default=3, ge=2, le=4, description="product versions per task")
    none_option: bool = Field(default=True, description='respondents may choose "none of these"')
    panel: int = Field(default=60, ge=10, le=600)
    age_groups: list[str] = Field(default_factory=list[str])
    genders: list[str] = Field(default_factory=list[str])
    model: str = Field(default="", description='model reference; "" = the app vision model')
    seed: int = 0

    @model_validator(mode="after")
    def validate_design(self) -> Self:
        if len(self.prices) == 1:
            raise ValueError("Give at least two price levels, or none")
        if len(set(self.prices)) != len(self.prices) or any(p < 0 for p in self.prices):
            raise ValueError("Price levels must be different, non-negative amounts")
        names = [a.name.casefold() for a in self.attributes] + (["price"] if self.prices else [])
        if len(names) != len(set(names)):
            raise ValueError("Give each attribute a different name (the price attribute is called 'Price')")
        if len(names) < 2:
            raise ValueError("A conjoint study needs at least two attributes, counting price")
        return self


class ConjointTask(BaseModel):
    profiles: list[list[int]]         # per option: the level index of each attribute (price last, when there is one)
    choice: int | None = None         # chosen option; None = none of these


class ConjointRespondent(BaseModel):
    respondent: str
    age_group: str
    gender: str
    tasks: list[ConjointTask] = []
    why: str = ""
    error: str = ""


class PartWorth(BaseModel):
    """Utility of a level, centred within its attribute, with a 95 % interval over respondents."""
    attribute: str
    level: str
    utility: float
    ci_low: float
    ci_high: float
    wtp: float | None = None          # minor units worth paying for this level over the attribute's first level
    wtp_low: float | None = None
    wtp_high: float | None = None


class AttributeImportance(BaseModel):
    attribute: str
    importance: float                 # share of the summed utility ranges
    ci_low: float
    ci_high: float


class ConjointFit(BaseModel):
    choices: int
    log_likelihood: float
    null_log_likelihood: float
    mcfadden_r2: float
    hit_rate: float                   # share of choices the model predicts as the most likely option
    chance_rate: float


class ConjointSegment(BaseModel):
    segment: str
    n: int
    importances: dict[str, float]
    none_share: float


class ConjointReport(BaseModel):
    conjoint_id: str
    name: str
    model: str
    product: str
    currency: str
    attributes: list[ConjointAttribute]
    prices: list[int] = []
    options: int
    none_option: bool
    respondents: int
    errors: int
    none_share: float = 0.0
    part_worths: list[PartWorth] = []
    importances: list[AttributeImportance] = []
    price_slope: float | None = None  # utility per minor unit of price
    price_mean: float = 0.0           # price at which the price part-worth is zero
    none_utility: float | None = None # utility of "none", on the scale of the centred part-worths
    fit: ConjointFit | None = None
    segments: list[ConjointSegment] = []
    answers: list[ConjointRespondent] = []
    verbatims: list[str] = []
    notes: list[str] = []
    seconds: float = 0.0
