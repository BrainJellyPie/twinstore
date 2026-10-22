from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from .providers import EnsembleConfig
from .rack import RackType
from .scenario import Scenario, ScenarioPriors


class EngineType(StrEnum):
    PATTERN_INTENT_IMPULSE = "pattern_intent_impulse"
    RULE_BASED = "rule_based"
    VLM_GLANCE = "vlm_glance"


# How exposure ("what the shopper saw") is computed along the walked route.
# - adjacency: legacy behavior — every item of any rack touched by the path counts as seen.
# - visibility: per-face line-of-sight model with distance and shelf-level attention.
type ExposureModel = Literal["adjacency", "visibility"]

# How visits are ordered into a route.
# - planned: keep the shopper's own planned order; insert impulse visits at the cheapest detour.
# - nearest: legacy greedy nearest-neighbor reordering from the entrance.
type RouteOrdering = Literal["planned", "nearest"]

# How structured output is requested from the model.
# - json: ask for a JSON object (works with every LiteLLM provider).
# - json_schema: send the JSON schema as response_format; OpenAI-compatible servers such as
#   llama.cpp and vLLM compile it into a grammar, so even sub-1B models emit valid output.
type StructuredOutput = Literal["json", "json_schema"]

# When the VLM shopper is shown a shelf.
# - gated: the shopper looks at a passed rack face with probability look_base × visibility ×
#   pattern factor (calibratable rate); the VLM decides what catches the eye and whether to buy.
# - all: the VLM sees every one of the max_glances most visible faces and decides alone.
type GlancePolicy = Literal["gated", "all"]
type ShelfViewMode = Literal["chart", "photo_chart"]

# Who plans the visit of a vision shopper (see VLMGlanceConfig.plan_policy).
type PlanPolicy = Literal["vlm", "rule"]


class LLMConfig(BaseModel):
    model: str = "anthropic/claude-haiku-5-5"
    temperature: float = 1.0
    max_tokens: int = 65535
    # OpenAI-compatible endpoint override (vLLM, llama.cpp server, gateways). None = provider default.
    api_base: str | None = None
    # When set, every call gets a deterministic per-customer seed derived from this value.
    seed: int | None = None
    timeout_sec: float = 600.0
    # Directory for the content-addressed response cache. None disables caching.
    cache_dir: str | None = None
    structured_output: StructuredOutput = "json"
    # Resolved from provider settings / environment at run time. Excluded from every dump, so it
    # is never written to run configs, manifests or API responses.
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    # Requests the endpoint serves at once (a llama.cpp server on this computer has that many slots); more wait their
    # turn in the client, so their time-out does not run while they queue on the server. None = no limit. Runtime only.
    max_parallel: int | None = Field(default=None, ge=1, exclude=True)


class DwellRange(BaseModel):
    min: int
    max: int


_DWELL_DEFAULTS: dict[RackType, DwellRange] = {
    RackType.SHELF:   DwellRange(min=2,  max=10),
    RackType.FRIDGE:  DwellRange(min=2,  max=8),
    RackType.COUNTER: DwellRange(min=5,  max=30),
}


class PerceptionConfig(BaseModel):
    """Parameters of the visibility exposure model.

    Defaults are uncalibrated priors (eye level > waist > top > bottom), meant to
    be fitted against observed data; see docs/IMPROVEMENTS.md.
    """
    view_distance: int = Field(default=2, ge=1, le=6)  # tiles in front of a face that can see it
    level_attention: dict[int, float] = {1: 0.55, 2: 0.85, 3: 1.0, 4: 0.7}
    min_visibility: float = Field(default=0.15, ge=0.0, le=1.0)
    max_exposed_items: int = Field(default=40, ge=1)


class PatternIntentImpulseConfig(BaseModel):
    llm: LLMConfig | None = None  # None falls back to SimulationConfig.llm


