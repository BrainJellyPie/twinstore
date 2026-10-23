import random

import pytest

from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine.simulation.shared_store import counters_needed


@pytest.mark.parametrize("customers", [1, 30, 31, 60, 99, 500, 2000])
@pytest.mark.parametrize("target", [0, 30, 120])
def test_recommendation_meets_target_at_large_simultaneous_arrivals(customers, target):
    config = OperationsConfig(checkout_base_sec=60, checkout_item_sec=0, target_wait_sec=target)
    recommended = counters_needed([(Weekday.MON, 36000, 1)] * customers, config)["10"]

    def wait(tills):
        return 60 * sum(index // tills for index in range(customers)) / customers

    assert wait(recommended) <= target
    assert recommended == 1 or wait(recommended - 1) > target


@pytest.mark.parametrize("seed", range(32))
def test_mixed_baskets_days_and_hour_boundaries_match_an_independent_schedule(seed):
    rng = random.Random(261023 + seed)
    checkouts = [(rng.choice([Weekday.MON, Weekday.SAT]),
                  rng.choice([3590, 3599.75, 3600, 3600.5, 7199, 7200]) + rng.choice([0, 0, 0.25]),
                  rng.randint(1, 8)) for _ in range(rng.randint(8, 60))]
    config = OperationsConfig(checkout_base_sec=rng.choice([0, 0.5, 30, 600]), checkout_item_sec=rng.choice([0, 0.25, 3, 60]),
                              target_wait_sec=rng.choice([0, 0.5, 10, 120]))
    actual = counters_needed(checkouts, config)
    for hour, count in actual.items():
        for tills in [count, count - 1] if count > 1 else [count]:
            waits = []
            for day in {row[0] for row in checkouts}:
                free = [0.0] * tills
                for _, moment, units in sorted(row for row in checkouts if row[0] == day):
                    cashier = free.index(min(free))
                    begin = max(moment, free[cashier])
                    if f"{int(moment) // 3600 % 24:02d}" == hour:
                        waits.append(begin - moment)
                    free[cashier] = begin + config.checkout_base_sec + config.checkout_item_sec * units
            mean = sum(waits) / len(waits)
            assert (mean <= config.target_wait_sec) == (tills == count)


def test_zero_service_and_empty_input_need_no_extra_capacity():
    config = OperationsConfig(checkout_base_sec=0, checkout_item_sec=0, target_wait_sec=0)
    assert counters_needed([], config) == {}
    assert counters_needed([(Weekday.MON, 3600, 1)] * 5000, config) == {"01": 1}


def test_days_share_the_hourly_mean_without_sharing_a_queue():
    config = OperationsConfig(checkout_base_sec=60, checkout_item_sec=0, target_wait_sec=0)
    rows = [(day, 36000, 1) for day in [Weekday.MON, Weekday.FRI] for _ in range(40)]
    assert counters_needed(rows, config) == {"10": 40}


def test_operations_report_preserves_recommendations_above_the_old_cap():
    from store_emulator.domain.operations import OperationsReport
    from store_emulator.engine.simulation.shared_store import resolve_shared_store
    from tests.engine.test_shared_store import _shopper, _store

    people = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(31)]
    config = OperationsConfig(stock_per_facing=100, restock_every_min=None, checkout_base_sec=60,
                              checkout_item_sec=0, target_wait_sec=0, patience_sd=0)
    _, report = resolve_shared_store(_store(), people, config, seed=5)
    saved = OperationsReport.model_validate_json(report.model_dump_json())
    assert saved.counters == 1 and saved.queued == 31 and saved.counters_needed == 31
    assert [(hour.hour, hour.counters_needed) for hour in saved.hours] == [("10", 31)]
