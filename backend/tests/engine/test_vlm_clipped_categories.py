"""Bounded model category names must not lose an otherwise unique directory match."""

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


LABELS = [
    ("Organic and specialty dry products", "Organic and specialty chilled beverages"),
    ("수입과일", "유기농과저지방우유및다양한대체우유를모아두고판매하는냉장유제품코너"),
    ("进口水果", "有机低脂牛奶以及多种植物奶和其他冷藏乳制品集中销售专用商品陈列区域"),
]


def prepared(labels, same_sku=False, reverse=False):
    store, engine = fixture(same_sku, reverse)
    for rack in store.product_racks:
        rack.rack_name = labels[0 if rack.id == "snacks" else 1]
        rack.rack_desc = rack.rack_name
    engine._llm.plan = {"enter": True, "items": [{"category": labels[1], "product": "Original", "qty": 1}]}
    return store, engine


@pytest.mark.parametrize("labels", LABELS)
@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_clipped_category_retains_its_unique_directory_prefix(labels, same_sku, reverse):
    store, engine = prepared(labels, same_sku, reverse)
    item = PlannedItem(category=labels[1], product="Original")
    assert len(labels[1]) > len(item.category) == 30
    match = match_plan_item(item, engine._catalog_for(store))
    assert match.how == "exact" and {entry[0].id for entry in match.candidates} == {"milk"}


@pytest.mark.parametrize("labels", LABELS)
@pytest.mark.parametrize("seed", [0, 1, 3, 7])
@pytest.mark.parametrize("same_sku", [False, True])
def test_long_category_model_response_preserves_the_intended_offer_and_revenue(labels, seed, same_sku):
    store, engine = prepared(labels, same_sku)
    decision = asyncio.run(engine.decide_actions(context_for(store, seed)))
    result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert len(result.purchases) == 1
    assert (result.purchases[0].target_rack, result.total_spent) == ("milk", 700)


@pytest.mark.parametrize("length", [29, 30])
def test_unclipped_exact_category_still_resolves(length):
    labels = ("Other", "x" * length)
    store, engine = prepared(labels)
    match = match_plan_item(PlannedItem(category=labels[1], product="Original"), engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"milk"}


def test_shared_truncated_prefix_is_kept_ambiguous():
    prefix = "a" * 30
    store, engine = prepared((prefix + " dry", prefix + " cold"))
    match = match_plan_item(PlannedItem(category=prefix, product="Original"), engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"snacks", "milk"}


@pytest.mark.parametrize("labels", LABELS)
@pytest.mark.parametrize("grammar_enforced", [False, True])
def test_strict_json_plan_resolves_full_or_grammar_bounded_category(labels, grammar_enforced):
    store, engine = prepared(labels)
    category = labels[1][:30] if grammar_enforced else labels[1]
    decision = entry_decision_model(3).model_validate_json(json.dumps({"items": [
        {"category": category, "product": "Original", "qty": 1}]}), strict=True)
    match = match_plan_item(decision.items[0], engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"milk"}


def test_truncated_label_does_not_impersonate_a_shorter_exact_directory_name():
    prefix = "a" * 30
    store, engine = prepared((prefix, prefix + " cold"))
    match = match_plan_item(PlannedItem(category=prefix + " cold", product="Original"), engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"snacks", "milk"}


@pytest.mark.parametrize("category", [" " * 30, "Organic and specialty chilled"])
def test_blank_or_unclipped_partial_label_does_not_claim_a_unique_prefix_match(category):
    store, engine = prepared(LABELS[0])
    match = match_plan_item(PlannedItem(category=category, product="Original"), engine._catalog_for(store))
    assert {entry[0].id for entry in match.candidates} == {"snacks", "milk"}
