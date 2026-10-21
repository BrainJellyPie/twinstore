"""Exact scenario targets do not expand to unrelated products with similar words."""
import pytest

from store_emulator.domain.scenario import Promotion, Scenario
from store_emulator.domain.store import Store
from store_emulator.engine.scenario import apply_to_store


def target_store():
    return Store.model_validate({"id": "test", "name": "Test", "type": "convenience", "grid_size": [8, 6], "racks": [
        {"id": "r1", "type": "shelf", "shape": [[1]], "position": [2, 2], "rack_name": "Drinks 1", "rack_desc": "soft_drinks",
         "slots": [{"block": 0, "face": "S", "items": [
             {"sku": "s-cola", "name": "Cola 500ml", "price": 100},
             {"sku": "s-zero", "name": "Zero Cola 500ml", "price": 100},
             {"sku": "s-lemon", "name": "Lemon Soda 500ml", "price": 100},
             {"sku": "s-large", "name": "Cola 1.5L", "price": 100},
         ]}]},
        {"id": "r10", "type": "shelf", "shape": [[1]], "position": [4, 2], "rack_name": "Drinks 10", "rack_desc": "beer",
         "slots": [{"block": 0, "face": "S", "items": [
             {"sku": "s-beer", "name": "Lager Beer 500ml", "price": 100},
         ]}]},
    ]})


@pytest.mark.parametrize("mode", ["promotion", "stockout"])
@pytest.mark.parametrize("target,expected", [
    ("Cola 500ml", {"s-cola"}), ("  cOLA 500ML  ", {"s-cola"}), ("s-cola", {"s-cola"}),
    ("Drinks 1", {"s-cola", "s-zero", "s-lemon", "s-large"}),
    ("  DRINKS 1 ", {"s-cola", "s-zero", "s-lemon", "s-large"}),
    ("soft_drinks", {"s-cola", "s-zero", "s-lemon", "s-large"}),
    ("cola", {"s-cola", "s-zero", "s-large"}),
])
def test_exact_targets_and_keyword_targets_have_distinct_scope(mode, target, expected):
    store = target_store()
    before = store.model_dump()
    original = {item.sku for rack in store.racks for slot in rack.slots for item in slot.items}
    scenario = (Scenario(promotions=[Promotion(target=target, discount_pct=50)]) if mode == "promotion"
                else Scenario(stockouts=[target]))
    changed, lifts = apply_to_store(store, scenario)
    items = {item.sku: item for rack in changed.racks for slot in rack.slots for item in slot.items}
    if mode == "promotion":
        assert {sku for sku, item in items.items() if item.price == 50} == expected
        assert set(lifts) == expected
    else:
        assert original - set(items) == expected
    assert store.model_dump() == before


@pytest.mark.parametrize("mode", ["promotion", "stockout"])
def test_exact_sku_does_not_match_another_products_name(mode):
    store = target_store()
    store.racks[1].slots[0].items[0].name = "Accessory for s-cola"
    scenario = (Scenario(promotions=[Promotion(target="s-cola")]) if mode == "promotion"
                else Scenario(stockouts=["s-cola"]))
    changed, _ = apply_to_store(store, scenario)
    other = next(item for rack in changed.racks for slot in rack.slots for item in slot.items if item.sku == "s-beer")
    assert other.price == 100 and not other.promo


def test_a_sold_out_exact_product_does_not_make_its_promotion_expand():
    store = target_store()
    changed, lifts = apply_to_store(store, Scenario(stockouts=["Cola 500ml"], promotions=[Promotion(target="Cola 500ml")]))
    items = {item.sku: item for rack in changed.racks for slot in rack.slots for item in slot.items}
    assert set(items) == {"s-zero", "s-lemon", "s-large", "s-beer"}
    assert not lifts and all(item.price == 100 and not item.promo for item in items.values())
