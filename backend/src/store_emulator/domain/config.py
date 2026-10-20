from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .rack import RackType


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


class LLMConfig(BaseModel):
    model: str = "gemini/gemini-3.1-pro-preview"
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
    browse_before_buy_prob: float = Field(default=0.6, ge=0.0, le=1.0)
    # Unplanned stops that end without a purchase, per impulse buy (noticed, looked, walked on).
    browse_only_ratio: float = Field(default=1.0, ge=0.0)
    pattern_weights: dict[str, float] = {
        "purposeful": 3.0, "habitual": 1.5, "routine_refill": 0.8, "urgent": 1.0,
        "quick_snack": 1.5, "exploratory": 1.0, "hungry_wandering": 0.6, "leisurely": 0.5,
        "social_browsing": 0.4, "impulse_heavy": 0.5, "window_shopping": 0.4, "deal_hunting": 0.5,
    }


class VLMGlanceConfig(BaseModel):
    """Vision-language shopper: rule-based planning, impulse decisions from rendered shelf images.

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


class EngineConfigs(BaseModel):
    pattern_intent_impulse: PatternIntentImpulseConfig = PatternIntentImpulseConfig()
    rule_based: RuleBasedConfig = RuleBasedConfig()
    vlm_glance: VLMGlanceConfig = VLMGlanceConfig()


class SimulationConfig(BaseModel):
    block_move_sec: int = 1
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
    budget_tolerance: float | None = 1.5
    max_quantity_per_line: int = Field(default=6, ge=1)
    # ISO 4217 code. Prices and budgets are integers in the currency's minor unit (USD → cents, KRW → won).
    currency: str = "USD"

    def dwell_for(self, rack_type: RackType) -> DwellRange:
        return self.dwell.get(rack_type, DwellRange(min=5, max=30))

    def llm_for(self, engine_type: EngineType) -> LLMConfig:
        if engine_type == EngineType.PATTERN_INTENT_IMPULSE:
            return self.engines.pattern_intent_impulse.llm or self.llm
        if engine_type == EngineType.VLM_GLANCE:
            return self.engines.vlm_glance.llm
        return self.llm
