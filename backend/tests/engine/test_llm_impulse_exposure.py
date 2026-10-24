"""Model-generated impulse purchases must come from the actual exposure list."""

import asyncio

import pytest

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import PerceptionConfig, SimulationConfig
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import IntentResponse
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage3_impulse import ImpulseResponse
from tests.engine.test_llm_engine_offline import _ScriptedLLM, _context, _persona


def fixture():
    def shelf(id, position, face, sku):
        return Rack(id=id, type="shelf", position=position, shape=[[1]], slots=[
            Slot(block=0, face=face, level=3, items=[SlotItem(sku=sku, name=sku, price=100)])])

    store = Store(id="exposure", name="Exposure", type="convenience", grid_size=(12, 6), racks=[
        shelf("near", (2, 1), Face.S, "seen"),
        shelf("far", (10, 1), Face.S, "unseen"),
        Rack(id="door", type="entrance", position=(0, 3), shape=[[1]]),
        Rack(id="exit", type="exit", position=(0, 4), shape=[[1]]),
        Rack(id="till", type="counter", position=(0, 1), shape=[[1]]),
    ])
    intent = IntentResponse(actions=[
        CustomerAction(nav="path", target=(0, 3), action=Action.ENTER),
        CustomerAction(nav="path", target=(2, 2), face=Face.S, action=Action.BROWSE),
        CustomerAction(nav="leave", action=Action.EXIT),
    ])
    return store, intent


def buy(sku, target=(10, 2)):
    return CustomerAction(nav="path", target=target, face=Face.S, action=Action.BUY, product_sku=sku)


def run(store, intent, impulse, ordering, exposure, *, cap=4, budget=None, perception=None):
    llm = _ScriptedLLM(intent, ImpulseResponse(actions=impulse))
    config = SimulationConfig(route_ordering=ordering, exposure_model=exposure, budget_tolerance=budget,
                              perception=perception or PerceptionConfig())
    context = _context(store, _persona(100))
    pattern = next(p for p in context.behavior_patterns if p.id == "exploratory")
    context.behavior_patterns = [pattern.model_copy(update={"max_products": cap})]
    decision = asyncio.run(PatternIntentImpulseEngine(llm, AStarPathFinder(), config).decide_actions(context))
    result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    return decision, result, llm


@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("exposure", ["adjacency", "visibility"])
@pytest.mark.parametrize("target", [(10, 2), (2, 2), None, (-100, 100)])
def test_existing_but_unseen_product_cannot_create_impulse_sales(ordering, exposure, target):
    store, intent = fixture()
    before = store.model_dump_json()
    decision, result, llm = run(store, intent, [buy("unseen", target)], ordering, exposure)
    assert decision.trace["exposed_skus"] == ["seen"]
    assert not result.purchases and result.total_spent == 0
    assert not any(event.action == Action.PAY for event in result.timeline)
    assert not any(event.target_rack == "far" for event in result.timeline)
    assert result.timeline[-1].action == Action.EXIT
    assert decision.trace["dropped_unexposed_buys"] == 1
    assert decision.dropped_invalid_buys == decision.dropped_over_budget == 0
    assert decision.trace["stage3"]["actions"][0]["product_sku"] == "unseen"
    assert len(llm.calls) == 3 and store.model_dump_json() == before


@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("exposure", ["adjacency", "visibility"])
@pytest.mark.parametrize("reverse", [False, True])
def test_unseen_and_invented_buys_do_not_take_visible_budget_or_basket_slot(ordering, exposure, reverse):
    store, intent = fixture()
    actions = [buy("unseen"), buy("invented"), buy("seen", (2, 2))]
    if reverse:
        actions.reverse()
    decision, result, _ = run(store, intent, actions, ordering, exposure, cap=1, budget=1)
    assert [event.product_sku for event in result.purchases] == ["seen"]
    assert result.total_spent == 100
    assert decision.trace["dropped_unexposed_buys"] == 1
    assert decision.dropped_invalid_buys == 1 and decision.dropped_over_budget == 0
    assert decision.trace["dropped_product_limit"] == 0
    assert sum(event.action == Action.PAY for event in result.timeline) == 1


@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("exposure", ["adjacency", "visibility"])
def test_exposure_constraint_does_not_reject_planned_product_destinations(ordering, exposure):
    store, intent = fixture()
    intent.actions.insert(2, buy("unseen"))
    decision, result, _ = run(store, intent, [], ordering, exposure)
    assert [event.product_sku for event in result.purchases] == ["unseen"]
    assert result.total_spent == 100 and result.purchases[0].origin == "planned"


@pytest.mark.parametrize("ordering", ["planned", "nearest"])
def test_visibility_cap_is_the_same_list_presented_to_the_model(ordering):
    store, intent = fixture()
    store.racks[0].slots[0].items.append(SlotItem(sku="seen-second", name="Second", price=100))
    decision, result, llm = run(store, intent, [buy("seen-second", (2, 2))], ordering, "visibility",
                               perception=PerceptionConfig(max_exposed_items=1))
    assert decision.trace["exposed_skus"] == ["seen"]
    assert "seen-second" not in llm.calls[-1][2]
    assert not result.purchases and decision.trace["dropped_unexposed_buys"] == 1


@pytest.mark.parametrize("ordering", ["planned", "nearest"])
def test_opposite_face_product_is_rejected_only_when_visibility_says_unseen(ordering):
    store, intent = fixture()
    store.racks[0].slots.append(Slot(block=0, face=Face.N, level=3, items=[
        SlotItem(sku="opposite", name="Opposite face", price=100)]))
    action = buy("opposite", (2, 0)).model_copy(update={"face": Face.N})
    decision, result, _ = run(store, intent, [action], ordering, "visibility")
    assert "opposite" not in decision.trace["exposed_skus"]
    assert not result.purchases and decision.trace["dropped_unexposed_buys"] == 1
    decision, result, _ = run(store, intent, [action], ordering, "adjacency")
    assert "opposite" in decision.trace["exposed_skus"]
    assert [event.product_sku for event in result.purchases] == ["opposite"]


def test_empty_exposure_still_skips_the_impulse_model():
    store, intent = fixture()
    intent.actions = [intent.actions[0], intent.actions[-1]]
    decision, result, llm = run(store, intent, [buy("seen")], "planned", "adjacency")
    assert decision.trace["exposed_skus"] == [] and len(llm.calls) == 2
    assert not result.purchases


@pytest.mark.parametrize("include_seen", [False, True])
def test_only_seen_impulse_sales_reach_shared_store_metrics(include_seen):
    from store_emulator.domain.operations import OperationsConfig
    from store_emulator.engine.simulation.shared_store import resolve_shared_store

    store, intent = fixture()
    actions = [buy("unseen")]
    if include_seen:
        actions.append(buy("seen", (2, 2)))
    _, result, _ = run(store, intent, actions, "planned", "visibility")
    results, report = resolve_shared_store(store, [result], OperationsConfig(
        restock_every_min=None, substitute_share=0), seed=1)
    assert results[0].total_spent == (100 if include_seen else 0)
    assert report.queued == int(include_seen)
    assert report.lost_units == report.lost_revenue == 0
