"""Buying from one face must keep that face's price and independent stock."""
import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.route_builder import JourneyStep
from store_emulator.engine.routing.timeline_builder import build_timeline
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.routing.test_route_builder import _sanitize


STANCES = {Face.N: (2, 1), Face.E: (3, 2), Face.S: (2, 3), Face.W: (1, 2)}
PRICES = {Face.N: 100, Face.E: 200, Face.S: 300, Face.W: 400}


def store_with_faces(reverse=False):
    slots = [Slot(block=0, face=face, level=1,
                  items=[SlotItem(sku="tea", name=f"Tea {face}", price=PRICES[face])]) for face in STANCES]
    return Store(id="store", name="Four offers", type="convenience", grid_size=(5, 5), racks=[
        Rack(id="shelf", type="shelf", position=(2, 2), shape=[[1]], slots=slots[::-1] if reverse else slots),
    ])


def visit(store, face, hint):
    stance = STANCES[face]
    action = CustomerAction(nav="path", action=Action.BUY, target=stance, face=hint, product_sku="tea", dwell=2)
    return build_timeline(persona_id=f"p_{face}", day=Weekday.MON, arrival_time="10:00:00", store=store,
                          journey=[JourneyStep(path=[stance], action=action)])


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("face", list(STANCES))
@pytest.mark.parametrize("hint", ["correct", "missing", "wrong"])
def test_buy_uses_the_reached_face_even_when_other_faces_carry_the_sku(reverse, face, hint):
    supplied = face if hint == "correct" else None if hint == "missing" else Face.N if face != Face.N else Face.S
    store = store_with_faces(reverse)
    action = CustomerAction(nav="path", action=Action.BUY, target=STANCES[face], face=supplied, product_sku="tea")
    routed = _sanitize(store, action)
    assert (routed.target, routed.face) == (STANCES[face], face)
    result = visit(store, face, supplied)
    buy = result.purchases[0]
    assert (buy.target_rack, buy.face, buy.price, buy.product_name) == (
        "shelf", face, PRICES[face], f"Tea {face}",
    )
    assert result.total_spent == PRICES[face]


@pytest.mark.parametrize("reverse", [False, True])
def test_opposite_faces_sell_their_own_stock_in_the_shared_store(reverse):
    store = store_with_faces(reverse)
    planned = [visit(store, face, face) for face in STANCES]
    actual, report = resolve_shared_store(store, planned,
        OperationsConfig(stock_per_facing=1, restock_every_min=None, substitute_share=0), seed=1)
    assert [shopper.units_bought for shopper in actual] == [1, 1, 1, 1]
    assert [shopper.total_spent for shopper in actual] == list(PRICES.values())
    assert report.lost_units == report.lost_revenue == 0
    assert sum(shopper.total_spent for shopper in actual) == 1000
