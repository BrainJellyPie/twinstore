"""Failed point routes cannot add remote browsing or delay later reachable stops."""

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.validation import validate
from tests.engine.routing.test_reachable_service_routes import divided_visit


@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("diagonal", [False, True])
@pytest.mark.parametrize("action_type", [Action.BROWSE, None, Action.MOVE])
@pytest.mark.parametrize("target_body", [False, True])
@pytest.mark.parametrize("doorway", [False, True])
def test_failed_point_stops_do_not_create_remote_dwell(
    transpose, side, diagonal, action_type, target_body, doorway,
):
    store, decision, _ = divided_visit("two", transpose, side, "local")
    remote = (2 if side else 7, 3)
    target = (remote[0], remote[1] if target_body else remote[1] - 1)
    if transpose:
        remote, target = remote[::-1], target[::-1]
    face = Face.W if transpose else Face.N
    store.racks.append(Rack(id="remote-shelf", type="shelf", position=remote, shape=[[1]], slots=[
        Slot(block=0, face=face, level=1, items=[SlotItem(sku="remote", name="Remote", price=100)])]))
    if doorway:
        store.racks = [rack for rack in store.racks if rack.id != "wall-5"]
    assert [issue for issue in validate(store) if issue.severity == "error"] == []

    finder = AStarPathFinder(diagonal=diagonal)
    control = execute_decision(store, "p", Weekday.MON, "10:00:00", decision, finder, 1)
    decision.actions.insert(0, CustomerAction(nav="path", target=target, face=face,
        action=action_type, dwell=50, description="remote stop"))
    original = decision.model_dump()
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", decision, finder, 1)
    remote_events = [event for event in result.timeline if event.description == "remote stop"]
    if doorway:
        assert len(remote_events) == 1
        event = remote_events[0]
        rack = next(rack for rack in store.racks if rack.id == "remote-shelf")
        assert (event.x, event.y) in rack.access_tiles(store.grid_size)
        assert result.duration_sec > control.duration_sec
    else:
        assert remote_events == []
        assert result == control  # Includes later paths, dwell, checkout, prices and departure.
    assert result.total_spent == 100
    assert result.timeline[-1].action == Action.EXIT
    assert decision.model_dump() == original


@pytest.mark.parametrize("action_type", [Action.BROWSE, None])
def test_browsing_without_a_destination_still_occurs_at_current_position(action_type):
    store, decision, _ = divided_visit("two", False, 0, "local")
    decision.actions.insert(0, CustomerAction(nav="path", action=action_type,
        dwell=7, description="look around"))
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)
    event = next(event for event in result.timeline if event.description == "look around")
    assert (event.x, event.y) == store.entrances[0].position
    assert event.action == Action.BROWSE and event.duration == 7 and event.target_rack == ""
