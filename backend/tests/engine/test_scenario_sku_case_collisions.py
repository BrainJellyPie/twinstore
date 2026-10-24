"""Case-distinct SKU identities must not collapse when applying a scenario."""

import pytest

from store_emulator.domain.rack import SlotItem
from store_emulator.domain.scenario import Promotion, Scenario
from store_emulator.engine.scenario import apply_to_store
from store_emulator.engine.scenario_writer import matched_skus
from tests.engine.test_scenario_target_matching import target_store


def store_with_skus(skus):
    store = target_store()
    store.racks[0].slots[0].items = [SlotItem(sku=sku, name=f"Product {index}", price=100) for index, sku in enumerate(skus)]
    return store


@pytest.mark.parametrize("skus", [("tea", "TEA", "Tea"), ("sku-1", "SKU-1", "Sku-1"), ("α1", "Α1")])
@pytest.mark.parametrize("mode", ["promotion", "stockout"])
@pytest.mark.parametrize("padded", [False, True])
def test_exact_id_changes_only_that_product_in_each_case_family(skus, mode, padded):
    store = store_with_skus(skus)
    original = store.model_dump()
    for sku in skus:
        target = f"  {sku}  " if padded else sku
        scenario = Scenario(promotions=[Promotion(target=target, discount_pct=50)]) if mode == "promotion" else Scenario(stockouts=[target])
        changed, lifts = apply_to_store(store, scenario)
        items = {item.sku: item for rack in changed.racks for slot in rack.slots for item in slot.items}
        if mode == "promotion":
            assert {key for key, item in items.items() if item.price == 50} == {sku}
            assert set(lifts) == {sku}
        else:
            assert set(skus) - set(items) == {sku}
        assert matched_skus(store, target) == {sku}
    assert store.model_dump() == original


@pytest.mark.parametrize("mode", ["promotion", "stockout"])
def test_ambiguous_case_fallback_does_not_change_multiple_ids(mode):
    store = store_with_skus(("tea", "TEA"))
    scenario = Scenario(promotions=[Promotion(target="tEa")]) if mode == "promotion" else Scenario(stockouts=["tEa"])
    changed, lifts = apply_to_store(store, scenario)
    assert changed == store
    assert lifts == {}
    assert matched_skus(store, "tEa") == set()


@pytest.mark.parametrize("target", ["tea", "TEA", "tEa", "  TEA  "])
def test_unique_case_insensitive_id_remains_supported(target):
    store = store_with_skus(("Tea",))
    assert matched_skus(store, target) == {"Tea"}


def test_sold_out_case_variant_does_not_suppress_another_variants_promotion():
    store = store_with_skus(("tea", "TEA", "Tea"))
    changed, lifts = apply_to_store(store, Scenario(stockouts=["tea"], promotions=[
        Promotion(target="TEA", discount_pct=50), Promotion(target="Tea", discount_pct=20),
    ]))
    items = {item.sku: item for rack in changed.racks for slot in rack.slots for item in slot.items}
    assert "tea" not in items
    assert items["TEA"].price == 50
    assert items["Tea"].price == 80
    assert set(lifts) == {"TEA", "Tea"}


@pytest.mark.parametrize("mode", ["promotion", "stockout"])
def test_blank_target_stays_a_noop_even_with_an_empty_legacy_sku(mode):
    store = store_with_skus(("", "tea"))
    scenario = Scenario(promotions=[Promotion(target="  ")]) if mode == "promotion" else Scenario(stockouts=["  "])
    changed, lifts = apply_to_store(store, scenario)
    assert changed == store
    assert lifts == {}
