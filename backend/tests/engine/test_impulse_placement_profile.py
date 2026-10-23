"""Calibration observes the selected shelf level even when identical SKUs repeat."""

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.rack import Slot, SlotItem
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.optimize.judge import impulse_profile
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import integrate_actions
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.routing.test_purchase_block_geometry import shelf_store, stance
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("level", [1, 2, 3, 4])
@pytest.mark.parametrize("block", [0, 1])
@pytest.mark.parametrize("reverse", [False, True])
def test_selected_height_survives_routing_storage_and_calibration(face, level, block, reverse):
    store, rack = shelf_store(face)
    rack.slots = [Slot(block=b, face=face, level=h, items=[SlotItem(sku="tea", name="Tea", price=100)])
                  for b in range(2) for h in range(1, 5)]
    if reverse:
        rack.slots.reverse()
    chosen = next(slot for slot in rack.slots if (slot.block, slot.level) == (block, level))
    action = CustomerAction(nav="path", action=Action.BUY, target=stance(rack, chosen), face=face,
                            product_sku="tea", product_block=block, product_level=level, origin="impulse")
    decision = EngineDecision(engine_type="offline", actions=integrate_actions(store, [action], [], ordering="planned"))
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)
    restored = CustomerResult.model_validate_json(result.model_dump_json())
    profile = impulse_profile(store, [restored])
    assert profile.level_distribution == {h: float(h == level) for h in range(1, 5)}
    assert profile.impulse_rate == 1 and profile.impulse_revenue_share == 1
    assert (restored.purchases[0].product_block, restored.purchases[0].product_level) == (block, level)


@pytest.mark.parametrize("face", [Face.E, None])
@pytest.mark.parametrize("levels", [[2], [2, 2], [2, 4]], ids=["unique", "repeated-same", "ambiguous"])
def test_legacy_timelines_infer_only_an_unambiguous_height(face, levels):
    store = _store()
    shelf = store.racks[0]
    shelf.slots = [shelf.slots[0].model_copy(update={"level": level}, deep=True) for level in levels]
    shopper = _shopper("p", "10:00:00", [("chips", 1)], origin="impulse")
    shopper.purchases[0].face = face
    profile = impulse_profile(store, [shopper])
    assert profile.level_distribution == ({h: float(h == 2) for h in range(1, 5)} if len(set(levels)) == 1 else {})
    assert profile.impulse_rate == profile.impulse_revenue_share == 1


@pytest.mark.parametrize("ambiguous", [False, True])
def test_substitution_does_not_keep_the_original_products_height(ambiguous):
    store = _store()
    shelf = store.racks[0]
    original = shelf.slots[0].items[0]
    alternative = shelf.slots[0].items[1]
    shelf.slots = [Slot(block=0, face=Face.E, level=1, items=[original]),
                   Slot(block=0, face=Face.E, level=4, items=[alternative])]
    if ambiguous:
        shelf.slots.append(Slot(block=0, face=Face.E, level=2, items=[alternative.model_copy()]))
    shopper = _shopper("p", "10:00:00", [("chips", 1)], origin="impulse")
    raw = shopper.model_dump()
    raw["timeline"][1].update(product_block=0, product_level=1)
    shopper = CustomerResult.model_validate(raw)
    results, report = resolve_shared_store(store, [shopper], OperationsConfig(
        stock_overrides={"chips": 0}, substitute_share=1, restock_every_min=None,
        checkout_base_sec=1, checkout_item_sec=0), seed=1)
    assert report.substituted_units == 1 and results[0].purchases[0].product_sku == "nuts"
    assert impulse_profile(store, results).level_distribution == (
        {} if ambiguous else {h: float(h == 4) for h in range(1, 5)})
    assert shopper.purchases[0].product_level == 1


def test_partial_stock_preserves_the_chosen_height():
    store = _store()
    shopper = _shopper("p", "10:00:00", [("chips", 3)], origin="impulse")
    raw = shopper.model_dump()
    raw["timeline"][1].update(product_block=0, product_level=1)
    shopper = CustomerResult.model_validate(raw)
    results, report = resolve_shared_store(store, [shopper], OperationsConfig(
        stock_per_facing=1, substitute_share=0, restock_every_min=None), seed=1)
    assert report.lost_units == 2 and results[0].units_bought == 1
    assert (results[0].purchases[0].product_block, results[0].purchases[0].product_level) == (0, 1)
