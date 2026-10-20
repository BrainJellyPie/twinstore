from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from .action import CustomerAction
from .behavior import BehaviorCue, BehaviorPattern
from .persona import Persona
from .store import Store
from .types import TokenUsage, Weekday


class PerCustomerContext(BaseModel):
    store: Store
    persona: Persona
    day: Weekday
    arrival_hour: int
    concurrent_visitors_in_hour: int
    cue: BehaviorCue
    behavior_patterns: list[BehaviorPattern]
    address: str = ""
    customer_profile: str = ""
    # Per-customer seed derived from (run seed, replicate, persona id). Independent of the layout,
    # so engines that draw randomness from it give paired layout comparisons common random numbers.
    seed: int = 0


class EngineDecision(BaseModel):
    actions: list[CustomerAction]
    engine_type: str
    trace: dict[str, object] = {}
    dropped_invalid_buys: int = 0
    dropped_over_budget: int = 0


class CustomerBehaviorEngine(Protocol):
    engine_type: str

    async def decide_actions(
        self,
        context: PerCustomerContext,
    ) -> EngineDecision: ...

    def reset_usage(self) -> None: ...
    def get_usage(self) -> TokenUsage: ...


@runtime_checkable
class EngineMetadataSource(Protocol):
    """Optional engine capability: run-level metadata saved as output/<engine_type>_meta.json."""

    def metadata(self) -> dict[str, object]: ...
