"""The LLM cannot turn a zero-purchase pattern into revenue or exceed its basket cap."""

import asyncio

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _intent, _persona


def context(store, cap, budget=1000):
    out = _context(store, _persona(budget))
    pattern = next(p for p in out.behavior_patterns if p.id == "exploratory")
    return out.model_copy(update={"behavior_patterns": [pattern.model_copy(update={"max_products": cap})]})


def buy(sku, face, quantity=1):
    return CustomerAction(nav="path", target=(1, 0), face=face, action=Action.BUY, product_sku=sku, quantity=quantity)


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
@pytest.mark.parametrize("planned,impulse", [(0, 2), (1, 1), (2, 0), (2, 2)])
@pytest.mark.parametrize("cap", [0, 1, 2, 4])
@pytest.mark.parametrize("quantity", [1, 3])
def test_pattern_cap_applies_to_executed_buys_prioritizing_planned_products(collision_store, ordering, planned, impulse, cap, quantity):
    collision_store.racks[0].slots[0].items.append(SlotItem(sku="sku-c", name="C item", price=300))
    collision_store.racks[1].slots[0].items.append(SlotItem(sku="sku-d", name="D item", price=400))
    before = collision_store.model_dump_json()
    intent = _intent()
    intent.actions = [a for a in intent.actions if a.action != Action.BUY]
    pay = next(i for i, a in enumerate(intent.actions) if a.action == Action.PAY)
    planned_skus, impulse_skus = ["sku-a", "sku-c"][:planned], ["sku-b", "sku-d"][:impulse]
    intent.actions[pay:pay] = [buy(sku, Face.E, quantity) for sku in planned_skus]
    llm = _ScriptedLLM(intent, ImpulseResponse(actions=[buy(sku, Face.W, quantity) for sku in impulse_skus]))
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(route_ordering=ordering, budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(context(collision_store, cap)))
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    expected = (planned_skus + impulse_skus)[:cap]
    assert {event.product_sku for event in result.purchases} == set(expected)
    assert len(result.purchases) == len(expected)
    prices = {"sku-a": 100, "sku-b": 200, "sku-c": 300, "sku-d": 400}
    assert result.total_spent == sum(prices[sku] * quantity for sku in expected)
    assert all(event.quantity == quantity for event in result.purchases)
    assert sum(event.action == Action.PAY for event in result.timeline) == bool(expected)
    assert result.timeline[-1].action == Action.EXIT
    assert decision.trace.get("dropped_product_limit", 0) == planned + impulse - len(expected)
    assert decision.dropped_invalid_buys == decision.dropped_over_budget == 0
    assert collision_store.model_dump_json() == before


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
def test_invented_products_do_not_consume_the_real_product_allowance(collision_store, ordering):
    intent = _intent()
    intent.actions.insert(1, buy("invented", Face.E))
    llm = _ScriptedLLM(intent, ImpulseResponse(actions=[buy("another-invented", Face.W), buy("sku-b", Face.W)]))
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(route_ordering=ordering, budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(context(collision_store, 1)))
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert [e.product_sku for e in result.purchases] == ["sku-a"]
    assert result.total_spent == 300
    assert decision.dropped_invalid_buys == 2
    assert decision.trace["dropped_product_limit"] == 1


@pytest.mark.parametrize("ordering", ["nearest", "planned"])
def test_over_limit_planned_buys_are_removed_before_exposure_and_impulse_prompt(collision_store, monkeypatch, ordering):
    from store_emulator.engine.simulation.engines.pattern_intent_impulse import engine as module

    original = module.build_journey
    observed = []
    def journey(store, actions, *args, **kwargs):
        observed.append([a.product_sku for a in actions if a.action == Action.BUY])
        return original(store, actions, *args, **kwargs)

    monkeypatch.setattr(module, "build_journey", journey)
    intent = _intent()
    intent.actions.insert(2, buy("sku-b", Face.W))
    llm = _ScriptedLLM(intent, ImpulseResponse())
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(route_ordering=ordering, budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(context(collision_store, 1)))
    assert observed == [["sku-b"]]
    impulse_call = next(call for call in llm.calls if call[0] == "ImpulseResponse")
    assert "기존 구매 1개" in impulse_call[1]
    assert sum(a.action == Action.BUY for a in decision.actions) == 1
    # Keep the original model answer available to explain what was pruned.
    assert sum(a["action"] == Action.BUY for a in decision.trace["stage2"]["actions"]) == 2


@pytest.mark.parametrize("cap", [0, 1])
def test_bounded_basket_reaches_shared_store_revenue_and_checkout_metrics(collision_store, cap):
    from store_emulator.domain.operations import OperationsConfig
    from store_emulator.engine.simulation.shared_store import resolve_shared_store

    llm = _ScriptedLLM(_intent(), ImpulseResponse(actions=[buy("sku-b", Face.W)]))
    engine = PatternIntentImpulseEngine(llm, AStarPathFinder(), SimulationConfig(budget_tolerance=None))
    decision = asyncio.run(engine.decide_actions(context(collision_store, cap)))
    result = execute_decision(collision_store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    resolved, report = resolve_shared_store(collision_store, [result], OperationsConfig(
        restock_every_min=None, checkout_base_sec=60, checkout_item_sec=0, patience_sec=10, patience_sd=0), seed=1)
    assert report.queued == cap and report.abandoned == 0
    assert resolved[0].total_spent == 300 * cap
    assert len(resolved[0].purchases) == cap
