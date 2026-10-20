from pydantic import BaseModel

from store_emulator.domain.types import TokenUsage


class RackStats(BaseModel):
    rack_id: str
    rack_name: str = ""
    visitors: int = 0       # distinct customers who stopped at the rack (browse or buy)
    browsers: int = 0       # distinct customers who browsed
    buyers: int = 0         # distinct customers who bought at least one item
    units: int = 0
    revenue: int = 0
    impulse_units: int = 0

    @property
    def stop_to_buy(self) -> float:
        return self.buyers / self.visitors if self.visitors else 0.0


class SegmentStats(BaseModel):
    visitors: int = 0
    buyers: int = 0
    revenue: int = 0
    units: int = 0
    conversion_rate: float = 0.0
    revenue_per_visitor: float = 0.0


class ProductStats(BaseModel):
    sku: str
    name: str = ""
    units: int = 0
    revenue: int = 0
    buyers: int = 0
    impulse_units: int = 0


class SimulationSummary(BaseModel):
    store_id: str
    currency: str = "USD_CENTS"
    total_customers: int = 0
    total_revenue: int = 0  # minor currency unit
    top_products: list[str] = []  # by revenue (legacy field)
    by_purpose: dict[str, int] = {}  # visitor counts per persona attribute (legacy fields)
    by_identity: dict[str, int] = {}
    by_age: dict[str, int] = {}
    by_gender: dict[str, int] = {}
    # Funnel / basket KPIs
    buyers: int = 0
    conversion_rate: float = 0.0
    units_sold: int = 0
    avg_units_per_buyer: float = 0.0
    avg_basket_value: float = 0.0       # revenue / buyers
    revenue_per_visitor: float = 0.0    # revenue / visitors
    impulse_revenue_share: float = 0.0  # revenue from impulse lines / revenue
    impulse_unit_share: float = 0.0
    avg_visit_sec: float = 0.0
    avg_path_tiles: float = 0.0
    top_products_by_units: list[str] = []
    products: list[ProductStats] = []
    racks: list[RackStats] = []
    segments: dict[str, dict[str, SegmentStats]] = {}  # dimension → value → stats
    hourly_visitors: dict[str, int] = {}  # "HH" → arrivals


class FailedCustomer(BaseModel):
    persona_id: str
    reason: str


class RunDiagnostics(BaseModel):
    requested_customers: int = 0
    succeeded_customers: int = 0
    failed_customers: list[FailedCustomer] = []
    dropped_invalid_buys: int = 0
    dropped_over_budget: int = 0
    buy_violations: dict[str, int] = {}  # invariant violation kind → count

    @property
    def failure_rate(self) -> float:
        return len(self.failed_customers) / self.requested_customers if self.requested_customers else 0.0


class RunManifest(BaseModel):
    """Everything needed to reproduce (or audit) a run."""
    engine_type: str
    model: str = ""
    seed: int = 0
    replicate: int = 0
    exposure_model: str = ""
    route_ordering: str = ""
    store_fingerprint: str = ""
    persona_fingerprint: str = ""
    package_version: str = ""
    created_at: str = ""
    scenario: str = ""          # scenario name ("" = ordinary day)
    scenario_id: str = ""
    town: str = ""              # neighborhood the visitors were drawn from ("" = persona pool as is)


class AggregatedResult(BaseModel):
    summary: SimulationSummary
    pathcalc_heatmap: list[list[float]]
    persona_heatmap: list[list[int]]  # timeline event count per tile (legacy)
    dwell_heatmap: list[list[float]] = []  # seconds spent per tile, summed over customers
    token_usage: TokenUsage = TokenUsage()
    diagnostics: RunDiagnostics = RunDiagnostics()
