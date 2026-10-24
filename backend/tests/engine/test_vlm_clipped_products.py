"""A bounded entry-plan product name must not select an unrelated catalog item."""

import asyncio
import json

import pytest

from store_emulator.domain.types import Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance.planning import match_plan_item
from store_emulator.engine.simulation.engines.vlm_glance.prompt import PlannedItem, entry_decision_model
from tests.engine.test_purchase_quantity_limits import context_for
from tests.engine.test_vlm_plan_category_disambiguation import fixture


NAMES = [
    "유기농원두로정성껏추출하고신선한우유를더해부드럽고풍부한향을즐길수있는프리미엄무가당콜드브루라테대용량",
    "精选有机咖啡豆低温萃取后加入新鲜牛奶制作而成口感顺滑香气浓郁无添加糖适合早餐下午茶饮用的冷藏拿铁大容量装",
    "ArtisanSingleOriginColombianColdBrewCoffeeWithFreshMilk500ml",
]


def prepared(name, *, other="Different product", same_sku=False, reverse=False):
    store, engine = fixture(same_sku, reverse)
    for rack in store.product_racks:
        rack.rack_name = rack.rack_desc = "Drinks"
        rack.slots[0].items[0].name = name if rack.id == "milk" else other
    engine._llm.plan = {"enter": True, "items": [{"category": "Drinks", "product": name, "qty": 2}]}
    return store, engine


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_unique_clipped_product_retains_its_offer(name, same_sku, reverse):
    store, engine = prepared(name, same_sku=same_sku, reverse=reverse)
    item = PlannedItem(category="Drinks", product=name)
    assert len(name) > len(item.product) == 48
    match = match_plan_item(item, engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"milk"}


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("seed", [0, 1, 7])
def test_clipped_model_choice_keeps_real_purchase_and_price(name, seed):
    store, engine = prepared(name)
    before = store.model_dump()
    decision = asyncio.run(engine.decide_actions(context_for(store, seed)))
    result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert len(result.purchases) == 1
    assert (result.purchases[0].target_rack, result.purchases[0].quantity, result.total_spent) == ("milk", 2, 1400)
    assert store.model_dump() == before


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("grammar_enforced", [False, True])
@pytest.mark.parametrize("category", ["", "Unknown", "Drinks"])
def test_strict_json_full_or_grammar_bounded_product(name, grammar_enforced, category):
    store, engine = prepared(name)
    decision = entry_decision_model(3).model_validate_json(json.dumps({"enter": True, "items": [
        {"category": category, "product": name[:48] if grammar_enforced else name}]}), strict=True)
    match = match_plan_item(decision.items[0], engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"milk"}


@pytest.mark.parametrize("other_suffix", ["", " alternative"])
def test_shared_clipped_prefix_remains_ambiguous_including_a_short_exact_name(other_suffix):
    prefix = "a" * 48
    store, engine = prepared(prefix + " wanted", other=prefix + other_suffix)
    match = match_plan_item(PlannedItem(category="Drinks", product=prefix + " wanted"), engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"snacks", "milk"}


def test_named_category_still_disambiguates_shared_product_prefixes():
    prefix = "a" * 48
    store, engine = prepared(prefix + " wanted", other=prefix + " alternative")
    for rack in store.product_racks:
        rack.rack_name = rack.rack_desc = rack.id.title()
    match = match_plan_item(PlannedItem(category="Milk", product=prefix), engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"milk"}


@pytest.mark.parametrize("product", ["a" * 47, " " * 48])
def test_unclipped_or_blank_name_does_not_claim_a_prefix(product):
    store, engine = prepared("a" * 52)
    match = match_plan_item(PlannedItem(category="Drinks", product=product), engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"snacks", "milk"}
