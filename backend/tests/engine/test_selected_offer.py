"""A chosen shelf offer survives routing, execution and stockout accounting."""
import pytest

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.rack import Slot, SlotItem
from store_emulator.domain.types import Weekday
from store_emulator.engine.routing.invariants import check_buy_consistency
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.rule_based import ImpulseOutcome
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from tests.engine.test_purchase_quantity_limits import purchase_fixture


@pytest.mark.parametrize("origin", ["planned", "impulse"])
@pytest.mark.parametrize("price", [0, 25, 200])
@pytest.mark.parametrize("selected_index", [0, 1])
def test_selected_level_price_matches_planned_spend_and_stockout_loss(origin, price, selected_index):
    config = SimulationConfig(budget_tolerance=1, engines={"rule_based": {"multi_unit_prob": 0}})
    store, rack, original, item, context, engine, plan, middle = purchase_fixture(config)
    # One face offers the same SKU at two prices, as allowed by the layout editor.
    rack.slots = [original.model_copy(update={"items": [item.model_copy()]}, deep=True),
        Slot(block=original.block, face=original.face, level=4,
        items=[SlotItem(sku=item.sku, name="Selected offer", price=price)])]
    selected = rack.slots[selected_index]
    expected_price = selected.items[0].price
    plan.budget = max(1, expected_price)
    out = ImpulseOutcome()
    if origin == "planned":
        assert engine.add_planned_buy(store, plan, middle, rack, selected, selected.items[0], "choose this offer")
    else:
        assert engine.add_impulse_buy(store, plan, out, rack, selected, selected.items[0], "choose this offer")
    engine.close_plan(store, plan, middle)
    decision = engine._finish(context, plan, out)
    result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1.0)
    assert result.total_spent == plan.spend == expected_price
    assert result.purchases[0].product_name == selected.items[0].name
    assert check_buy_consistency(store, [result]) == []
    actual, report = resolve_shared_store(store, [result], OperationsConfig(
        stock_overrides={item.sku: 0}, restock_every_min=None, substitute_share=0), seed=1)
    assert actual[0].total_spent == 0
    assert report.lost_units == 1 and report.lost_revenue == expected_price

    bulk = result.model_copy(deep=True)
    bulk.purchases[0].quantity = 3
    bulk.total_spent = 3 * expected_price
    actual, report = resolve_shared_store(store, [bulk], OperationsConfig(
        stock_per_facing=1, restock_every_min=None, substitute_share=0), seed=1)
    assert actual[0].total_spent == 2 * expected_price
    assert report.lost_units == 1 and report.lost_revenue == expected_price

    alternatives = [SlotItem(sku=f"alternative_{p}", name=f"Alternative {p}", price=p) for p in [10, 80, 300]]
    rack.slots[0].items.extend(alternatives)
    actual, report = resolve_shared_store(store, [bulk], OperationsConfig(
        stock_per_facing=1, stock_overrides={item.sku: 0}, restock_every_min=None, substitute_share=1), seed=1)
    substitute = min(alternatives, key=lambda offer: (abs(offer.price - expected_price), offer.price, offer.sku))
    assert actual[0].total_spent == substitute.price
    assert actual[0].purchases[0].product_sku == substitute.sku
    assert report.lost_units == 2 and report.lost_revenue == 2 * expected_price


def test_engine_placement_hints_stay_out_of_model_response_schemas():
    from store_emulator.domain.action import CustomerAction
    fields = CustomerAction.model_json_schema()["properties"]
    assert "product_block" not in fields and "product_level" not in fields
