"""Moving a product must not send the displaced product into an inaccessible face."""

from collections import Counter

import pytest

from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.rack import Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.engine.marketing.variants import apply_changes
from store_emulator.engine.validation import list_blocked_faces
from tests.engine.test_optimizer_blocked_offers import store


def full_slot():
    return [SlotItem(sku=sku, name=sku, price=100) for sku in ["C", "D", "E", "F"]]


def visible(layout):
    blocked = {(row.rack_id, row.block, row.face) for row in list_blocked_faces(layout)}
    return Counter(item.sku for rack in layout.racks for slot in rack.slots
                   if (rack.id, slot.block, slot.face) not in blocked for item in slot.items)


def move(level=2):
    return VariantChange(kind="move", sku="A", rack_id="shelf", face="S", level=level)


@pytest.mark.parametrize("blocked_first", [False, True])
def test_full_target_uses_an_accessible_source_for_the_displaced_product(blocked_first):
    source = store()
    source.racks[0].slots[3].items = full_slot()
    if not blocked_first:
        source.racks[0].slots.reverse()
    before = source.model_dump_json()
    updated, applied, warnings = apply_changes(source, [move()])
    assert applied and not warnings
    assert visible(updated) == visible(source)
    assert source.model_dump_json() == before
    assert next(s for s in updated.racks[0].slots if s.face == Face.S and s.level == 2).items[-1].sku == "A"


def test_full_target_is_left_unchanged_when_only_blocked_sources_exist():
    source = store()
    source.racks[0].slots[2].items = []
    source.racks[0].slots[3].items = full_slot()
    updated, applied, warnings = apply_changes(source, [move()])
    assert not applied and warnings
    assert updated.model_dump() == source.model_dump()


@pytest.mark.parametrize("existing_target", [False, True])
def test_blocked_source_can_move_into_available_space(existing_target):
    source = store()
    source.racks[0].slots[2].items = []
    updated, applied, warnings = apply_changes(source, [move(2 if existing_target else 3)])
    assert applied and not warnings
    assert visible(updated) == visible(source) + Counter(A=1)


def test_blocked_full_target_does_not_prevent_moving_to_a_later_empty_block():
    source = store()
    shelf = source.racks[0]
    shelf.shape = [[1, 1]]
    shelf.slots[2].items = []
    shelf.slots[3].items = full_slot()
    updated, applied, warnings = apply_changes(source, [move()])
    assert applied and warnings
    assert visible(updated) == visible(source) + Counter(A=1)
    target = next(s for s in updated.racks[0].slots if s.block == 1 and s.face == Face.S and s.level == 2)
    assert [item.sku for item in target.items] == ["A"]
    original = next(s for s in updated.racks[0].slots if s.block == 0 and s.face == Face.S and s.level == 2)
    assert [item.sku for item in original.items] == ["C", "D", "E", "F"]


@pytest.mark.parametrize("sku", ["missing", "A"])
def test_unapplied_moves_do_not_create_empty_slots(sku):
    source = store()
    if sku == "A":
        for slot in source.racks[0].slots:
            slot.items = [item for item in slot.items if item.sku != "A"]
        source.racks[0].slots.append(Slot(block=0, face=Face.S, level=3, items=[SlotItem(sku="A", name="A", price=100)]))
        source.racks[0].shape = [[1, 1]]
    updated, applied, warnings = apply_changes(source, [move(3).model_copy(update={"sku": sku})])
    assert not applied and warnings
    assert updated.model_dump() == source.model_dump()
