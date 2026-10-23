"""Purchases require reaching the selected offer, including after failed visits."""

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.rack import BlockFace, Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, FACE_OFFSETS, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.shared_store import resolve_shared_store


def separated_store(face, obstacle):
    dx, dy = FACE_OFFSETS[face]
    target = (7 + dx, 4 + dy)
    shelf = Rack(id="far", type="shelf", position=(7, 4), shape=[[1]], slots=[
        Slot(block=0, face=face, level=1, items=[SlotItem(sku="far", name="Far item", price=500)])])
    near = Rack(id="near", type="shelf", position=(2, 3), shape=[[1]], slots=[
        Slot(block=0, face=Face.N, level=1, items=[SlotItem(sku="near", name="Near item", price=100)])])
    racks = [shelf, near, Rack(id="in", type="entrance", position=(0, 0), shape=[[1]]),
             Rack(id="out", type="exit", position=(0, 9), shape=[[1]]),
             Rack(id="till", type="counter", position=(2, 8), shape=[[1]])]
    if obstacle in ("wall", "door"):
        racks += [Rack(id=f"wall-{y}", type="shelf", position=(4, y), shape=[[1]])
                  for y in range(10) if obstacle == "wall" or y != 5]
    elif obstacle == "stance":
        racks.append(Rack(id="obstruction", type="shelf", position=target, shape=[[1]]))
    elif obstacle == "locked":
        shelf.locked_faces = [BlockFace(block=0, face=face)]
    return Store(id="s", name="Separated aisles", type="shop", grid_size=(10, 10), racks=racks), target


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("obstacle", ["wall", "door", "stance", "locked", "none"])
@pytest.mark.parametrize("diagonal", [False, True])
@pytest.mark.parametrize("target_hint", [True, False])
def test_inaccessible_buy_does_not_create_sales_or_interrupt_next_reachable_buy(
    face, obstacle, diagonal, target_hint, caplog,
):
    store, target = separated_store(face, obstacle)
    decision = EngineDecision(engine_type="offline", dropped_invalid_buys=2, actions=[
        CustomerAction(nav="path", action=Action.ENTER, target=(0, 0)),
        CustomerAction(nav="path", action=Action.BUY, target=target if target_hint else None,
                       face=face, product_sku="far", quantity=3),
        CustomerAction(nav="path", action=Action.BUY, target=(2, 2), face=Face.N,
                       product_sku="near", quantity=2),
        CustomerAction(nav="path", action=Action.PAY, target=(2, 7)),
        CustomerAction(nav="leave"),
    ])
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", decision,
                              AStarPathFinder(diagonal=diagonal), 1)
    reachable = obstacle in ("door", "none")
    assert [buy.product_sku for buy in result.purchases] == (["far", "near"] if reachable else ["near"])
    assert result.total_spent == (1700 if reachable else 200)
    assert result.dropped_invalid_buys == 2
    assert ("Skipped 1 unreachable purchases" in caplog.text) is not reachable
    assert result.timeline[-1].action == Action.EXIT
    if not reachable and obstacle == "wall":
        assert all(event.x < 4 for event in result.timeline)
    for buy in result.purchases:
        assert (buy.x, buy.y) == (target if buy.product_sku == "far" else (2, 2))
    actual, report = resolve_shared_store(store, [result], OperationsConfig(
        stock_overrides={"far": 0, "near": 5}, restock_every_min=None, substitute_share=0), seed=1)
    assert actual[0].total_spent == 200
    assert report.lost_units == (3 if reachable else 0)
    assert report.lost_revenue == (1500 if reachable else 0)


@pytest.mark.parametrize("unknown", ["", "missing"])
def test_unknown_product_cannot_become_a_zero_price_purchase(unknown):
    store, target = separated_store(Face.N, "none")
    result = execute_decision(store, "p", Weekday.MON, "10:00:00", EngineDecision(
        engine_type="offline", actions=[CustomerAction(nav="path", action=Action.BUY,
            target=target, face=Face.N, product_sku=unknown)]), AStarPathFinder(), 1)
    assert result.purchases == []
    assert result.dropped_invalid_buys == 1