class RuleBasedConfig(BaseModel):
    """Behavioral parameters of the non-LLM baseline engine (all calibratable)."""
    planned_hit_prob: float = Field(default=0.9, ge=0.0, le=1.0)  # finds a planned category item
    impulse_base: float = Field(default=0.06, ge=0.0, le=1.0)     # per-item impulse prob at visibility 1
    promo_multiplier: float = Field(default=1.8, ge=0.0)
    walkout_prob: float = Field(default=0.04, ge=0.0, le=1.0)    # leaves without buying (no-purchase patterns)
    max_impulse_items: int = Field(default=3, ge=0)
    # Mean products bought per planned category (≥ 1; extra products follow a geometric draw) and the
    # chance a bought line is two or more units. Defaults keep the original one-unit, one-product rule.
    items_per_category: float = Field(default=1.0, ge=1.0, le=6.0)
    multi_unit_prob: float = Field(default=0.0, ge=0.0, le=0.9)
    # planned_hit_prob × decay^k for the k-th preferred category (0-based): a shopping list is written
    # in priority order and its tail is often skipped. 1.0 = every entry equally likely (original rule).
    plan_position_decay: float = Field(default=1.0, gt=0.0, le=1.0)
    # Chance that, in a category holding one of the persona's usual products, the planner takes a usual
    # product instead of drawing by shelf attention. Calibrated on The Complete Journey:
    # 0.9 brings the repeat share of a trip's products to 0.59 (real 0.66; 0.12 without usual products).
    habit_prob: float = Field(default=0.9, ge=0.0, le=1.0)
    # Response to a product's price against its regular price (SlotItem.regular_price): choice weights and
    # impulse odds are multiplied by (price / regular) ** price_elasticity. Real own-price elasticity of
    # grocery items is about −0.7 at item level (M5 food sales, Walmart) and −1.8 to −2.6 at brand level
    # (meta-analyses); −1.8 here gives a measured own-price elasticity of −0.78 when half a store's
    # products move ±20 %.
    price_elasticity: float = Field(default=-1.8, ge=-5.0, le=0.0)
    browse_before_buy_prob: float = Field(default=0.6, ge=0.0, le=1.0)
    # Time at the shelf when the shopper looks before taking a product (look + pick, seconds): lognormal
    # with this median and log-sd. Fitted to 88 unplanned purchases filmed with mobile eye trackers in a
    # supermarket (median 8.2 s, quartiles 4.5–15 s). 0 keeps
    # the original uniform 3–12 s look + 2–5 s pick.
    shelf_time_median_sec: float = Field(default=8.2, ge=0.0, le=120.0)
    shelf_time_log_sd: float = Field(default=0.75, ge=0.0, le=2.0)
    # Unplanned stops that end without a purchase, per impulse buy (noticed, looked, walked on).
    browse_only_ratio: float = Field(default=1.0, ge=0.0)
    pattern_weights: dict[str, float] = {
        "purposeful": 3.0, "habitual": 1.5, "routine_refill": 0.8, "urgent": 1.0,
        "quick_snack": 1.5, "exploratory": 1.0, "hungry_wandering": 0.6, "leisurely": 0.5,
        "social_browsing": 0.4, "impulse_heavy": 0.5, "window_shopping": 0.4, "deal_hunting": 0.5,
    }


class VLMGlanceConfig(BaseModel):
    """Vision-language shopper: the VLM plans the visit at the entrance (plan_policy "vlm") and makes
    the impulse decisions from rendered shelf images; route style and caps stay rule-based.

    The default endpoint is a local llama.cpp server (OpenAI-compatible) running a small VLM
    on CPU, e.g. `llama-server -m Qwen3.5-0.8B-Q4_K_M.gguf --mmproj mmproj-...gguf --port 8081`.
    """
    llm: LLMConfig = LLMConfig(
        model="openai/local-vlm",
        api_base="http://127.0.0.1:8081/v1",
        temperature=0.3,
        max_tokens=160,
        timeout_sec=900.0,
        structured_output="json_schema",
    )
    max_glances: int = Field(default=3, ge=0, le=12)       # most visible rack faces considered per customer
    glance_policy: GlancePolicy = "gated"
    look_base: float = Field(default=0.6, ge=0.0, le=1.0)  # gated: P(look) at visibility 1, pattern factor 1
    image_width: int = Field(default=512, ge=256, le=2048)  # 512 read best on ≤2B models (see CHANGELOG)
    # Randomize the number badges per glance so a model's preference for low numbers
    # shows up as noise instead of as a fake product preference.
    shuffle_marks: bool = True
    # The VLM picks the most tempting product and rates interest 0–10; then
    #   P(buy)  = buy_scale × interest/10 × w(level),  P(look) = interest/10 × w(level)
    # with w = perception.level_attention when weight_by_level (eye level 1.0, top 0.7, …).
    # buy_scale is the calibration knob for the impulse-purchase rate; w(level) also offsets the
    # strong top-row preference small VLMs show on shelf images.
    buy_scale: float = Field(default=0.5, ge=0.0, le=1.0)
    weight_by_level: bool = True
    # Who decides what the shopper came for (and whether they go in at all).
    # - vlm: one call at the entrance with persona, time, situation, budget and the store directory
    #   (plus the directory map image when entrance_image); the scenario's numeric demand and walk-out
    #   multipliers are then not applied to the plan — the model read the situation itself.
    # - rule: the rule-based planner (preferred categories × scenario demand multipliers).
    plan_policy: PlanPolicy = "vlm"
    # 3 suits a convenience-store visit; supermarket trips need more (calibrate from POS lines per trip).
    max_plan_items: int = Field(default=3, ge=0, le=30)
    entrance_image: bool = True
    # Products named per category in the text directory, and whether each shopper sees its own random
    # draw of them (in random order) rather than the same top-of-shelf list. Validated on real baskets:
    # with 3 fixed examples 87 % of planned products were those three (54 %
    # real); with 8 in random order the product-choice JSD against real sales ranks fell 0.11 → 0.02.
    directory_examples: int = Field(default=8, ge=1, le=50)
    directory_shuffle: bool = True
    directory_prices: bool = True   # each product's own price in the directory (else the category's range)
    # glance_order: which of the equally well seen rack faces the max_glances glances go to. Faces passed close by
    # are all seen at visibility 1; "shuffle" draws among them per shopper (common random numbers across layouts),
    # "rack" takes them by rack id, which sent every shopper's glances to the same first racks whatever the route.
    glance_order: Literal["shuffle", "rack"] = "shuffle"
    plan_max_tokens: int = Field(default=320, ge=64, le=4096)  # plans are longer than glance answers
    # What a glance shows: "chart" (the rendered front elevation with names, prices and numbers) or
    # "photo_chart" (the face photographed in the 3D store, with the same numbers, above that chart). Faces
    # without a stored photo fall back to the chart. shelf_views_dir: where the photos are (set per run).
    shelf_view: ShelfViewMode = "chart"
    shelf_views_dir: str = ""


