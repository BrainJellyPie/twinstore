"""The store the shoppers of a run share: stock on the shelves and the line at the tills.

Without it every shopper walks an empty store with endless stock. With it, what one shopper takes is gone for the
next, staff top the shelves up on a schedule, and shoppers who reach the tills wait for one to come free — and some
give up and leave their basket behind."""

from pydantic import BaseModel, Field, field_validator, model_validator


class OperationsConfig(BaseModel):
    """How the shared store runs during the simulated day(s). Every shelf starts full each day."""
    # Units of each product on each shelf level that carries it, at opening.
    stock_per_facing: int = Field(default=12, ge=1, le=10_000)
    # Units per shelf level for single products (SKU → units), overriding stock_per_facing; 0 starts sold out.
    stock_overrides: dict[str, int] = Field(default_factory=dict[str, int])
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
    # Backroom: units of each product kept behind the shelves (all its shelves together), which refills draw from.
    # None = an endless backroom: refills never run short. backroom_overrides sets single products (SKU → units);
    # with backroom_per_product None only those products have a finite backroom.
    backroom_per_product: int | None = Field(default=None, ge=0, le=1_000_000)
    backroom_overrides: dict[str, int] = Field(default_factory=dict[str, int])
    # A delivery before each later day tops every backroom up to its level again (order-up-to, next-morning
    # delivery). False: no delivery during the simulated days — what was in the backroom has to last.
    daily_delivery: bool = True
    # Crowding: with this many shoppers stopped at one shelf at once (the shopper included), an unplanned pick there
    # is skipped with crowd_skip chance — crowded shoppers buy less on impulse and leave sooner (Harrell, Hutt &
    # Anderson 1980; Machleit, Eroglu & Mantel 2000). None = no crowding. Assumed values, to set from observation.
    crowd_limit: int | None = Field(default=4, ge=2, le=50)
    crowd_skip: float = Field(default=0.35, ge=0.0, le=1.0)
    # One crew for the tills and the shelves: this many staff on duty, each serving at a till when shoppers wait and
    # refilling shelves when free, so a refill takes someone away from the tills. None = the tills are staffed on
    # their own (open_counters, till_schedule) and refill rounds are instant (restock_every_min). With a crew those
    # three are not used: crew member n works till n, the first stays at the tills while anyone else is on duty, and
    # a shelf face is refilled once it is down to refill_at of its full stock, by whoever is free first, taking
    # refill_face_sec plus refill_unit_sec per unit. The times are assumptions, to set from your own time studies.
    crew: int | None = Field(default=None, ge=1, le=100)
    crew_schedule: dict[str, int] = Field(default_factory=dict[str, int])   # "HH" → crew on duty that hour, 0–100
    refill_at: float = Field(default=0.5, ge=0.0, le=0.95)
    refill_face_sec: float = Field(default=30.0, ge=0.0, le=1800.0)
    refill_unit_sec: float = Field(default=4.0, ge=0.0, le=600.0)

    @field_validator("till_schedule")
    @classmethod
    def _hours(cls, schedule: dict[str, int]) -> dict[str, int]:
        for hour, tills in schedule.items():
            if len(hour) != 2 or not hour.isascii() or not hour.isdigit() or int(hour) > 23:
                raise ValueError(f"till_schedule hours are \"00\"–\"23\", not {hour!r}")
            if not 0 <= tills <= 50:
                raise ValueError(f"till_schedule[{hour!r}] must be 0–50 tills")
        return dict(sorted(schedule.items()))

    @field_validator("crew_schedule")
    @classmethod
    def _crew_hours(cls, schedule: dict[str, int]) -> dict[str, int]:
        for hour, crew in schedule.items():
            if len(hour) != 2 or not hour.isascii() or not hour.isdigit() or int(hour) > 23:
                raise ValueError(f"crew_schedule hours are \"00\"–\"23\", not {hour!r}")
            if not 0 <= crew <= 100:
                raise ValueError(f"crew_schedule[{hour!r}] must be 0–100 staff")
        return dict(sorted(schedule.items()))

    @model_validator(mode="after")
    def _crew_first(self) -> "OperationsConfig":
        if self.crew_schedule and self.crew is None:
            raise ValueError("crew_schedule needs crew (the staff on duty in the other hours)")
        return self

    @field_validator("backroom_overrides")
    @classmethod
    def _backroom_units(cls, overrides: dict[str, int]) -> dict[str, int]:
        if any(not 0 <= units <= 1_000_000 for units in overrides.values()):
            raise ValueError("backroom_overrides are 0–1,000,000 units")
        return overrides

    @field_validator("stock_overrides")
    @classmethod
    def _units(cls, overrides: dict[str, int]) -> dict[str, int]:
        if any(not 0 <= units <= 10_000 for units in overrides.values()):
            raise ValueError("stock_overrides are 0–10,000 units per shelf level")
        return overrides


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


class BackroomStats(BaseModel):
    """A product whose backroom ran dry: refills that came up short."""
    sku: str
    name: str = ""
    level: int = 0                 # units in the backroom at opening of the first day (and after each delivery)
    refilled: int = 0              # units moved from the backroom to the shelves, all days
    short_units: int = 0           # units refills wanted but the backroom did not have
    dry_day: int = 0               # the first day it ran dry (weekday number)
    dry_at: str = ""               # "HH:MM:SS" that day


class EmptySpell(BaseModel):
    """A time a product's shelf face stood empty (clock seconds of the day)."""
    day: int
    rack_id: str
    face: str
    sku: str
    name: str = ""
    start: int
    end: int


