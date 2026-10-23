"""A blocked copy in the baseline is not permission to hide every offer of its SKU."""

import pytest

from store_emulator.domain.optimize import OptimizeConstraints, OptimizeScope
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.optimize.moves import MoveRules, SlotRef, SwapSlots, apply_move, is_feasible


def store():
    shelf = Rack(id="shelf", type="shelf", rack_name="Snacks", position=(2, 0), shape=[[1]], slots=[
        Slot(block=0, face=face, level=level, items=[SlotItem(sku=sku, name=sku, price=100)])
        for face, level, sku in [(Face.N, 1, "A"), (Face.N, 2, "B"), (Face.S, 1, "A"), (Face.S, 2, "C")]
    ])
    fixtures = [
        Rack(id=kind, type=kind, position=position, shape=[[1]])
        for kind, position in [("entrance", (0, 3)), ("exit", (5, 3)), ("counter", (4, 3))]
    ]
    return Store(id="test", name="Test", type="convenience", grid_size=(6, 5), racks=[shelf, *fixtures])


def rules(baseline):
    return MoveRules.for_baseline(baseline, OptimizeScope.PLANOGRAM, OptimizeConstraints())


def test_optimizer_cannot_delist_last_reachable_copy_of_an_already_blocked_sku():
    baseline = store()
    before = baseline.model_dump_json()
    move = SwapSlots(SlotRef("shelf", 0, Face.S, 1), SlotRef("shelf", 0, Face.N, 2))
    assert apply_move(baseline, move, rules(baseline)) is None
    assert baseline.model_dump_json() == before


@pytest.mark.parametrize("count", [1, 2, 3])
@pytest.mark.parametrize("newly_blocked", [1, 2, 3])
def test_blocked_facing_allowance_counts_copies_not_just_sku_presence(count, newly_blocked):
    baseline = store()
    baseline.racks[0].slots[0].items *= count
    candidate = baseline.model_copy(deep=True)
    candidate.racks[0].slots.append(Slot(block=0, face=Face.N, level=3,
                                       items=[baseline.racks[0].slots[2].items[0]] * newly_blocked))
    assert not is_feasible(candidate, rules(baseline))


@pytest.mark.parametrize("field,value", [("price", 50), ("name", "New A"), ("regular_price", 200),
    ("promo", "Special"), ("image_url", "/api/projects/test/images?sku=A&v=new")])
def test_different_offers_of_one_sku_do_not_share_a_blocked_allowance(field, value):
    baseline = store()
    old = baseline.racks[0].slots[2].items[0]
    baseline.racks[0].slots[2].items = [old.model_copy(update={field: value})]
    candidate = baseline.model_copy(deep=True)
    north, south = candidate.racks[0].slots[0], candidate.racks[0].slots[2]
    north.items, south.items = south.items, north.items
    assert not is_feasible(candidate, rules(baseline))


def test_unchanged_or_improved_accessibility_and_rearranging_existing_blocked_stock_remain_allowed():
    baseline = store()
    allowed = rules(baseline)
    assert is_feasible(baseline, allowed)
    improved = baseline.model_copy(deep=True)
    improved.racks[0].slots[3].items.extend(improved.racks[0].slots[1].items)
    improved.racks[0].slots[1].items = []
    assert is_feasible(improved, allowed)
    move = SwapSlots(SlotRef("shelf", 0, Face.N, 1), SlotRef("shelf", 0, Face.N, 2))
    assert apply_move(baseline, move, allowed) is not None


def test_reachable_stock_can_still_be_rearranged():
    baseline = store()
    move = SwapSlots(SlotRef("shelf", 0, Face.S, 1), SlotRef("shelf", 0, Face.S, 2))
    assert apply_move(baseline, move, rules(baseline)) is not None
