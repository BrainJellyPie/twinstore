"""Stock replacements must be available at the shopper's actual shelf position."""

import pytest

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.rack import Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.engine.routing.invariants import check_buy_consistency
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.test_shared_store import _shopper, _store


def visit(face, saved=False):
    store = _store()
    rack = store.racks[0]
    vertical = face in (Face.E, Face.W)
    rack.shape = [[1], [1]] if vertical else [[1, 1]]
    rack.position = (2, 2)
    rack.slots = [Slot(block=0, face=face, level=1,
                       items=[SlotItem(sku="chips", name="Chips", price=300)])]
    shopper = _shopper("buyer", "10:00:00", [("chips", 1)])
    event = shopper.timeline[1]
    dx, dy = {Face.E: (1, 0), Face.W: (-1, 0), Face.N: (0, -1), Face.S: (0, 1)}[face]
    event.x, event.y = 2 + dx, 2 + dy
    event.face = face
    event.product_block, event.product_level = 0, 1
    return store, CustomerResult.model_validate_json(shopper.model_dump_json()) if saved else shopper


def replay(store, shopper):
    return resolve_shared_store(store, [shopper], OperationsConfig(
        stock_overrides={"chips": 0}, restock_every_min=None, substitute_share=1,
        checkout_base_sec=1, checkout_item_sec=0, crowd_limit=None,
    ), seed=1)


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("saved", [False, True])
def test_a_different_block_on_the_same_rack_face_cannot_supply_a_replacement(face, saved):
    store, shopper = visit(face, saved)
    store.racks[0].slots.append(Slot(block=1, face=face, level=1,
                                    items=[SlotItem(sku="nuts", name="Nuts", price=350)]))
    before = shopper.model_dump_json()
    results, report = replay(store, shopper)
    assert results[0].total_spent == 0
    assert report.substituted_units == 0 and report.lost_units == 1
    assert check_buy_consistency(store, results) == []
    assert shopper.model_dump_json() == before


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("local_price, remote_price, budget, expected", [
    (500, 350, 400, 0), (350, 500, 400, 350), (0, 500, 0, 0), (500, 350, None, 500),
])
def test_the_local_offer_supplies_the_name_price_and_budget_check(face, local_price, remote_price, budget, expected):
    store, shopper = visit(face)
    shopper.spend_limit = budget
    # The other block is deliberately first in storage, with the same SKU but a different offer.
    store.racks[0].slots.extend([
        Slot(block=1, face=face, level=1, items=[SlotItem(sku="nuts", name="Remote nuts", price=remote_price)]),
        Slot(block=0, face=face, level=3, items=[SlotItem(sku="nuts", name="Local nuts", price=local_price)]),
    ])
    results, report = replay(store, shopper)
    assert results[0].total_spent == expected
    assert check_buy_consistency(store, results) == []
    if local_price == 0 or expected:
        bought = results[0].purchases[0]
        assert (bought.product_name, bought.price, bought.product_block, bought.product_level) == (
            "Local nuts", local_price, 0, 3,
        )
        assert report.substituted_units == 1
    else:
        assert report.substituted_units == 0


@pytest.mark.parametrize("budget", [None, 350])
def test_multiple_levels_choose_the_nearest_affordable_actual_offer(budget):
    store, shopper = visit(Face.E)
    shopper.spend_limit = budget
    store.racks[0].slots.extend([
        Slot(block=0, face=Face.E, level=2, items=[SlotItem(sku="nuts", name="Large nuts", price=900)]),
        Slot(block=0, face=Face.E, level=4, items=[SlotItem(sku="nuts", name="Small nuts", price=325)]),
    ])
    results, report = replay(store, shopper)
    assert results[0].total_spent == 325 and report.substituted_units == 1
    bought = results[0].purchases[0]
    assert (bought.product_name, bought.product_block, bought.product_level) == ("Small nuts", 0, 4)
    assert check_buy_consistency(store, results) == []
