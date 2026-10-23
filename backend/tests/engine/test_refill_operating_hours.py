"""A fixed restock schedule follows store hours even when its shoppers leave early."""

import pytest

from store_emulator.domain.operations import OperationsConfig, OperationsCosts
from store_emulator.domain.types import Weekday
from store_emulator.engine.simulation.operations_plan import replay
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("interval", [30, 60, 120, 240, 360])
@pytest.mark.parametrize("stock", [1, 2, 3])
@pytest.mark.parametrize("reserve", [1, 2])
@pytest.mark.parametrize("delivery", [False, True])
def test_a_nonbuying_observer_cannot_change_next_days_stock_and_revenue(interval, stock, reserve, delivery):
    store = _store()
    shoppers = [_shopper("mon", "09:00:00", [("chips", 1)])]
    shoppers += [_shopper(f"tue{i}", f"08:{5 + i:02d}:00", [("chips", 1)], day=Weekday.TUE)
                 for i in range(stock)]
    # Consume from Tuesday's first refill as well as its opening shelf stock.
    late_hour = 9 + interval // 60
    shoppers.append(_shopper("tue_late", f"{late_hour:02d}:00:00", [("chips", 1)], day=Weekday.TUE))
    observer = _shopper("observer", "21:00:00", [], pay=False)
    config = OperationsConfig(stock_per_facing=stock, backroom_per_product=reserve, daily_delivery=delivery,
                              restock_every_min=interval, substitute_share=0, checkout_base_sec=1,
                              checkout_item_sec=0, crowd_limit=None)
    costs = OperationsCosts(till_hour=1000, restock_round=100, stock_unit_day=1)
    before = [shopper.model_dump() for shopper in shoppers]
    money, report, played = replay(store, shoppers, config, costs, seed=1)
    control_money, control_report, control_played = replay(store, [*shoppers, observer], config, costs, seed=1)
    assert money == control_money
    assert report == control_report
    assert played == control_played[:-1]
    assert [shopper.model_dump() for shopper in shoppers] == before


def test_morning_delivery_follows_the_previous_days_last_scheduled_refill():
    shoppers = [_shopper("mon", "09:00:00", [("chips", 1)]),
                _shopper("tue1", "08:05:00", [("chips", 1)], day=Weekday.TUE),
                _shopper("tue2", "08:06:00", [("chips", 1)], day=Weekday.TUE),
                _shopper("tue3", "11:00:00", [("chips", 1)], day=Weekday.TUE)]
    config = OperationsConfig(stock_per_facing=2, backroom_per_product=1, daily_delivery=True,
                              restock_every_min=120, substitute_share=0, checkout_base_sec=1, checkout_item_sec=0)
    money, report, played = replay(_store(), shoppers, config, OperationsCosts(restock_round=100), seed=1)
    assert money.revenue == 1200
    assert [shopper.total_spent for shopper in played] == [300] * 4
    assert report.restocks == 2
    assert report.deliveries == 1
    assert money.restock_cost == 200


@pytest.mark.parametrize("interval, rounds", [(30, 1), (60, 1), (120, 0)])
def test_refill_scheduled_exactly_at_closing_does_not_run(interval, rounds):
    store = _store()
    for day in store.weekly_schedule:
        day.close_hour = 10
    shoppers = [_shopper("early", "08:00:00", [("chips", 1)]), _shopper("observer", "09:59:30", [], pay=False)]
    config = OperationsConfig(stock_per_facing=1, restock_every_min=interval, checkout_base_sec=1, checkout_item_sec=0)
    _, report, _ = replay(store, shoppers, config, OperationsCosts(), seed=1)
    assert report.restocks == rounds


def test_shoppers_finishing_after_closing_do_not_trigger_another_refill():
    shoppers = [_shopper("late", "21:59:30", [("chips", 1)])]
    config = OperationsConfig(stock_per_facing=1, restock_every_min=120, checkout_base_sec=1, checkout_item_sec=0)
    _, report, _ = replay(_store(), shoppers, config, OperationsCosts(), seed=1)
    assert report.restocks == 0


def test_a_legacy_store_without_opening_hours_keeps_its_observed_visit_window():
    store = _store()
    store.weekly_schedule = []
    shoppers = [_shopper("early", "08:00:00", [("chips", 1)])]
    config = OperationsConfig(stock_per_facing=1, restock_every_min=120)
    _, short, _ = replay(store, shoppers, config, OperationsCosts(), seed=1)
    _, longer, _ = replay(store, [*shoppers, _shopper("observer", "11:00:00", [], pay=False)],
                          config, OperationsCosts(), seed=1)
    assert short.restocks == 0
    assert longer.restocks == 1
