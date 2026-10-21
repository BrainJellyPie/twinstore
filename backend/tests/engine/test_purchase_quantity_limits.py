"""Purchase quantities and recorded spending respect the configured limits."""
import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.rule_based import ImpulseOutcome, RuleBasedEngine


def context_for(store, seed):
    return PerCustomerContext(
        store=store, persona=Persona(id="shopper", identity="Shopper", age_group="30s", gender="Female",
            description="", intent="", purpose="", budget_max=100), day=Weekday.MON, arrival_hour=12,
        concurrent_visitors_in_hour=1, cue=BehaviorCue(),
        behavior_patterns=[next(p for p in BEHAVIOR_PATTERNS if p.id == "purposeful")], seed=seed,
    )


def purchase_fixture(config, seed=0):
    store = generate_store("urban_cvs")
    rack = store.product_racks[0]
    slot = next(slot for slot in rack.slots if slot.items)
    item = slot.items[0]
    for shelf in store.product_racks:
        for facing in shelf.slots:
            for product in facing.items:
                if product.sku == item.sku:
                    product.price = 100
    context = context_for(store, seed)
    engine = RuleBasedEngine(AStarPathFinder(), config)
    plan, middle = engine._begin_plan(context)
    return store, rack, slot, item, context, engine, plan, middle


@pytest.mark.parametrize("tolerance,budget,spent,price,max_units", [
    (1.0, 100, 0, 100, 1), (1.5, 100, 50, 100, 1), (1.0, 500, 300, 100, 2),
    (None, 100, 500, 100, 3), (0.0, 100, 0, 0, 3),
])
def test_impulse_quantities_respect_remaining_budget(tolerance, budget, spent, price, max_units):
    observed = []
    for seed in range(12):
        config = SimulationConfig(budget_tolerance=tolerance, engines={"rule_based": {"multi_unit_prob": 0.9}})
        store, rack, slot, item, context, engine, plan, middle = purchase_fixture(config, seed)
        item.price = price
        plan.budget = budget
        plan.spend = spent
        engine.close_plan(store, plan, middle)
        out = ImpulseOutcome()
        assert engine.can_buy_more(plan, 0, item.price)
        assert engine.add_impulse_buy(store, plan, out, rack, slot, item, "takes an extra")
        decision = engine._finish(context, plan, out)
        result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1.0)
        assert 1 <= result.units_bought <= max_units
        assert result.total_spent == plan.spend - spent
        if tolerance is not None:
            assert plan.spend <= budget * tolerance
        observed.append(result.units_bought)
    assert max(observed) == max_units


@pytest.mark.parametrize("origin", ["planned", "impulse"])
@pytest.mark.parametrize("max_quantity", [1, 2, 6])
def test_plan_spending_matches_executed_quantity_limit(origin, max_quantity):
    config = SimulationConfig(budget_tolerance=None, max_quantity_per_line=max_quantity,
                              engines={"rule_based": {"multi_unit_prob": 0.9}})
    store, rack, slot, item, context, engine, plan, middle = purchase_fixture(config)
    out = ImpulseOutcome()
    if origin == "planned":
        assert engine.add_planned_buy(store, plan, middle, rack, slot, item, "planned extra")
    else:
        assert engine.add_impulse_buy(store, plan, out, rack, slot, item, "takes an extra")
    engine.close_plan(store, plan, middle)
    decision = engine._finish(context, plan, out)
    result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1.0,
                              max_quantity=max_quantity)
    assert result.units_bought == min(3, max_quantity)
    assert all(a.quantity <= max_quantity for a in decision.actions if a.action == Action.BUY)
    assert plan.spend == result.total_spent
