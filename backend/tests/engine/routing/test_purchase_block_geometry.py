"""A multi-cell shelf offer keeps its own stance, price and block-level lock."""

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.rack import BlockFace, Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, FACE_OFFSETS, Face, Weekday
from store_emulator.engine.routing.invariants import check_buy_consistency
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import integrate_actions
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.rule_based import ImpulseOutcome, RuleBasedEngine
from tests.engine.test_purchase_quantity_limits import context_for


def shelf_store(face, rotation=0, reverse=False):
    horizontal = (face in (Face.N, Face.S)) == (rotation in (0, 180))
    slots = [Slot(block=block, face=face, level=1,
                  items=[SlotItem(sku="tea", name=f"Tea offer {block}", price=price)])
             for block, price in enumerate([100, 400])]
    rack = Rack(id="shelf", type="shelf", position=(3, 3), rotation=rotation,
                shape=[[1, 1]] if horizontal else [[1], [1]], slots=slots[::-1] if reverse else slots)
    store = Store(id="s", name="Two offers", type="shop", grid_size=(10, 10), racks=[
        rack, Rack(id="entrance", type="entrance", position=(0, 0), shape=[[1]]),
        Rack(id="exit", type="exit", position=(9, 9), shape=[[1]]),
        Rack(id="till", type="counter", position=(8, 8), shape=[[1]]),
    ])
    return store, rack


def stance(rack, slot):
    x, y = rack.occupied_positions[slot.block]
    dx, dy = FACE_OFFSETS[slot.face]
    return x + dx, y + dy


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("selected", [0, 1])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("hint", ["correct", "missing", "wrong"])
def test_unhinted_model_purchase_keeps_reached_block_price_and_position(face, rotation, selected, reverse, hint):
    store, rack = shelf_store(face, rotation, reverse)
    slot = next(slot for slot in rack.slots if slot.block == selected)
    supplied = face if hint == "correct" else None if hint == "missing" else Face.N if face != Face.N else Face.S
    action = CustomerAction(nav="path", action=Action.BUY, target=stance(rack, slot), face=supplied,
                            product_sku="tea", quantity=2, dwell=2)
    actions = integrate_actions(store, [action], [], ordering="planned")
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", EngineDecision(
        engine_type="offline", actions=actions), AStarPathFinder(), 1)
    buy = result.purchases[0]
    assert (buy.x, buy.y) == stance(rack, slot)
    assert (buy.price, buy.product_name) == (slot.items[0].price, slot.items[0].name)
    assert result.total_spent == slot.items[0].price * 2
    assert check_buy_consistency(store, [result]) == []


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("selected", [0, 1])
@pytest.mark.parametrize("blocked", [False, True])
def test_rule_planner_uses_the_selected_block_or_declines_its_blocked_stance(face, selected, blocked):
    store, rack = shelf_store(face)
    slot = rack.slots[selected]
    target = stance(rack, slot)
    if blocked:
        store.racks.append(Rack(id="wall", type="shelf", position=target, shape=[[1]]))
    engine = RuleBasedEngine(AStarPathFinder(), SimulationConfig(engines={"rule_based": {"multi_unit_prob": 0}}))
    context = context_for(store, 0)
    plan, middle = engine._begin_plan(context)
    added = engine.add_planned_buy(store, plan, middle, rack, slot, slot.items[0], "this offer")
    assert added is not blocked
    if not added:
        return
    engine.close_plan(store, plan, middle)
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", engine._finish(context, plan, ImpulseOutcome()),
                              AStarPathFinder(), 1)
    buy = result.purchases[0]
    assert (buy.x, buy.y) == target
    assert result.total_spent == plan.spend == slot.items[0].price


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("selected", [0, 1])
def test_purchase_diagnostics_only_use_the_reached_blocks_lock_and_offer(face, selected):
    store, rack = shelf_store(face)
    slot = rack.slots[selected]
    x, y = stance(rack, slot)
    from store_emulator.domain.customer import CustomerResult, TimelineEvent
    event = TimelineEvent(elapsed_sec=1, x=x, y=y, action=Action.BUY, target_rack=rack.id,
                          face=face, product_sku="tea", product_name=slot.items[0].name, price=slot.items[0].price)
    result = CustomerResult(persona_id="p", day=Weekday.MON, arrival_time="10:00:00", timeline=[event])
    rack.locked_faces = [BlockFace(block=1-selected, face=face)]
    assert check_buy_consistency(store, [result]) == []
    event.price = rack.slots[1-selected].items[0].price
    assert [v.kind for v in check_buy_consistency(store, [result])] == ["price_mismatch"]
    event.price = slot.items[0].price
    rack.locked_faces = [BlockFace(block=selected, face=face)]
    assert [v.kind for v in check_buy_consistency(store, [result])] == ["locked_face"]