class QueueHour(BaseModel):
    """The tills in one hour of the day (all simulated days together)."""
    hour: str                      # "HH" — the hour shoppers reached the tills
    arrivals: int = 0
    avg_wait_sec: float = 0.0
    max_wait_sec: float = 0.0
    abandoned: int = 0
    counters_open: int = 0         # tills staffed in the hour
    crew_on_duty: int = 0          # with a crew: staff on duty in the hour (at the tills or the shelves)
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
    backroom_units: int = 0        # units in finite backrooms at opening of the first day
    refill_short_units: int = 0    # units refills could not put on the shelves: the backroom was empty
    deliveries: int = 0            # mornings a delivery topped the backrooms up
    backroom: list[BackroomStats] = []    # products whose backroom ran dry, by units short
    crowd_skipped_units: int = 0   # unplanned picks given up at a crowded shelf
    crowd_skipped_revenue: int = 0
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
    # Crew (OperationsConfig.crew): who did what while the store was open, all days
    crew_hours: float = 0.0        # staff hours on duty
    crew_till_hours: float = 0.0   # … serving at the tills
    crew_refill_hours: float = 0.0   # … refilling shelves
    face_refills: int = 0          # shelf faces refilled
    refill_wait_min: float = 0.0   # average minutes a face waited, from its refill point to being refilled
    refill_backlog_max: int = 0    # most faces waiting for a refill at once
    refills_unfinished: int = 0    # faces still waiting at closing
    hours: list[QueueHour] = []
    stockouts: list[StockoutStats] = []   # by lost revenue, the largest first
    empty_spells: list[EmptySpell] = []   # when each face stood empty, for playback (the first few thousand)


class OperationsCosts(BaseModel):
    """What running the store costs, in the currency's minor unit, for comparing plans."""
    till_hour: int = Field(default=0, ge=0, le=10**9)          # one staffed till (or crew member) for an hour
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
    crew_hours: float = 0.0        # with a crew: staff hours on duty (what labor_cost counts instead of till hours)
    restocks: int = 0
    face_refills: int = 0          # with a crew: shelf faces refilled (it refills face by face, not in rounds)
    stock_units: int = 0           # units on the shelves and in finite backrooms at opening, each day
    labor_cost: int = 0
    restock_cost: int = 0
    holding_cost: int = 0
    net: int = 0                   # revenue less the three costs


class OperationsReplay(BaseModel):
    """A finished run's shoppers, with their decisions unchanged, replayed under another operations plan."""
    planned_revenue: int = 0       # what the shoppers meant to buy (endless stock, no line)
    outcome: OperationsOutcome = OperationsOutcome()
    report: OperationsReport = OperationsReport()
    weeks: "WeeksReport | None" = None   # with shoppers who remember (MemoryConfig), the weeks that follow


class OperationsPlan(BaseModel):
    """The best plan found by replaying the run's shoppers under many."""
    current_config: OperationsConfig = OperationsConfig()
    current: OperationsOutcome = OperationsOutcome()
    config: OperationsConfig = OperationsConfig()
    best: OperationsOutcome = OperationsOutcome()
    replays: int = 0               # plans tried
    raised_skus: list[str] = []    # products given more units per shelf level than the rest
    complete: bool = True          # False: the search stopped at its time or size limit with the best found so far
    # With shoppers who remember: the plans were judged by their money over the weeks, shown here.
    current_weeks: "WeeksReport | None" = None
    best_weeks: "WeeksReport | None" = None


class MemoryConfig(BaseModel):
    """Shoppers who remember: the run's week repeated, with the shoppers a bad visit put off staying away.

    The chances are assumptions to set from your own data (loyalty-card lapses, exit surveys), not fitted values:
    research finds that stock-outs and waits at the tills lower satisfaction and repeat visits, but not one rate."""
    weeks: int = Field(default=8, ge=2, le=52)
    # Chance a shopper stops coming, for each unit they wanted and found gone (not replaced).
    leave_per_missing_unit: float = Field(default=0.03, ge=0.0, le=1.0)
    # … for leaving the line at the tills without paying.
    leave_after_line: float = Field(default=0.25, ge=0.0, le=1.0)
    # … for each minute waited at the tills before paying.
    leave_per_wait_minute: float = Field(default=0.01, ge=0.0, le=1.0)
    # Shoppers who stop coming anyway each week (moving away, other stores) — in a perfectly run store too.
    weekly_churn: float = Field(default=0.01, ge=0.0, le=1.0)


class WeekStats(BaseModel):
    week: int                      # 1 = the run's own week
    shoppers: int = 0
    revenue: int = 0
    lost_revenue: int = 0
    abandoned: int = 0
    avg_wait_sec: float = 0.0
    net: int = 0                   # revenue less the week's operations costs
    left_for_stock: int = 0        # shoppers who stopped coming after this week, mostly over missing products
    left_for_tills: int = 0        # … mostly over the tills
    left_anyway: int = 0           # … for the weekly churn alone
    ideal_shoppers: int = 0        # with endless stock and no line (the weekly churn only)
    ideal_revenue: int = 0


class WeeksReport(BaseModel):
    """The run's week repeated under one operations plan, with shoppers who remember."""
    memory: MemoryConfig = MemoryConfig()
    weeks: list[WeekStats] = []
    shoppers_first: int = 0
    shoppers_last: int = 0
    revenue: int = 0               # all weeks
    net: int = 0
    ideal_revenue: int = 0         # all weeks with endless stock and no line
    lost_to_memory: int = 0        # revenue of shoppers who stayed away because of a visit (not the weekly churn)


OperationsReplay.model_rebuild()
OperationsPlan.model_rebuild()
