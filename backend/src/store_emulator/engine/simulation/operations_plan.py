"""Operations plans tried on a finished run.

The shoppers' visits — what each meant to buy, where and when — were decided once, by whatever engine ran them.
Stock, refills and tills only decide what of it happens, so any other operations plan replays in milliseconds on the
same shoppers, with no model call: the same shoppers, the same patience, only the store run differently.

The search maximises revenue less the cost of staffed till hours (or crew hours, with a crew), refill rounds and units
kept on the shelves — over the weeks that follow when shoppers remember their visits (customer_memory.py). Ties go to
the plan using less (fewer refills, fewer units, fewer till and crew hours)."""

import logging
import time
from collections.abc import Iterable

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.operations import (
    CrewShift, MemoryConfig, OperationsConfig, OperationsCosts, OperationsOutcome, OperationsPlan, OperationsReport,
    RosterRules, WeeksReport,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import Weekday

from .shared_store import open_hours, resolve_shared_store, shelf_stock

logger = logging.getLogger(__name__)

_REFILLS: tuple[int | None, ...] = (None, 30, 60, 90, 120, 180, 240, 360)
_STOCKS: tuple[int, ...] = (2, 3, 4, 6, 8, 12, 16, 24, 32, 48)
_REFILL_POINTS: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75)   # with a crew: refill a face once down to this share
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
    units = sum(p.full for p in shelf_stock(store, config).values()) + report.backroom_units
    labor = round((report.crew_hours if config.crew is not None else report.till_hours) * costs.till_hour)
    refills = report.restocks * costs.restock_round
    holding = units * max(1, report.days) * costs.stock_unit_day
    revenue = sum(r.total_spent for r in results)
    return OperationsOutcome(
        revenue=revenue, lost_revenue=report.lost_revenue, abandoned_revenue=report.abandoned_revenue,
        abandoned=report.abandoned, avg_wait_sec=report.avg_wait_sec, p90_wait_sec=report.p90_wait_sec,
        till_hours=report.till_hours, crew_hours=report.crew_hours, restocks=report.restocks,
        face_refills=report.face_refills, stock_units=units,
        labor_cost=labor, restock_cost=refills, holding_cost=holding, net=revenue - labor - refills - holding,
    )


type _Tried = tuple[OperationsOutcome, OperationsReport, WeeksReport | None]


def _better(a: _Tried, b: _Tried) -> bool:
    """Whether plan a beats plan b: more net money (over the weeks, when shoppers remember), then less used."""
    def key(tried: _Tried) -> tuple[float, ...]:
        day, _, weeks = tried
        return (weeks.net if weeks is not None else day.net, -day.restocks, -day.stock_units, -day.crew_hours,
                -day.till_hours)
    return key(a) > key(b)


