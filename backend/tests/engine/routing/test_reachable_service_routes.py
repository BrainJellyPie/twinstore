"""A valid multi-entrance layout may have separately connected customer areas."""

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.validation import validate


def divided_visit(topology, transpose, side, hint):
    def point(x, y):
        return (y, x) if transpose else (x, y)

    def rack(id, kind, x, y, **kwargs):
        return Rack(id=id, type=kind, position=point(x, y), shape=[[1]], **kwargs)

    racks = [rack("entry", "entrance", 9 if side else 0, 0),
             rack("other-entry", "entrance", 0 if side else 9, 0),
             rack("other-exit", "exit", 0 if side else 9, 9),
             rack("exit", "exit", 9 if side else 0, 9)]
    racks += [rack(f"wall-{y}", "shelf", 4, y) for y in range(10)
              if topology != "split" or y != 5]
    if topology == "split":
        racks.append(rack("counter", "counter", 4, 5))
        local, remote, body = point(5 if side else 3, 5), point(3 if side else 5, 5), point(4, 5)
    else:
        if topology != "remote-only":
            racks.append(rack("local-counter", "counter", 7 if side else 2, 7))
        racks.append(rack("remote-counter", "counter", 2 if side else 7, 7))
        local = point(7 if side else 2, 6)
        remote, body = point(2 if side else 7, 6), point(2 if side else 7, 7)
    face = Face.W if transpose else Face.N
    racks.append(rack("product", "shelf", 7 if side else 2, 3, slots=[
        Slot(block=0, face=face, level=1, items=[SlotItem(sku="tea", name="Tea", price=100)])]))
    store = Store(id="s", name="Two customer areas", type="shop", grid_size=(10, 10), racks=racks)
    target = {"remote": remote, "body": body, "missing": None, "local": local}[hint]
    decision = EngineDecision(engine_type="offline", actions=[
        CustomerAction(nav="path", action=Action.BUY, target=point(7 if side else 2, 2),
                       face=face, product_sku="tea"),
        CustomerAction(nav="path", action=Action.PAY, target=target, dwell=10),
        CustomerAction(nav="leave"),
    ])
    return store, decision, local


@pytest.mark.parametrize("topology", ["split", "two"])
@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("hint", ["remote", "body", "missing", "local"])
@pytest.mark.parametrize("diagonal", [False, True])
def test_checkout_and_exit_are_reached_from_the_customers_own_area(topology, transpose, side, hint, diagonal):
    store, decision, local = divided_visit(topology, transpose, side, hint)
    assert [issue for issue in validate(store) if issue.severity == "error"] == []
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", decision,
                              AStarPathFinder(diagonal=diagonal), 1)
    pay = next(event for event in result.timeline if event.action == Action.PAY)
    counter = next(rack for rack in store.counters if rack.id == pay.target_rack)
    assert (pay.x, pay.y) in counter.service_access_tiles(store.grid_size)
    assert (pay.y if transpose else pay.x) > 4 if side else (pay.y if transpose else pay.x) < 4
    if hint == "local":
        assert (pay.x, pay.y) == local
    assert (result.timeline[-1].x, result.timeline[-1].y) == store.exits[1].position
    assert result.total_spent == 100
    positions = [(event.x, event.y) for event in result.timeline]
    assert all(max(abs(a[0]-b[0]), abs(a[1]-b[1])) <= 1 for a, b in zip(positions, positions[1:]))


@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("side", [0, 1])
def test_unreachable_checkout_fails_the_visit_instead_of_recording_remote_payment(transpose, side):
    store, decision, _ = divided_visit("remote-only", transpose, side, "remote")
    assert [issue for issue in validate(store) if issue.severity == "error"] == []
    with pytest.raises(ValueError, match="reachable checkout"):
        execute_decision(store, "p", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)


@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("side", [0, 1])
def test_unreachable_exit_does_not_finish_the_visit_at_the_counter(transpose, side):
    store, decision, _ = divided_visit("two", transpose, side, "local")
    store.racks = [rack for rack in store.racks if rack.id != "exit"]
    assert [issue for issue in validate(store) if issue.severity == "error"] == []
    with pytest.raises(ValueError, match="reachable exit"):
        execute_decision(store, "p", Weekday.MON, "10:00:00", decision, AStarPathFinder(), 1)
