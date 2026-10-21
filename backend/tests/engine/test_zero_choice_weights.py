import random

import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.engine.layout_gen.assortment import AssortmentCategory, generate_assortment_store
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine
from store_emulator.engine.simulation.engines.vlm_glance.planning import PlanMatch, pick_candidate


def store_with_promotion(all_products):
    store = generate_assortment_store([
        AssortmentCategory(key="drinks", label="Drinks", storage="fridge", items=[("Cola", 100), ("Water", 100)])
    ], store_id="test", name="Test")
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                if all_products or item.name == "Cola":
                    item.promo = "Special offer"
    return store


@pytest.mark.parametrize("planner", ["rule", "vlm"])
@pytest.mark.parametrize("cause", ["promotion", "attention"])
def test_zero_weight_products_are_not_selected(planner, cause):
    store = store_with_promotion(True)
    config = SimulationConfig(engines={"rule_based": {"promo_multiplier": 0 if cause == "promotion" else 1}},
                              perception={"level_attention": {1: 0, 2: 0, 3: 0, 4: 0}} if cause == "attention" else {})
    engine = RuleBasedEngine(AStarPathFinder(), config)
    if planner == "rule":
        result = engine._pick_item(store, "Drinks", 1000, set(), random.Random(0))
    else:
        result = pick_candidate(PlanMatch("category", tuple(engine._catalog_for(store))), chosen=set(), remaining=1000,
            attention=config.perception.level_attention, promo_multiplier=config.engines.rule_based.promo_multiplier,
            rng=random.Random(0))
    assert result is None


def test_zero_weight_usual_product_does_not_hide_a_valid_alternative():
    store = store_with_promotion(False)
    config = SimulationConfig(engines={"rule_based": {"promo_multiplier": 0, "habit_prob": 1}})
    engine = RuleBasedEngine(AStarPathFinder(), config)
    for seed in range(10):
        result = engine._pick_item(store, "Drinks", 1000, set(), random.Random(seed), frozenset({"cola"}))
        assert result is not None and result[2].name == "Water"


@pytest.mark.parametrize("planner", ["rule", "vlm"])
def test_zero_weight_candidates_leave_positive_weight_products_available(planner):
    store = store_with_promotion(False)
    config = SimulationConfig(engines={"rule_based": {"promo_multiplier": 0}})
    engine = RuleBasedEngine(AStarPathFinder(), config)
    for seed in range(10):
        if planner == "rule":
            result = engine._pick_item(store, "Drinks", 1000, set(), random.Random(seed))
        else:
            result = pick_candidate(PlanMatch("category", tuple(engine._catalog_for(store))), chosen=set(), remaining=1000,
                attention=config.perception.level_attention, promo_multiplier=0, rng=random.Random(seed))
        assert result is not None and result[2].name == "Water"