def plan_operations(
    store: Store, planned: list[CustomerResult], current: OperationsConfig, costs: OperationsCosts, *, seed: int,
    max_tills: int | None = None, time_budget_sec: float = _TIME_BUDGET_SEC, memory: MemoryConfig | None = None,
    max_crew: int | None = None, roster: RosterRules | None = None,
) -> OperationsPlan:
    """The best refill interval, shelf stock, per-product stock and hourly tills found for these shoppers — with a
    crew, the best refill point, shelf stock, per-product stock and crew hour by hour."""
    from .customer_memory import simulate_weeks   # builds on this module's outcome()

    deadline = time.monotonic() + time_budget_sec
    stopped = False
    tills = len(store.counters)
    limit = min(tills, max_tills) if max_tills is not None else tills
    tried = 0
    cache: dict[str, _Tried] = {}

    def bounded(config: OperationsConfig) -> OperationsConfig:
        updates: dict[str, object] = {}
        if config.crew is None and max_tills is not None:
            opened = config.open_counters
            if opened is not None:
                opened = min(opened, max_tills)
            elif tills > max_tills:
                opened = max_tills
            updates.update(open_counters=opened,
                           till_schedule={hour: min(n, max_tills) for hour, n in config.till_schedule.items()})
        elif config.crew is not None and max_crew is not None:
            updates.update(crew=min(config.crew, max_crew),
                           crew_schedule={hour: min(n, max_crew) for hour, n in config.crew_schedule.items()})
            # Respect simultaneous staff, not just each shift's headcount. Keep
            # earlier shifts first and preserve their days and duration.
            covered = [[0] * 24 for _ in range(7)]
            shifts: list[CrewShift] = []
            for shift in config.crew_shifts:
                days = shift.days or list(range(1, 8))
                room = min(max_crew - covered[day - 1][hour] for day in days for hour in range(shift.start, shift.end))
                staff = min(shift.staff, room)
                if staff <= 0:
                    continue
                shifts.append(shift.model_copy(update={"staff": staff}))
                for day in days:
                    for hour in range(shift.start, shift.end):
                        covered[day - 1][hour] += staff
            updates["crew_shifts"] = shifts
        return config.model_copy(update=updates) if updates else config

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
    # The original remains the comparison baseline, but cannot win outside the
    # requested feasible set, even when the search deadline has already elapsed.
    best_config = bounded(current)
    best_tried = run(best_config)

    def consider(candidates: Iterable[OperationsConfig]) -> None:
        nonlocal best_config, best_tried, stopped
        for candidate in candidates:
            if tried >= _MAX_REPLAYS or time.monotonic() > deadline:
                stopped = True
                return
            candidate = bounded(candidate)
            result = run(candidate)
            if _better(result, best_tried):
                best_config, best_tried = candidate, result

    # 1. Refill interval (with a crew, refill point) and shelf stock together: they trade off against each other.
    if current.crew is not None:
        consider(
            current.model_copy(update={"refill_at": point, "stock_per_facing": stock})
            for point in sorted(set(_REFILL_POINTS) | {current.refill_at})
            for stock in sorted(set(_STOCKS) | {current.stock_per_facing})
        )
    else:
        consider(
            current.model_copy(update={"restock_every_min": refill, "stock_per_facing": stock})
            for refill in sorted(set(_REFILLS) | {current.restock_every_min}, key=lambda r: (r is None, r or 0))
            for stock in sorted(set(_STOCKS) | {current.stock_per_facing})
        )

    # 2. A backroom kept at another level (when the store has one): fewer refills come up short, more units held.
    if best_config.backroom_per_product is not None:
        level = best_config.backroom_per_product
        consider(best_config.model_copy(update={"backroom_per_product": units})
                 for units in sorted({0, level // 2, level * 2, level * 4, max(1, level) * 8} - {level}) if units <= 1_000_000)

    # 3. More units for the products that still run out and lose money.
    raised: list[str] = []
    for stats in [s for s in best_tried[1].stockouts if s.lost_revenue > 0][:_RAISED]:
        base = best_config.stock_overrides.get(stats.sku, best_config.stock_per_facing)
        candidates = (1, 2, 3, 4) if base == 0 else (base * 2, base * 3, base * 4)   # 0: it started sold out
        before = best_config
        consider(
            best_config.model_copy(update={"stock_overrides": {**best_config.stock_overrides, stats.sku: units}})
            for units in candidates if units <= 10_000
        )
        if best_config is not before:
            raised.append(stats.sku)

    # 4. Crew (or tills) hour by hour, twice over (an hour's line or refill backlog spills into the next).
    if current.crew is not None and not current.crew_shifts:
        largest = max([current.crew, *current.crew_schedule.values()])
        crew_limit = min(100, max_crew if max_crew is not None else max(largest, tills) + 2)
        for _ in range(2):
            for hour in open_hours(store, planned):
                consider(
                    best_config.model_copy(update={"crew_schedule": {**best_config.crew_schedule, hour: n}})
                    for n in range(1, crew_limit + 1)
                )
        # The most common positive crew becomes the default; unstaffed hours stay explicit — if that plays the same.
        if best_config.crew is not None and best_config.crew_schedule:
            staffed = [best_config.crew_schedule.get(hour, best_config.crew) for hour in open_hours(store, planned)]
            common = min((n for n in set(staffed) if n > 0),
                         key=lambda n: (-staffed.count(n), n), default=best_config.crew)
            tidy = best_config.model_copy(update={"crew": common, "crew_schedule": {
                hour: n for hour, n in best_config.crew_schedule.items() if n != common}})
            if tidy != best_config and run(tidy)[0] == best_tried[0]:
                best_config = tidy

    # 5. A roster: shifts of a workable length that cover the hours' crew, then trimmed shift by shift and weekday by
    #    weekday while that leaves more money.
    if current.crew is not None and (roster is not None or current.crew_shifts):
        rules = roster or RosterRules()
        hours = [int(hour) for hour in open_hours(store, planned)]
        days = sorted({int(result.day) for result in planned})
        if roster is not None and any(not rules.min_hours <= shift.end - shift.start <= rules.max_hours
                                      for shift in best_config.crew_shifts):
            # Rebuild invalid shifts before comparing money: a cheaper plan outside the requested limits cannot win.
            spans: dict[tuple[int, int, int, int], list[int]] = {}
            for day in range(1, 8):
                schedule = store.schedule_for(Weekday(day))
                day_hours = hours if not store.weekly_schedule else []
                if schedule is not None and schedule.is_open:
                    day_hours = list(range(schedule.open_hour, schedule.close_hour))
                need = {hour: best_config.crew_on_duty(day, hour) for hour in day_hours}
                copies: dict[tuple[int, int, int], int] = {}
                for shift in cover(need, rules):
                    span = (shift.start, shift.end, shift.staff)
                    index = copies.get(span, 0)
                    spans.setdefault((*span, index), []).append(day)
                    copies[span] = index + 1
            shifts = [CrewShift(start=start, end=end, staff=staff, days=[] if len(on_days) == 7 else on_days)
                      for (start, end, staff, _), on_days in sorted(spans.items())]
            settings = best_config.model_dump()
            settings["crew_shifts"] = shifts
            if not shifts:
                settings["crew_schedule"] = {f"{hour:02d}": 0 for hour in range(24)}
            best_config = bounded(OperationsConfig.model_validate(settings))
            best_tried = run(best_config)
        if not best_config.crew_shifts and hours and days:
            need = {hour: max(best_config.crew_on_duty(day, hour) for day in days) for hour in hours}
            covering = bounded(best_config.model_copy(update={"crew_shifts": cover(need, rules)}))
            # The roster replaces the hourly plan even when it costs more: hourly numbers are not a rota anyone works.
            best_config, best_tried = covering, run(covering)
        for _ in range(3):
            before = best_config
            for index in range(len(best_config.crew_shifts)):
                if index >= len(best_config.crew_shifts):
                    break
                consider(_reshaped(best_config, index, rules, days, (min(hours), max(hours) + 1) if hours else (0, 24)))
            if best_config is before:
                break
    hours = [h.hour for h in best_tried[1].hours] if current.crew is None else []
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


def cover(need: dict[int, int], rules: RosterRules) -> list[CrewShift]:
    """Shifts of rules.min_hours to rules.max_hours that put at least `need[hour]` staff on duty in each hour, from
    the first hour on: each new shift runs while the hours ahead still lack someone, up to the longest shift."""
    if not need:
        return []
    first, last = min(need), max(need) + 1
    if any(need.values()) and last - first < rules.min_hours:
        raise ValueError(f"the shortest shift ({rules.min_hours} hours) exceeds the operating window "
                         f"({last - first} hours); lower the shortest shift or extend the store's opening hours")
    covered = dict.fromkeys(range(first, last), 0)
    spans: dict[tuple[int, int], int] = {}
    for hour in range(first, last):
        while covered[hour] < need.get(hour, 0):
            end = min(last, hour + rules.min_hours)
            while end < last and end - hour < rules.max_hours and need.get(end, 0) > covered[end]:
                end += 1
            start = max(first, end - rules.min_hours) if end - hour < rules.min_hours else hour
            for covered_hour in range(start, end):
                covered[covered_hour] += 1
            spans[(start, end)] = spans.get((start, end), 0) + 1
    return [CrewShift(start=start, end=end, staff=min(100, staff - offset))
            for (start, end), staff in sorted(spans.items()) for offset in range(0, staff, 100)]


def _reshaped(
    config: OperationsConfig, index: int, rules: RosterRules, days: list[int], day_hours: tuple[int, int],
) -> Iterable[OperationsConfig]:
    """The roster with shift `index` changed one step: dropped (or one fewer on it), an hour earlier or later at
    either end within the shift lengths and opening hours, or off on one of the simulated weekdays."""
    shifts = config.crew_shifts
    shift = shifts[index]
    first, last = day_hours

    def with_shift(changed: CrewShift | None) -> OperationsConfig:
        rest = [s for i, s in enumerate(shifts) if i != index]
        return config.model_copy(update={"crew_shifts": [*rest[:index], changed, *rest[index:]] if changed else rest})

    if len(shifts) > 1 or shift.staff > 1:
        yield with_shift(shift.model_copy(update={"staff": shift.staff - 1}) if shift.staff > 1 else None)
    for start, end in ((shift.start + 1, shift.end), (shift.start - 1, shift.end),
                       (shift.start, shift.end - 1), (shift.start, shift.end + 1)):
        if first <= start < end <= last and rules.min_hours <= end - start <= rules.max_hours:
            yield with_shift(CrewShift(start=start, end=end, days=shift.days, staff=shift.staff))
    working = shift.days or days
    if len(working) > 1:
        for day in working:
            yield with_shift(CrewShift(start=shift.start, end=shift.end, staff=shift.staff,
                                       days=[d for d in working if d != day]))
