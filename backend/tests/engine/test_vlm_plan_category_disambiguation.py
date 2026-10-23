"""Identical product names in different categories retain the model's named category."""

import asyncio

import pytest

from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.planning import match_plan_item
from store_emulator.engine.simulation.engines.vlm_glance.prompt import PlannedItem
from tests.engine.test_purchase_quantity_limits import context_for
from tests.engine.test_vlm_plan import _config, _FakeVLM


def fixture(same_sku, reverse, name="Original"):
    racks = [Rack(id=category, rack_name=category.title(), rack_desc=category, type="shelf",
                  position=(3 + index * 3, 3), shape=[[1]], slots=[
        Slot(block=0, face=Face.N, level=1 + index * 2, items=[
            SlotItem(sku="shared" if same_sku else category, name=name, price=100 + index * 600)])])
        for index, category in enumerate(["snacks", "milk"])]
    store = Store(id="s", name="Repeated names", type="shop", grid_size=(10, 10), racks=[
        *(racks[::-1] if reverse else racks),
        Rack(id="in", type="entrance", position=(0, 0), shape=[[1]]),
        Rack(id="out", type="exit", position=(9, 0), shape=[[1]]),
        Rack(id="till", type="counter", position=(8, 2), shape=[[1]])])
    fake = _FakeVLM({"enter": True, "items": [{"category": "Milk", "product": name, "qty": 1}]})
    engine = VLMGlanceEngine(fake, AStarPathFinder(), _config(entrance_image=False, max_glances=0).model_copy(
        update={"budget_tolerance": None}))
    return store, engine


@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("name", ["Original", "X", "茶", "Straße"])
def test_named_category_disambiguates_exact_names(same_sku, reverse, name):
    store, engine = fixture(same_sku, reverse, name)
    matched = match_plan_item(PlannedItem(category=" MILK ", product=name.upper()), engine._catalog_for(store))
    assert matched.how == "exact" and {entry[0].id for entry in matched.candidates} == {"milk"}


@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("seed", [0, 1, 3, 7, 13, 21])
def test_fake_model_plan_buys_from_its_named_category(same_sku, reverse, seed):
    store, engine = fixture(same_sku, reverse)
    decision = asyncio.run(engine.decide_actions(context_for(store, seed)))
    result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert len(result.purchases) == 1
    buy = result.purchases[0]
    assert (buy.target_rack, buy.price, buy.product_level) == ("milk", 700, 3)
    assert engine.plan_log[0].resolved[0][3] == "Milk"


@pytest.mark.parametrize("category", ["", "Unknown", "Snacks"])
def test_exact_name_still_resolves_when_named_category_does_not_stock_it(category):
    store, engine = fixture(False, False)
    store.racks[0].slots[0].items[0].name = "Different product"
    match = match_plan_item(PlannedItem(category=category, product="Original"), engine._catalog_for(store))
    assert match.how == "exact" and {entry[0].id for entry in match.candidates} == {"milk"}
