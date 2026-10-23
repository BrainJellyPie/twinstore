"""A chosen checkout survives routing and is attributed to its service counter."""

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import build_journey
from store_emulator.engine.routing.timeline_builder import build_timeline


@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("body", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_chosen_counter_survives_route_and_timeline(wall, index, body, reverse):
    store = generate_store("compact_cvs", seed=0, options=LayoutOptions(checkouts=3, checkout_wall=wall))
    counter = store.counters[index]
    grid = store.walkable_grid()
    service = [tile for tile in counter.service_access_tiles(store.grid_size) if grid[tile[1]][tile[0]]]
    assert service
    target = counter.occupied_positions[0] if body else service[0]
    action = CustomerAction(nav="path", action=Action.PAY, target=target, dwell=10)
    if reverse:
        store.racks.reverse()
    journey = build_journey(store, [action, CustomerAction(nav="leave")], AStarPathFinder())
    assert journey[0].action.target in service
    assert journey[0].path[-1] in service
    if not body:
        assert journey[0].action.target == target
    result = build_timeline("p", Weekday.MON, "10:00:00", journey, store)
    pay = next(event for event in result.timeline if event.action == Action.PAY)
    assert (pay.x, pay.y) in service
    assert pay.target_rack == counter.id
    assert action.target == target


def test_unknown_pay_target_still_falls_back_to_a_service_tile():
    store = generate_store("compact_cvs", seed=0, options=LayoutOptions(checkouts=3))
    action = CustomerAction(nav="path", action=Action.PAY, target=(-10, -10), dwell=10)
    journey = build_journey(store, [action], AStarPathFinder())
    assert journey[0].path[-1] in store.counters[0].service_access_tiles(store.grid_size)
