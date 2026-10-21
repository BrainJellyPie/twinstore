"""Scenario discounts retain the was-price used by shopper prompts and price response."""
import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.scenario import Promotion, PromotionKind, Scenario
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.perception import directory_text, store_directory
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.scenario import apply_to_store
from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine


def store_with_reference(reference):
    store = generate_store("urban_cvs")
    original = next(item for rack in store.product_racks for slot in rack.slots for item in slot.items
                    if item.name == "Cola 500ml")
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                if item.sku == original.sku:
                    item.regular_price = reference
    return store, original


@pytest.mark.parametrize("reference", [0, 299, 499])
@pytest.mark.parametrize("discount", [0, 20, 50, 90])
def test_scenario_discount_keeps_reference_price_for_shopper_decisions(reference, discount):
    store, original = store_with_reference(reference)
    changed, _ = apply_to_store(store, Scenario(promotions=[Promotion(target=original.sku, discount_pct=discount)]))
    revised = [item for rack in changed.product_racks for slot in rack.slots for item in slot.items if item.sku == original.sku]
    expected_reference = reference or original.price
    assert revised and all(item.regular_price == expected_reference for item in revised)
    assert all(item.price == round(original.price * (1 - discount / 100)) for item in revised)
    assert original.price == 229 and original.regular_price == reference
    engine = RuleBasedEngine(AStarPathFinder(), SimulationConfig())
    if revised[0].price < expected_reference:
        assert engine._price_factor(revised[0]) > 1
        text = directory_text(store_directory(changed, examples=50), "USD", item_prices=True)
        assert f"(was ${expected_reference / 100:.2f})" in text
    else:
        assert engine._price_factor(revised[0]) == 1


@pytest.mark.parametrize("kind", [PromotionKind.FEATURED, PromotionKind.ONE_PLUS_ONE, PromotionKind.TWO_PLUS_ONE])
@pytest.mark.parametrize("reference", [0, 299])
def test_non_discount_promotions_keep_price_and_reference(kind, reference):
    store, original = store_with_reference(reference)
    changed, _ = apply_to_store(store, Scenario(promotions=[Promotion(target=original.sku, kind=kind)]))
    revised = [item for rack in changed.product_racks for slot in rack.slots for item in slot.items if item.sku == original.sku]
    assert all((item.price, item.regular_price) == (229, reference) for item in revised)
