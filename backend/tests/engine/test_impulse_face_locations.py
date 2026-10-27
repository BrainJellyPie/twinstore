"""The model must see the exact exposed face, not a few arbitrary rack sides."""
import json
import re

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.routing.route_builder import integrate_actions
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent, stage3_impulse
from tests.engine.routing.test_purchase_block_geometry import shelf_store, stance
from tests.engine.test_llm_engine_offline import _persona


def prompt_for(store, rack, *, selection=False):
    exposed = [(rack, slot, item.sku) for slot in rack.slots for item in slot.items]
    records = stage2_intent.catalog_records(store)
    return stage3_impulse.build_user_prompt(_persona(), stage2_intent.IntentResponse(), exposed,
        store=store, grid_size=store.grid_size, records=records, selection=selection), records


@pytest.mark.parametrize("face", list(Face))
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("reverse", [False, True])
def test_copying_exposed_location_reaches_the_correct_offer_without_guessing(face, rotation, reverse):
    store, rack = shelf_store(face, rotation, reverse)
    before = store.model_dump()
    prompt, records = prompt_for(store, rack)
    locations = {code: json.loads(value) for code, value in re.findall(r"^  (R\d+):.* @ (\{.*\})$", prompt, re.M)}
    assert len(locations) == 2
    for slot in rack.slots:
        offer = slot.items[0]
        code = next(code for code, item in records.items() if item is offer)
        line = next(line for line in prompt.splitlines() if line.startswith(f"  - {code}:"))
        anchor = re.search(r"\| (R\d+) level=", line).group(1)
        coordinates = locations[anchor]
        assert coordinates == {"target": list(stance(rack, slot)), "face": face.value}
        action = CustomerAction.model_validate({"nav": "path", "action": "buy", "product_sku": offer.sku, **coordinates})
        actions = integrate_actions(store, [action], [], ordering="planned")
        result = execute_decision(store, "p", Weekday.MON, "09:00:00",
            EngineDecision(engine_type="offline", actions=actions), AStarPathFinder(), 1)
        assert len(result.purchases) == 1
        purchase = result.purchases[0]
        assert (purchase.x, purchase.y, purchase.price) == (*stance(rack, slot), offer.price)
    assert store.model_dump() == before


def test_opposite_faces_are_separate_but_repeated_levels_share_a_location():
    store, rack = shelf_store(Face.N)
    rack.slots = [Slot(block=0, face=face, level=level, items=[SlotItem(sku=f"{face}-{level}", name="Tea", price=100)])
                  for face in (Face.N, Face.S) for level in (1, 4)]
    prompt, _ = prompt_for(store, rack)
    assert len(re.findall(r"^  R\d+:", prompt, re.M)) == 2
    assert len(re.findall(r"\| R1 level=", prompt)) == len(re.findall(r"\| R2 level=", prompt)) == 2


@pytest.mark.parametrize("blocked", ["outside", "fixture", "internal"])
def test_unavailable_face_does_not_advertise_another_sides_tile(blocked):
    store, rack = shelf_store(Face.N)
    rack.slots = [rack.slots[0]]
    target = stance(rack, rack.slots[0])
    if blocked == "outside":
        rack.position = (3, 0)
    elif blocked == "fixture":
        store.racks.append(Rack(id="obstacle", type="shelf", position=target, shape=[[1]]))
    else:
        rack.rotation = 90
        rack.slots[0].block = 1
    prompt, _ = prompt_for(store, rack)
    location = next(line for line in prompt.splitlines() if line.startswith("  R1:"))
    assert "unavailable" in location and '"target"' not in location


def test_selection_remains_coordinate_free():
    store, rack = shelf_store(Face.N)
    prompt, _ = prompt_for(store, rack, selection=True)
    assert '"target"' not in prompt and not re.search(r"^  R\d+:", prompt, re.M)
