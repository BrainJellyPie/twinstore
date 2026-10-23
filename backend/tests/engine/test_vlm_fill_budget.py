"""Automatic trip-size filling must retain the VLM plan's hard spend limit."""

import asyncio

import pytest

from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from tests.engine.test_vlm_plan import _FakeVLM, _config, _context, _personas


def fill_store(prices):
    return Store(id="s", name="Trip fill", type="shop", grid_size=(8, 8), racks=[
        Rack(id="shelf", type="shelf", rack_name="Drinks", shape=[[1]], position=(2, 2), slots=[
            Slot(block=0, face=Face.N, level=3, items=[SlotItem(sku=str(i), name=f"Product {i}", price=price)
                 for i, price in enumerate(prices)])]),
        Rack(id="in", type="entrance", shape=[[1]], position=(0, 0)),
        Rack(id="out", type="exit", shape=[[1]], position=(7, 0)),
        Rack(id="till", type="counter", shape=[[1]], position=(6, 2)),
    ])


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("budget,tolerance,prices,multi,expected_skus", [
    (100, 1, [0, 101, 200, 300], 0, {"0"}),
    (100, 1, [0, 50, 101, 200], 0, {"0", "1"}),
    (100, 0, [0, 0, 500, 900], 0, {"0", "1"}),
    (100, 1.5, [100, 50, 51, 999], 0, {"0", "1"}),
    (100, 1, [0, 50, 50, 60000], 0.9, None),
    (100, None, [0, 60000, 70000, 80000], 0, None),
    (0, 0, [0, 60000, 70000, 80000], 0, None),
])
def test_breadth_fill_keeps_affordable_alternatives_and_caps_final_units(
    seed, budget, tolerance, prices, multi, expected_skus,
):
    store = fill_store(prices)
    config = _config(entrance_image=False, max_glances=0)
    config.budget_tolerance = tolerance
    config.engines.rule_based.multi_unit_prob = multi
    context = _context(store, _personas(1)[0], seed)
    context.persona = context.persona.model_copy(update={
        "budget_max": budget, "basket_size": 3, "basket_kinds": 1, "usual_products": ["Product 3"],
    })
    fake = _FakeVLM({"enter": True, "items": [{"category": "Drinks", "product": "Product 0", "qty": 1}]})
    engine = VLMGlanceEngine(fake, AStarPathFinder(), config)
    decision = asyncio.run(engine.decide_actions(context))
    result = execute_decision(store, context.persona.id, Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    bought = {buy.product_sku for buy in result.purchases}
    if expected_skus is not None:
        assert bought == expected_skus
    if tolerance is not None and budget > 0:
        assert result.total_spent <= int(budget * tolerance)
    else:
        assert len(bought) == 3 and result.total_spent > 100000
    if multi:
        assert result.total_spent == 100
    assert len(bought) == len(result.purchases)
    assert result.total_spent == sum(buy.price * buy.quantity for buy in result.purchases)


def test_rule_planned_purchases_keep_their_existing_soft_budget():
    store = fill_store([300, 300, 300, 300])
    config = _config(entrance_image=False, max_glances=0)
    config.budget_tolerance = 1
    context = _context(store, _personas(1)[0], 3)
    context.persona = context.persona.model_copy(update={
        "budget_max": 100, "basket_size": 3, "basket_kinds": 1, "preferred_categories": ["Drinks"],
    })
    plan = RuleBasedEngine(AStarPathFinder(), config)._plan(context)
    assert len(plan.buys) == 3 and plan.spend == 900
