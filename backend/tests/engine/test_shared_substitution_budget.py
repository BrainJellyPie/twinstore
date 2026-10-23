"""Sold-out replacements retain the VLM planner's hard budget, including saved replays."""

import asyncio

import pytest

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.test_vlm_fill_budget import fill_store
from tests.engine.test_vlm_plan import _FakeVLM, _config, _context, _personas


def planned_visit(prices, items, budget, tolerance, seed):
    store = fill_store(prices)
    config = _config(entrance_image=False, max_glances=0, max_plan_items=len(items))
    config.budget_tolerance = tolerance
    config.engines.rule_based.multi_unit_prob = 0
    context = _context(store, _personas(1)[0], seed)
    context.persona = context.persona.model_copy(update={
        "budget_max": budget, "basket_size": len(items), "basket_kinds": 1,
    })
    engine = VLMGlanceEngine(_FakeVLM({"enter": True, "items": [
        {"category": "Drinks", "product": f"Product {sku}", "qty": quantity} for sku, quantity in items
    ]}), AStarPathFinder(), config)
    decision = asyncio.run(engine.decide_actions(context))
    planned = execute_decision(store, context.persona.id, Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    return store, planned


@pytest.mark.parametrize("seed", [0, 3])
@pytest.mark.parametrize("saved", [False, True])
@pytest.mark.parametrize("budget,tolerance,prices,items,spent,substituted", [
    (100, 1, [100, 175], [(0, 1)], 0, 0),
    (100, 1, [100, 75], [(0, 1)], 75, 1),
    (100, 1, [100, 0], [(0, 1)], 0, 1),
    (100, 1, [50, 75], [(0, 2)], 75, 1),
    (160, 1, [50, 75, 60], [(0, 2), (2, 1)], 120, 1),
    (100, 1, [0, 60], [(0, 2)], 60, 1),
    (100, 0, [0, 60], [(0, 1)], 0, 0),
    (100, 1.5, [100, 175], [(0, 1)], 0, 0),
    (200, 0.5, [100, 175], [(0, 1)], 0, 0),
    (0, 1, [100, 175], [(0, 1)], 175, 1),
    (100, None, [100, 175], [(0, 1)], 175, 1),
])
def test_substitutions_use_only_money_left_after_the_other_planned_lines(
    seed, saved, budget, tolerance, prices, items, spent, substituted,
):
    store, planned = planned_visit(prices, items, budget, tolerance, seed)
    before = planned.model_dump_json()
    source = CustomerResult.model_validate_json(before) if saved else planned
    results, report = resolve_shared_store(store, [source], OperationsConfig(
        stock_overrides={"0": 0}, restock_every_min=None, substitute_share=1,
        checkout_base_sec=0, checkout_item_sec=0,
    ), seed=seed)
    result = results[0]
    assert result.total_spent == spent
    assert result.substituted_units == report.substituted_units == substituted
    assert result.total_spent == sum(e.price * e.quantity for e in result.purchases)
    if budget > 0 and tolerance is not None:
        assert result.total_spent <= int(budget * tolerance)
    assert planned.model_dump_json() == before
    assert source.model_dump_json() == before


def test_legacy_results_without_a_recorded_limit_keep_their_previous_substitution_policy():
    store, planned = planned_visit([100, 175], [(0, 1)], 100, 1, 3)
    data = planned.model_dump()
    data.pop("spend_limit", None)
    legacy = CustomerResult.model_validate(data)
    results, report = resolve_shared_store(store, [legacy], OperationsConfig(
        stock_overrides={"0": 0}, restock_every_min=None, substitute_share=1,
        checkout_base_sec=0, checkout_item_sec=0,
    ), seed=3)
    assert results[0].total_spent == 175 and report.substituted_units == 1
