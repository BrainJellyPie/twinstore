"""Shoppers who remember a visit.

The run's week is repeated. After each week, every shopper may stay away from then on: the more products they found
gone (and did without), the longer they waited at the tills, and whether they gave up in the line, the likelier.
The ones who keep coming make the same visits as before, so a store that ran out loses customers, the next weeks are
less crowded, and stock and tills stretch further — the loop a single day cannot show.

Next to it runs the same weeks in an ideal store (endless stock, no line), where shoppers leave only for the weekly
churn. Each shopper's leave-or-stay draw is the same number in both (and in every plan), so the difference is the
revenue that operations cost through customers' memory."""

import math
import random
from collections import defaultdict

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.operations import MemoryConfig, OperationsConfig, OperationsCosts, WeekStats, WeeksReport
from store_emulator.domain.store import Store
from store_emulator.domain.types import stable_seed

from .operations_plan import outcome
from .shared_store import resolve_shared_store


def _hazard(chance: float) -> float:
    return -math.log(max(1e-12, 1.0 - chance))


def simulate_weeks(
    store: Store, planned: list[CustomerResult], operations: OperationsConfig, memory: MemoryConfig,
    costs: OperationsCosts, *, seed: int,
) -> WeeksReport:
    spend: dict[str, int] = defaultdict(int)
    for result in planned:
        spend[result.persona_id] += result.total_spent
    everyone = sorted(spend)
    staying = set(everyone)
    ideal = set(everyone)
    report = WeeksReport(memory=memory, shoppers_first=len(everyone))
    away_spend = 0

    for week in range(1, memory.weeks + 1):
        visits = [r for r in planned if r.persona_id in staying]
        results, day = resolve_shared_store(store, visits, operations, seed=seed, calendar=planned)
        money = outcome(store, results, day, operations, costs)
        stats = WeekStats(
            week=week, shoppers=len(staying), revenue=money.revenue, lost_revenue=money.lost_revenue,
            abandoned=money.abandoned, avg_wait_sec=money.avg_wait_sec, net=money.net,
            ideal_shoppers=len(ideal), ideal_revenue=sum(spend[p] for p in ideal),
        )
        away_spend += sum(spend[p] for p in ideal - staying)

        missing: dict[str, int] = defaultdict(int)
        waited: dict[str, int] = defaultdict(int)
        gave_up: set[str] = set()
        for result in results:
            missing[result.persona_id] += result.lost_units
            if result.left_queue:
                gave_up.add(result.persona_id)
            else:
                waited[result.persona_id] += result.queue_wait_sec

        churn = _hazard(memory.weekly_churn)
        for shopper in sorted(staying | ideal):
            draw = random.Random(stable_seed(seed, shopper, week, "comes back")).random()
            if shopper in ideal and draw >= 1.0 - memory.weekly_churn:
                ideal.discard(shopper)
            if shopper not in staying:
                continue
            stock = _hazard(1.0 - (1.0 - memory.leave_per_missing_unit) ** missing[shopper])
            tills = (_hazard(memory.leave_after_line) if shopper in gave_up
                     else _hazard(1.0 - (1.0 - memory.leave_per_wait_minute) ** (waited[shopper] / 60.0)))
            if draw < math.exp(-(churn + stock + tills)):
                continue
            staying.discard(shopper)
            reason = max((stock, "stock"), (tills, "tills"), (churn, "anyway"))[1]
            if reason == "stock":
                stats.left_for_stock += 1
            elif reason == "tills":
                stats.left_for_tills += 1
            else:
                stats.left_anyway += 1
        report.weeks.append(stats)

    report.shoppers_last = report.weeks[-1].shoppers if report.weeks else 0
    report.revenue = sum(w.revenue for w in report.weeks)
    report.net = sum(w.net for w in report.weeks)
    report.ideal_revenue = sum(w.ideal_revenue for w in report.weeks)
    report.lost_to_memory = away_spend
    return report
