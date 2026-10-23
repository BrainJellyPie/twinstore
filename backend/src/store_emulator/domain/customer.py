from pydantic import BaseModel, Field

from .rack import RACK_LEVELS

from .types import Action, Face, Weekday


class TimelineEvent(BaseModel):
    elapsed_sec: int
    x: int
    y: int
    action: Action
    duration: int = 0
    target_rack: str = ""
    face: Face | None = None
    description: str = ""
    product_sku: str = ""
    product_block: int | None = Field(default=None, ge=0)
    product_level: int | None = Field(default=None, ge=1, le=RACK_LEVELS)
    product_name: str = ""
    price: int = 0  # unit price in the currency's minor unit
    quantity: int = 1  # units on a BUY line; line total = price × quantity
    origin: str = ""  # "planned" | "impulse" on BROWSE/BUY, "" otherwise


class CustomerResult(BaseModel):
    persona_id: str
    day: Weekday
    arrival_time: str  # "HH:MM:SS"
    leave_time: str = ""
    timeline: list[TimelineEvent] = []
    total_spent: int = 0  # minor currency unit, Σ price × quantity
    # A planner's hard cap, retained for stock substitutions and saved operations replays. None: no hard cap.
    spend_limit: int | None = Field(default=None, ge=0)
    engine_type: str = ""
    dropped_invalid_buys: int = 0  # BUYs naming SKUs that are not in the store (LLM hallucinations)
    dropped_over_budget: int = 0  # impulse BUYs removed by the budget tolerance rule
    # The shared store (runs with operations): what was gone when the shopper reached it, and the till line.
    lost_units: int = 0  # units wanted but sold out, not replaced by another product
    substituted_units: int = 0  # units of another product taken because the wanted one was sold out
    queue_wait_sec: int = 0  # seconds in line before a till came free (or before giving up)
    left_queue: bool = False  # left the line without paying; the basket stayed behind

    @property
    def purchases(self) -> list[TimelineEvent]:
        return [e for e in self.timeline if e.action == Action.BUY]

    @property
    def units_bought(self) -> int:
        return sum(e.quantity for e in self.purchases)

    @property
    def duration_sec(self) -> int:
        return self.timeline[-1].elapsed_sec if self.timeline else 0
