"""Shelf Lab: controlled experiments on photographed shelves.

Counterfactual edits change one thing on a real shelf photo (swap two products, empty a run, put a
new package on the shelf, change a price tag, hang a promotion sign) and record exactly which pixels
changed and how the planogram changed. Sim2real shows the same shoppers the photo and its rendered
twin. The compliance audit compares a field photo with the layout's reference face and prices the
differences by paired simulation.
"""

from typing import Literal

from pydantic import BaseModel, Field

from .analysis import MetricComparison
from .capture import Box, CaptureResult

type EditKind = Literal["swap", "remove", "replace", "price", "promo", "duplicate"]
type Sim2RealCondition = Literal["render", "photo", "photo_raw"]
type LabJobState = Literal["pending", "running", "completed", "failed"]


class PhotoEdit(BaseModel):
    """One counterfactual change. `item_id` is a product of the capture's planogram."""
    kind: EditKind
    item_id: str
    other_id: str = Field(default="", description="swap: the product to trade places with; duplicate: the run to overwrite")
    price: int | None = Field(default=None, ge=0, description="price: new tag price (minor units); replace: the new product's price")
    promo: str = Field(default="", max_length=24, description='promo: sign text, e.g. "1+1", "SALE", "-30%"')
    name: str = Field(default="", max_length=80, description="replace: name of the new product")
    brand: str = Field(default="", max_length=40)
    category: str = Field(default="", description="replace: catalog category key (default: the replaced product's)")
    asset_id: str = Field(default="", description="replace: id of an uploaded package image")


class EditChange(BaseModel):
    """Ground truth of one changed region: the pixels in `box` were rewritten."""
    kind: EditKind
    item_id: str
    box: Box
    before: str = ""
    after: str = ""


class EditedShelf(BaseModel):
    edit_id: str
    capture_id: str
    edits: list[PhotoEdit]
    changes: list[EditChange]
    result: CaptureResult                     # the planogram the edited photo shows
    promos: dict[str, str] = {}               # item id → promotion sign text visible on the photo
    image_size: tuple[int, int]
    created_at: str = ""


class GlanceAnswer(BaseModel):
    persona_id: str
    condition: Sim2RealCondition
    sku: str = ""                             # "" = nothing caught the shopper's eye (or unresolved)
    name: str = ""
    level: int = 0
    interest: int = 0
    resolved_by: str = ""                     # name | number | none | invalid | error
    reason: str = ""
    error: str = ""


class ConditionStats(BaseModel):
    condition: Sim2RealCondition
    answers: int
    errors: int
    none_rate: float
    mean_interest: float
    level_share: dict[int, float] = {}        # level → share of picks
    picks: dict[str, int] = {}                # sku → times picked


class Agreement(BaseModel):
    condition: Sim2RealCondition              # compared with the render
    pairs: int
    same_pick: float                          # share of personas who pick the same product (or nothing) in both
    ci_low: float
    ci_high: float
    interest_spearman: float | None = None


class Sim2RealReport(BaseModel):
    job_id: str
    capture_id: str
    edit_id: str = ""
    model: str
    personas: int
    conditions: list[Sim2RealCondition]
    products: dict[str, str] = {}             # sku → name, for the products both views show
    stats: list[ConditionStats] = []
    agreement: list[Agreement] = []
    answers: list[GlanceAnswer] = []
    notes: list[str] = []
    seconds: float = 0.0


class LabJobStatus(BaseModel):
    job_id: str
    kind: Literal["sim2real", "audit"]
    capture_id: str
    status: LabJobState
    progress: float = 0.0
    stage: str = ""
    error: str = ""
    created_at: str = ""
    finished_at: str = ""


class AuditFinding(BaseModel):
    kind: Literal["missing", "unexpected", "misplaced", "facings", "price", "gap"]
    level: int
    sku: str = ""
    name: str = ""
    expected: str = ""
    found: str = ""
    box: Box | None = None                    # where on the photo (when the finding is visible)
    loss_per_day: float | None = None         # revenue lost per day by this finding (stock-outs), currency minor units
    loss_ci: tuple[float, float] | None = None


class LevelCompliance(BaseModel):
    level: int
    expected_facings: int
    found_facings: int
    matched_facings: int
    score: float


class AuditReport(BaseModel):
    job_id: str
    capture_id: str
    setup_id: str
    rack_id: str
    face: str
    currency: str
    compliance: float                         # matched facings / expected facings
    levels: list[LevelCompliance] = []
    findings: list[AuditFinding] = []
    impact: MetricComparison | None = None    # per-visitor spend: reference (A) vs as photographed (B)
    visitors_per_day: float = 0.0
    revenue_delta_per_day: float | None = None
    revenue_delta_ci: tuple[float, float] | None = None
    panel_size: int = 0
    notes: list[str] = []
    seconds: float = 0.0
