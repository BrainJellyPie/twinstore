from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .rack import RackType


class EngineType(StrEnum):
    PATTERN_INTENT_IMPULSE = "pattern_intent_impulse"
    RULE_BASED = "rule_based"


# How exposure ("what the shopper saw") is computed along the walked route.
# - adjacency: legacy behavior — every item of any rack touched by the path counts as seen.
# - visibility: per-face line-of-sight model with distance and shelf-level attention.
type ExposureModel = Literal["adjacency", "visibility"]

# How visits are ordered into a route.
# - planned: keep the shopper's own planned order; insert impulse visits at the cheapest detour.
# - nearest: legacy greedy nearest-neighbor reordering from the entrance.
type RouteOrdering = Literal["planned", "nearest"]


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
    pattern_weights: dict[str, float] = {
        "purposeful": 3.0, "habitual": 1.5, "routine_refill": 0.8, "urgent": 1.0,
        "quick_snack": 1.5, "exploratory": 1.0, "hungry_wandering": 0.6, "leisurely": 0.5,
        "social_browsing": 0.4, "impulse_heavy": 0.5, "window_shopping": 0.4, "deal_hunting": 0.5,
    }


class EngineConfigs(BaseModel):
    pattern_intent_impulse: PatternIntentImpulseConfig = PatternIntentImpulseConfig()
    rule_based: RuleBasedConfig = RuleBasedConfig()


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
        return self.llm
