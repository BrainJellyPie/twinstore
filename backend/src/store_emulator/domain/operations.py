"""The store the shoppers of a run share: stock on the shelves and the line at the tills.

Without it every shopper walks an empty store with endless stock. With it, what one shopper takes is gone for the
next, staff top the shelves up on a schedule, and shoppers who reach the tills wait for one to come free — and some
give up and leave their basket behind."""

from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class OperationsConfig(BaseModel):
    """How the shared store runs during the simulated day(s). Every shelf starts full each day."""
    # Units of each product on each shelf level that carries it, at opening.
    stock_per_facing: int = Field(default=12, ge=1, le=10_000)
    # Units per shelf level for single products (SKU → units); zero starts sold out.
    stock_overrides: dict[str, Annotated[int, Field(ge=0, le=10_000)]] = Field(default_factory=dict[str, int])
    # Staff fill every shelf back up this often during the day (minutes); None = only overnight.
    restock_every_min: int | None = Field(default=120, ge=5, le=1440)
    # Share of shoppers who take another product from the same shelf face when theirs is sold out. Shoppers
    # facing a stock-out in 40 studies (Gruen, Corsten & Bharadwaj 2002): 45 % substituted (same brand or another),
    # 31 % bought elsewhere, 15 % delayed and 9 % did without.
    substitute_share: float = Field(default=0.45, ge=0.0, le=1.0)
    # Tills staffed; None = every checkout counter of the layout.
    open_counters: int | None = Field(default=None, ge=1, le=50)
    # Tills staffed in single hours of the day ("18" → 3), overriding open_counters there; never more than the
    # layout has. 0 closes the tills for that hour: shoppers wait for the next open one.
    till_schedule: dict[str, int] = Field(default_factory=dict[str, int])
    # Time at the till: a fixed part (greeting, payment, bagging) and a part per unit scanned.
    checkout_base_sec: float = Field(default=25.0, ge=0.0, le=600.0)
    checkout_item_sec: float = Field(default=3.0, ge=0.0, le=60.0)
    # The wait a shopper accepts before leaving the line (median, seconds) and how much that varies between
    # shoppers (sd of its log).
    patience_sec: float = Field(default=300.0, ge=10.0, le=7200.0)
    patience_sd: float = Field(default=0.5, ge=0.0, le=2.0)
    # The longest average wait the till recommendation accepts in an hour (seconds).
    target_wait_sec: float = Field(default=120.0, ge=0.0, le=3600.0)

    @field_validator("till_schedule")
    @classmethod
    def _hours(cls, schedule: dict[str, int]) -> dict[str, int]:
        for hour, tills in schedule.items():
            if len(hour) != 2 or not hour.isascii() or not hour.isdigit() or int(hour) > 23:
                raise ValueError(f"till_schedule hours are \"00\"–\"23\", not {hour!r}")
            if not 0 <= tills <= 50:
                raise ValueError(f"till_schedule[{hour!r}] must be 0–50 tills")
        return dict(sorted(schedule.items()))


class StockoutStats(BaseModel):
    """A product that ran out on one shelf face."""
    sku: str
    name: str = ""
    rack_id: str
    rack_name: str = ""
    stock: int = 0                 # units on the face at opening (each day)
    sold_units: int = 0
    lost_units: int = 0            # wanted but not there, and not replaced by another product
    lost_revenue: int = 0          # minor currency unit, at the shelf price
    substituted_units: int = 0     # units of other products taken instead
    shoppers_missed: int = 0       # shoppers who found it gone
    first_out: str = ""            # "HH:MM:SS" of the first time it ran out
    minutes_out: float = 0.0       # time empty while the store was serving shoppers, all days


class QueueHour(BaseModel):
    """The tills in one hour of the day (all simulated days together)."""
    hour: str                      # "HH" — the hour shoppers reached the tills
    arrivals: int = 0
    avg_wait_sec: float = 0.0
    max_wait_sec: float = 0.0
    abandoned: int = 0
    counters_open: int = 0         # tills staffed in the hour
    counters_needed: int = 0       # fewest tills keeping this hour's average wait within the target


class OperationsReport(BaseModel):
    """What sharing the store did to the day."""
    config: OperationsConfig = OperationsConfig()
    days: int = 0
    counters: int = 0              # tills staffed
    counters_in_layout: int = 0
    # Stock
    stockout_faces: int = 0        # product faces that ran out at least once
    shoppers_hit: int = 0          # shoppers who found at least one product gone
    lost_units: int = 0
    lost_revenue: int = 0
    substituted_units: int = 0
    substituted_revenue: int = 0
    restocks: int = 0              # rounds of shelf filling during the day(s)
    # Tills
    queued: int = 0                # shoppers who reached the tills with something to pay
    avg_wait_sec: float = 0.0
    p90_wait_sec: float = 0.0
    max_wait_sec: float = 0.0
    abandoned: int = 0             # left the line without paying
    abandoned_units: int = 0
    abandoned_revenue: int = 0
    counter_utilization: float = 0.0   # share of the tills' open time spent serving
    till_hours: float = 0.0        # hours of staffed tills while the store served shoppers, all days
    counters_needed: int = 0       # the busiest hour's recommendation
    hours: list[QueueHour] = []
    stockouts: list[StockoutStats] = []   # by lost revenue, the largest first


class OperationsCosts(BaseModel):
    """What running the store costs, in the currency's minor unit, for comparing plans."""
    till_hour: int = Field(default=0, ge=0, le=10**9)          # one staffed till for an hour
    restock_round: int = Field(default=0, ge=0, le=10**9)      # one round of refilling the shelves
    stock_unit_day: int = Field(default=0, ge=0, le=10**9)     # keeping one unit on the shelves for a day


class OperationsOutcome(BaseModel):
    """A day (or days) under one operations plan, in money and waits."""
    revenue: int = 0
    lost_revenue: int = 0          # wanted, sold out, not replaced
    abandoned_revenue: int = 0     # baskets left at the tills
    abandoned: int = 0
    avg_wait_sec: float = 0.0
    p90_wait_sec: float = 0.0
    till_hours: float = 0.0
    restocks: int = 0
    stock_units: int = 0           # units on the shelves at opening, each day
    labor_cost: int = 0
    restock_cost: int = 0
    holding_cost: int = 0
    net: int = 0                   # revenue less the three costs


class OperationsReplay(BaseModel):
    """A finished run's shoppers, with their decisions unchanged, replayed under another operations plan."""
    planned_revenue: int = 0       # what the shoppers meant to buy (endless stock, no line)
    outcome: OperationsOutcome = OperationsOutcome()
    report: OperationsReport = OperationsReport()


class OperationsPlan(BaseModel):
    """The best plan found by replaying the run's shoppers under many."""
    current_config: OperationsConfig = OperationsConfig()
    current: OperationsOutcome = OperationsOutcome()
    config: OperationsConfig = OperationsConfig()
    best: OperationsOutcome = OperationsOutcome()
    replays: int = 0               # plans tried
    raised_skus: list[str] = []    # products given more units per shelf level than the rest
    complete: bool = True          # False: the search stopped at its time or size limit with the best found so far
