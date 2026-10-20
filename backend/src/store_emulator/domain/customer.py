from pydantic import BaseModel

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
    engine_type: str = ""
    dropped_invalid_buys: int = 0  # BUYs naming SKUs that are not in the store (LLM hallucinations)
    dropped_over_budget: int = 0  # impulse BUYs removed by the budget tolerance rule

    @property
    def purchases(self) -> list[TimelineEvent]:
        return [e for e in self.timeline if e.action == Action.BUY]

    @property
    def units_bought(self) -> int:
        return sum(e.quantity for e in self.purchases)

    @property
    def duration_sec(self) -> int:
        return self.timeline[-1].elapsed_sec if self.timeline else 0
