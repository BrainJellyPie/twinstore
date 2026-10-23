"""POS receipt clocks must be compared with checkout completion, including queued visits."""

from datetime import datetime, timedelta

import pytest

from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.types import Action
from store_emulator.engine.analysis.fidelity import PosLine, fidelity_report
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.test_shared_store import _shopper, _store


def score(shoppers, hours):
    report = fidelity_report(_store(), shoppers, [
        PosLine(transaction_id=str(i), sku="chips", unit_price=300, hour=hour)
        for i, hour in enumerate(hours)
    ])
    return {m.name: m.value for m in report.metrics}.get("hourly_js_similarity"), report


@pytest.mark.parametrize("hour", range(24))
@pytest.mark.parametrize("offset,duration", [(0, 0), (19, 1), (20, 0), (3600, 60)])
def test_hour_and_midnight_boundaries_use_recorded_checkout(hour, offset, duration):
    arrival = datetime(2026, 10, 25, hour, 59, 40)
    shopper = _shopper("p", arrival.strftime("%H:%M:%S"), [("chips", 1)])
    pay = next(e for e in shopper.timeline if e.action == Action.PAY)
    pay.elapsed_sec, pay.duration = offset, duration
    # Deliberately stale leave_time: the recorded checkout, not a summary clock, is authoritative.
    shopper.leave_time = "09:00:00"
    expected = (arrival + timedelta(seconds=offset + duration)).hour
    value, _ = score([shopper], [expected])
    assert value == 1


def test_queue_delay_is_counted_once_before_receipt_completion():
    shoppers = [_shopper(str(i), "10:59:00", [("chips", 1)]) for i in range(2)]
    resolved, _ = resolve_shared_store(_store(), shoppers, OperationsConfig(
        checkout_base_sec=20, checkout_item_sec=0, restock_every_min=None), seed=1)
    assert [c.queue_wait_sec for c in resolved] == [0, 20]
    value, _ = score(resolved, [10, 11])
    assert value == 1


@pytest.mark.parametrize("arrival", ["10:00:00", "unknown", "", "10:99:00"])
def test_missing_checkout_is_not_guessed_from_arrival(arrival):
    legacy = _shopper("old", arrival, [("chips", 1)], pay=False)
    value, report = score([legacy], [10])
    assert value is None
    assert any("checkout" in note for note in report.notes)
    assert report.real_transactions == 1
    assert next(m.value for m in report.metrics if m.name == "basket_value_w1") == 0


def test_mixed_legacy_and_recorded_visits_only_use_known_transaction_times():
    old = _shopper("old", "08:00:00", [("chips", 1)], pay=False)
    current = _shopper("new", "10:59:40", [("chips", 1)])
    value, report = score([old, current], [11])
    assert value == 1
    assert any("1" in note and "checkout" in note for note in report.notes)


def test_non_buyers_do_not_add_checkout_transactions():
    buyer = _shopper("buyer", "10:59:40", [("chips", 1)])
    visitor = _shopper("visitor", "09:00:00", [])
    assert score([buyer, visitor], [11])[0] == 1


@pytest.mark.parametrize("arrival", ["unknown", "", "10:99:00", "24:00:00", "10:00:00+09:00"])
def test_unusable_arrival_clock_does_not_manufacture_transaction_time(arrival):
    buyer = _shopper("buyer", arrival, [("chips", 1)])
    value, report = score([buyer], [10])
    assert value is None and any("checkout" in note for note in report.notes)
