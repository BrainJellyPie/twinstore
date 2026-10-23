"""Optional model coordinates must not permit remote purchases and payment."""

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import build_journey
from store_emulator.engine.routing.timeline_builder import build_timeline
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import drop_invalid_buys


@pytest.mark.parametrize("index", [0, -1])
@pytest.mark.parametrize("diagonal", [False, True])
@pytest.mark.parametrize("missing_buy", [False, True])
@pytest.mark.parametrize("missing_pay", [False, True])
def test_known_sku_and_checkout_get_reached_when_coordinates_are_omitted(index, diagonal, missing_buy, missing_pay):
    store = generate_store("compact_cvs", seed=0)
    rack = store.product_racks[index]
    slot = rack.slots[0]
    item = slot.items[0]
    grid = store.walkable_grid()
    stance = next(tile for tile in rack.access_tiles(store.grid_size)
                  if rack.accepts_face_at(tile, slot.face, store.grid_size) and grid[tile[1]][tile[0]])
    counter = store.counters[0]
    checkout = next(tile for tile in counter.service_access_tiles(store.grid_size) if grid[tile[1]][tile[0]])
    actions = [
        CustomerAction(nav="path", action=Action.BUY, product_sku=item.sku, face=slot.face,
                       target=None if missing_buy else stance, quantity=2, dwell=5),
        CustomerAction(nav="path", action=Action.PAY, target=None if missing_pay else checkout, dwell=10),
        CustomerAction(nav="leave"),
    ]
    before = [action.model_dump() for action in actions]
    kept, dropped = drop_invalid_buys(actions, store)
    assert dropped == 0
    journey = build_journey(store, kept, AStarPathFinder(diagonal=diagonal), block_move_sec=3)
    result = build_timeline("p", Weekday.MON, "10:00:00", journey, store)
    buy = next(event for event in result.timeline if event.action == Action.BUY)
    pay = next(event for event in result.timeline if event.action == Action.PAY)
    served = next(shelf for shelf in store.racks if shelf.id == buy.target_rack)
    assert served.accepts_face_at((buy.x, buy.y), buy.face, store.grid_size)
    assert any(product.sku == item.sku for shelf_slot in served.slots if shelf_slot.face == buy.face
               for product in shelf_slot.items)
    if not missing_buy:
        assert buy.target_rack == rack.id
    assert buy.product_sku == item.sku
    assert (pay.x, pay.y) in counter.service_access_tiles(store.grid_size)
    assert pay.target_rack == counter.id
    assert result.total_spent == 2 * item.price
    assert buy.elapsed_sec > 0 and pay.elapsed_sec > buy.elapsed_sec
    for first, second in zip(result.timeline, result.timeline[1:]):
        assert max(abs(first.x - second.x), abs(first.y - second.y)) <= 1
    assert [action.model_dump() for action in actions] == before


def test_unknown_sku_with_missing_coordinates_is_still_rejected():
    store = generate_store("compact_cvs", seed=0)
    actions = [CustomerAction(nav="path", action=Action.BUY, product_sku="missing"),
               CustomerAction(nav="path", action=Action.PAY), CustomerAction(nav="leave")]
    kept, dropped = drop_invalid_buys(actions, store)
    assert dropped == 1
    assert [action.nav for action in kept] == ["leave"]
