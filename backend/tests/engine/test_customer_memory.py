"""Shoppers who remember a visit stay away, and the following weeks are less crowded."""

import pytest

from store_emulator.domain.operations import MemoryConfig, OperationsConfig, OperationsCosts
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.simulation.customer_memory import simulate_weeks
from store_emulator.engine.simulation.operations_plan import plan_operations
from tests.engine.test_shared_store import _SEED, _crowd, _run, _shopper, _store

_FREE = OperationsCosts()
_NO_LINE = OperationsConfig(stock_per_facing=1, substitute_share=0.0, restock_every_min=None,
                            checkout_base_sec=1, checkout_item_sec=0)


def test_a_shopper_who_found_the_shelf_empty_stays_away_and_the_next_one_finds_it_full():
    shoppers = [_shopper("first", "10:00:00", [("chips", 1)]), _shopper("second", "10:05:00", [("chips", 1)])]
    memory = MemoryConfig(weeks=3, leave_per_missing_unit=1.0, leave_after_line=0, leave_per_wait_minute=0,
                          weekly_churn=0)
    report = simulate_weeks(_store(), shoppers, _NO_LINE, memory, _FREE, seed=1)
    assert [(w.shoppers, w.revenue, w.lost_revenue, w.left_for_stock) for w in report.weeks] == [
        (2, 300, 300, 1), (1, 300, 0, 0), (1, 300, 0, 0)]
    assert [w.ideal_shoppers for w in report.weeks] == [2, 2, 2]
    assert report.lost_to_memory == 2 * 300 and report.ideal_revenue == 3 * 600
    assert (report.shoppers_first, report.shoppers_last, report.revenue) == (2, 1, 900)


def test_a_shopper_who_gave_up_in_the_line_stays_away():
    shoppers = [_shopper(f"p{i}", "10:00:00", [("chips", 1)]) for i in range(3)]
    operations = OperationsConfig(stock_per_facing=5, checkout_base_sec=57, checkout_item_sec=3, patience_sec=90,
                                  patience_sd=0, restock_every_min=None)
    memory = MemoryConfig(weeks=2, leave_per_missing_unit=0, leave_after_line=1.0, leave_per_wait_minute=0,
                          weekly_churn=0)
    report = simulate_weeks(_store(), shoppers, operations, memory, _FREE, seed=1)
    assert report.weeks[0].abandoned == 1 and report.weeks[0].left_for_tills == 1
    # With one fewer in line, nobody waits past their patience the week after.
    assert report.weeks[1].shoppers == 2 and report.weeks[1].abandoned == 0


def test_a_well_run_store_keeps_everyone_but_the_weekly_churn():
    shoppers = [_shopper(f"p{i}", f"10:{i:02d}:00", [("chips", 1)]) for i in range(20)]
    memory = MemoryConfig(weeks=6, weekly_churn=0.2)
    report = simulate_weeks(_store(), shoppers, OperationsConfig(stock_per_facing=100, checkout_base_sec=1,
                            checkout_item_sec=0), memory, _FREE, seed=5)
    assert [w.shoppers for w in report.weeks] == [w.ideal_shoppers for w in report.weeks]
    assert report.lost_to_memory == 0 and report.revenue == report.ideal_revenue
    assert report.weeks[-1].shoppers < 20
    assert all(w.left_for_stock == w.left_for_tills == 0 for w in report.weeks)
    assert sum(w.left_anyway for w in report.weeks[:-1]) == 20 - report.weeks[-1].shoppers


def test_every_plan_faces_the_same_leave_or_stay_draws():
    shoppers = [_shopper(f"p{i}", f"10:{i:02d}:00", [("chips", 1)]) for i in range(30)]
    memory = MemoryConfig(weeks=5, weekly_churn=0.15, leave_per_missing_unit=0.5)
    tight = simulate_weeks(_store(), shoppers, _NO_LINE, memory, _FREE, seed=9)
    roomy = simulate_weeks(_store(), shoppers, _NO_LINE.model_copy(update={"stock_per_facing": 50}), memory, _FREE,
                           seed=9)
    assert [w.ideal_shoppers for w in tight.weeks] == [w.ideal_shoppers for w in roomy.weeks]
    assert all(w.shoppers <= w.ideal_shoppers for w in tight.weeks)
    assert all(t.shoppers <= r.shoppers for t, r in zip(tight.weeks, roomy.weeks))
    assert tight.lost_to_memory > roomy.lost_to_memory == 0


def test_a_crowded_store_that_runs_out_loses_shoppers_and_then_runs_out_less():
    store = generate_store("urban_cvs")
    _, customers = _run(store, _crowd(150), None)
    report = simulate_weeks(store, customers, OperationsConfig(stock_per_facing=1, restock_every_min=None),
                            MemoryConfig(weeks=6, leave_per_missing_unit=0.2), _FREE, seed=_SEED)
    first, last = report.weeks[0], report.weeks[-1]
    assert last.shoppers < first.shoppers and sum(w.left_for_stock for w in report.weeks) > 0
    assert last.lost_revenue < first.lost_revenue
    assert report.lost_to_memory > 0


def test_a_plan_judged_over_weeks_reports_them_and_never_does_worse():
    store = generate_store("urban_cvs")
    _, customers = _run(store, _crowd(100), None)
    current = OperationsConfig(stock_per_facing=1, restock_every_min=None)
    plan = plan_operations(store, customers, current, OperationsCosts(stock_unit_day=1), seed=_SEED,
                           memory=MemoryConfig(weeks=4, leave_per_missing_unit=0.2))
    assert plan.current_weeks is not None and plan.best_weeks is not None
    assert plan.best_weeks.net >= plan.current_weeks.net
    assert len(plan.best_weeks.weeks) == 4


@pytest.mark.parametrize("bad", [{"weeks": 1}, {"weeks": 53}, {"weekly_churn": 1.5}, {"leave_after_line": -0.1}])
def test_impossible_memory_settings_are_refused(bad):
    with pytest.raises(ValueError):
        MemoryConfig(**bad)
