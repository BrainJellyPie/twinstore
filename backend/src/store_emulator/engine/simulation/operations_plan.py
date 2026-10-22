"""Operations plans tried on a finished run.

The shoppers' visits — what each meant to buy, where and when — were decided once, by whatever engine ran them.
Stock, refills and tills only decide what of it happens, so any other operations plan replays in milliseconds on the
same shoppers, with no model call: the same shoppers, the same patience, only the store run differently.

The search maximises revenue less the cost of staffed till hours, refill rounds and units kept on the shelves — over
the weeks that follow when shoppers remember their visits (customer_memory.py). Ties go to the plan using less (fewer
refills, fewer units, fewer till hours)."""

import logging
import time
from collections.abc import Iterable

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.operations import (
    MemoryConfig, OperationsConfig, OperationsCosts, OperationsOutcome, OperationsPlan, OperationsReport, WeeksReport,
)
from store_emulator.domain.store import Store

from .shared_store import resolve_shared_store, shelf_stock

logger = logging.getLogger(__name__)

_REFILLS: tuple[int | None, ...] = (None, 30, 60, 90, 120, 180, 240, 360)
_STOCKS: tuple[int, ...] = (2, 3, 4, 6, 8, 12, 16, 24, 32, 48)
_RAISED = 30            # products, by revenue lost, whose own shelf stock the search tries to raise
_MAX_REPLAYS = 600
_TIME_BUDGET_SEC = 25.0   # a large run answers with the best plan found so far instead of keeping the page waiting


def replay(
    store: Store, planned: list[CustomerResult], config: OperationsConfig, costs: OperationsCosts, *, seed: int,
) -> tuple[OperationsOutcome, OperationsReport, list[CustomerResult]]:
    results, report = resolve_shared_store(store, planned, config, seed=seed)
    return outcome(store, results, report, config, costs), report, results


def outcome(
    store: Store, results: list[CustomerResult], report: OperationsReport, config: OperationsConfig,
    costs: OperationsCosts,
) -> OperationsOutcome:
    units = sum(p.full for p in shelf_stock(store, config).values())
    labor = round(report.till_hours * costs.till_hour)
    refills = report.restocks * costs.restock_round
    holding = units * max(1, report.days) * costs.stock_unit_day
    revenue = sum(r.total_spent for r in results)
    return OperationsOutcome(
        revenue=revenue, lost_revenue=report.lost_revenue, abandoned_revenue=report.abandoned_revenue,
        abandoned=report.abandoned, avg_wait_sec=report.avg_wait_sec, p90_wait_sec=report.p90_wait_sec,
        till_hours=report.till_hours, restocks=report.restocks, stock_units=units,
        labor_cost=labor, restock_cost=refills, holding_cost=holding, net=revenue - labor - refills - holding,
    )


type _Tried = tuple[OperationsOutcome, OperationsReport, WeeksReport | None]


def _better(a: _Tried, b: _Tried) -> bool:
    """Whether plan a beats plan b: more net money (over the weeks, when shoppers remember), then less used."""
    def key(tried: _Tried) -> tuple[float, ...]:
        day, _, weeks = tried
        return (weeks.net if weeks is not None else day.net, -day.restocks, -day.stock_units, -day.till_hours)
    return key(a) > key(b)


def plan_operations(
    store: Store, planned: list[CustomerResult], current: OperationsConfig, costs: OperationsCosts, *, seed: int,
    max_tills: int | None = None, time_budget_sec: float = _TIME_BUDGET_SEC, memory: MemoryConfig | None = None,
) -> OperationsPlan:
    """The best refill interval, shelf stock, per-product stock and hourly tills found for these shoppers."""
    from .customer_memory import simulate_weeks   # builds on this module's outcome()

    deadline = time.monotonic() + time_budget_sec
    stopped = False
    tills = len(store.counters)
    limit = min(tills, max_tills) if max_tills is not None else tills
    tried = 0
    cache: dict[str, _Tried] = {}

    def run(config: OperationsConfig) -> _Tried:
        nonlocal tried
        key = config.model_dump_json()
        if key not in cache:
            tried += 1
            result, report, _ = replay(store, planned, config, costs, seed=seed)
            weeks = simulate_weeks(store, planned, config, memory, costs, seed=seed) if memory is not None else None
            cache[key] = (result, report, weeks)
        return cache[key]

    now_tried = run(current)
    best_config, best_tried = current, now_tried

    def consider(candidates: Iterable[OperationsConfig]) -> None:
        nonlocal best_config, best_tried, stopped
        for candidate in candidates:
            if tried >= _MAX_REPLAYS or time.monotonic() > deadline:
                stopped = True
                return
            result = run(candidate)
            if _better(result, best_tried):
                best_config, best_tried = candidate, result

    # 1. Refill interval and shelf stock together (they trade off against each other).
    consider(
        current.model_copy(update={"restock_every_min": refill, "stock_per_facing": stock})
        for refill in sorted(set(_REFILLS) | {current.restock_every_min}, key=lambda r: (r is None, r or 0))
        for stock in sorted(set(_STOCKS) | {current.stock_per_facing})
    )

    # 2. More units for the products that still run out and lose money.
    raised: list[str] = []
    for stats in [s for s in best_tried[1].stockouts if s.lost_revenue > 0][:_RAISED]:
        base = best_config.stock_overrides.get(stats.sku, best_config.stock_per_facing)
        before = best_config
        consider(
            best_config.model_copy(update={"stock_overrides": {**best_config.stock_overrides, stats.sku: units}})
            for units in (base * 2, base * 3, base * 4) if units <= 10_000
        )
        if best_config is not before:
            raised.append(stats.sku)

    # 3. Tills hour by hour, twice over (an hour's line spills into the next).
    hours = [h.hour for h in best_tried[1].hours]
    if limit > 0 and hours:
        for _ in range(2):
            for hour in hours:
                consider(
                    best_config.model_copy(update={"till_schedule": {**best_config.till_schedule, hour: n}})
                    for n in range(1, limit + 1)
                )

    logger.info(f"[operations plan] {tried} plans tried; net {now_tried[0].net} → {best_tried[0].net}")
    return OperationsPlan(current_config=current, current=now_tried[0], config=best_config, best=best_tried[0],
                          replays=tried, raised_skus=sorted(set(raised)), complete=not stopped,
                          current_weeks=now_tried[2], best_weeks=best_tried[2])