class EngineConfigs(BaseModel):
    pattern_intent_impulse: PatternIntentImpulseConfig = PatternIntentImpulseConfig()
    rule_based: RuleBasedConfig = RuleBasedConfig()
    vlm_glance: VLMGlanceConfig = VLMGlanceConfig()


class SimulationConfig(BaseModel):
    # Seconds to walk one tile. Movement validated on 13,159 pedestrian tracks from a shopping center
    # (ATC pedestrian tracks): with a tile of 1.25 m, 1.04 s/tile gives a median per-shopper walking
    # speed of 1.12 m/s against 1.13 m/s real (1.0 s/tile: 1.25 m/s). Diagonal steps take the straight
    # line instead of a staircase (detour index 1.27 → 1.19; real 1.06 in open corridors), and pace
    # varies between shoppers (sd of log pace 0.3; real p90 1.46 m/s, simulated 1.53).
    block_move_sec: float = Field(default=1.04, gt=0.0, le=10.0)
    diagonal_moves: bool = True
    walk_pace_sd: float = Field(default=0.3, ge=0.0, le=1.0)   # sd of log pace across shoppers; 0 = everyone alike
    max_grid_size: int = 30
    dwell: dict[RackType, DwellRange] = dict(_DWELL_DEFAULTS)
    engine_type: EngineType = EngineType.PATTERN_INTENT_IMPULSE
    llm: LLMConfig = LLMConfig()
    engines: EngineConfigs = EngineConfigs()
    # Reproducibility. Every per-customer random stream is derived from (seed, replicate, persona_id),
    # so two layouts run with the same seed/replicate share cues and arrivals (common random numbers).
    seed: int = 0
    replicate: int = 0
    exposure_model: ExposureModel = "visibility"
    route_ordering: RouteOrdering = "planned"
    perception: PerceptionConfig = PerceptionConfig()
    # Impulse buys are dropped (latest first) once spend exceeds budget_max × tolerance. None disables.
    budget_tolerance: float | None = Field(default=1.5, ge=0, allow_inf_nan=False)
    # Scales every behavior pattern's product cap (max_products). The presets are sized for convenience
    # stores; supermarket trips are larger. Calibrated from POS lines per trip (see engine.calibration).
    basket_scale: float = Field(default=1.0, ge=0.1, le=10.0)
    max_quantity_per_line: int = Field(default=6, ge=1)
    # ISO 4217 code. Prices and budgets are integers in the currency's minor unit (USD → cents, KRW → won).
    currency: str = "USD"
    # Several models as one consumer population for the run's LLM/VLM engine (None = single model).
    ensemble: EnsembleConfig | None = None
    # Situation of the simulated day(s): weather, events, promotions, stock-outs, crowding …
    scenario: Scenario | None = None
    # Effect sizes of situations (weather, calendar, events, promotions). None: chosen by the store's
    # type — grocery formats use the profile fitted to real data (engine/scenario.py GROCERY_PRIORS),
    # the others the convenience-store priors.
    scenario_priors: ScenarioPriors | None = None

    def dwell_for(self, rack_type: RackType) -> DwellRange:
        return self.dwell.get(rack_type, DwellRange(min=5, max=30))

    def llm_for(self, engine_type: EngineType) -> LLMConfig:
        if engine_type == EngineType.PATTERN_INTENT_IMPULSE:
            return self.engines.pattern_intent_impulse.llm or self.llm
        if engine_type == EngineType.VLM_GLANCE:
            return self.engines.vlm_glance.llm
        return self.llm
