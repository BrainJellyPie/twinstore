"""Plans must select an accessible offer before reserving its SKU, budget or basket position."""

import asyncio

import pytest

from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.rule_based import ImpulseOutcome, RuleBasedEngine
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from tests.engine.routing.test_reachable_service_routes import divided_visit
from tests.engine.test_vlm_plan import _FakeVLM, _config, _context, _personas


def divided_store(side):
    store, _, _ = divided_visit("two", False, side, "local")
    local = next(r for r in store.racks if r.id == "product")
    local.rack_name = "Drinks"
    remote = Rack(id="remote-product", type="shelf", rack_name="Drinks", shape=[[1]],
                  position=(2 if side else 7, 3), slots=[Slot(block=0, face=Face.N, level=1, items=[
                      SlotItem(sku="tea", name="Tea", price=1, promo="SALE"),
                      SlotItem(sku="remote-only", name="Remote drink", price=0),
                  ])])
    store.racks.append(remote)
    return store, local, remote


def engine_context(store, kind, seed, diagonal):
    config = _config(entrance_image=False, max_glances=0, max_plan_items=3)
    config.engines.rule_based.walkout_prob = 0
    config.engines.rule_based.impulse_base = 0
    context = _context(store, _personas(1)[0], seed)
    context.persona = context.persona.model_copy(update={"preferred_categories": ["Drinks"], "budget_max": 100,
                                                       "basket_size": 2, "basket_kinds": 1})
    paths = AStarPathFinder(diagonal=diagonal)
    engine = RuleBasedEngine(paths, config) if kind == "rule" else VLMGlanceEngine(_FakeVLM({
        "enter": True, "items": [{"category": "Drinks", "product": "Tea", "qty": 1}],
    }), paths, config)
    return engine, context, paths


@pytest.mark.parametrize("kind", ["rule", "vlm"])
@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("diagonal", [False, True])
@pytest.mark.parametrize("seed", range(4))
def test_disconnected_promoted_and_free_offers_cannot_displace_accessible_purchases(kind, side, diagonal, seed):
    store, local, remote = divided_store(side)
    engine, context, paths = engine_context(store, kind, seed, diagonal)
    decision = asyncio.run(engine.decide_actions(context))
    result = execute_decision(store, "p", Weekday.MON, "12:00:00", decision, paths, 1)
    chosen = [action for action in decision.actions if action.action == Action.BUY]
    assert len(chosen) == len(result.purchases) == 1
    assert result.purchases[0].target_rack == local.id
    assert result.purchases[0].price == 100 and result.total_spent == 100

    # Removing inaccessible art/offers must not change seeded decisions in the customer's own area.
    without = store.model_copy(update={"racks": [r for r in store.racks if r is not remote]})
    other, other_context, other_paths = engine_context(without, kind, seed, diagonal)
    other_decision = asyncio.run(other.decide_actions(other_context))
    other_result = execute_decision(without, "p", Weekday.MON, "12:00:00", other_decision, other_paths, 1)
    assert result.model_dump() == other_result.model_dump()


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("action", ["planned", "impulse", "look"])
def test_unreachable_stops_cannot_reserve_a_budget_or_chosen_sku(side, action):
    store, _, remote = divided_store(side)
    engine, context, _ = engine_context(store, "rule", 0, False)
    plan, middle = engine._begin_plan(context)
    outcome = ImpulseOutcome()
    slot = remote.slots[0]
    if action == "planned":
        added = engine.add_planned_buy(store, plan, middle, remote, slot, slot.items[0], "remote")
    elif action == "impulse":
        added = engine.add_impulse_buy(store, plan, outcome, remote, slot, slot.items[0], "remote")
    else:
        added = engine.add_impulse_look(store, plan, outcome, remote, slot, "remote")
    assert added is False
    assert plan.spend == 0 and not plan.chosen and not plan.buys and not outcome.actions


def test_engine_recomputes_access_when_used_with_another_layout():
    store, _, remote = divided_store(0)
    engine, context, _ = engine_context(store, "rule", 0, False)
    assert all(entry[0].id != remote.id for entry in engine._catalog_for(store))
    opened = store.model_copy(update={"racks": [r for r in store.racks if r.id != "wall-5"]})
    assert any(entry[0].id == remote.id for entry in engine._catalog_for(opened))
    assert all(entry[0].id != remote.id for entry in engine._catalog_for(store))


def test_new_run_rebuilds_access_after_in_place_layout_edits():
    store, _, remote = divided_store(0)
    engine, _, _ = engine_context(store, "rule", 0, False)
    engine.prepare(store)
    assert all(entry[0].id != remote.id for entry in engine._catalog_for(store))
    store.racks = [r for r in store.racks if r.id != "wall-5"]
    engine.prepare(store)
    assert any(entry[0].id == remote.id for entry in engine._catalog_for(store))
