import csv
import io
import random

import pytest
from pydantic import ValidationError

from store_emulator.domain.restock_order import RestockOrderItem, RestockOrderRequest
from store_emulator.domain.shelf_lab import AuditFinding, AuditReport
from store_emulator.engine.shelf_lab.restock_order import plan_restock_order, restock_order_csv


def audit():
    return AuditReport(job_id="aud_test", capture_id="cap_test", setup_id="setup_test", rack_id="rack", face="N",
                       currency="KRW", compliance=0.5, findings=[
                           AuditFinding(kind="missing", level=1, sku="tea", name="Tea", loss_per_day=1000),
                           AuditFinding(kind="missing", level=2, sku="tea", name="Tea", loss_per_day=1000),
                           AuditFinding(kind="missing", level=1, sku="snack", name="Snack"),
                           AuditFinding(kind="missing", level=3),
                           AuditFinding(kind="price", level=4, sku="other"),
                       ])


def item(sku="tea", **kwargs):
    return RestockOrderItem.model_validate({"sku": sku, "required_units": 10, "stockroom_units": 2,
                                           "pack_size": 6, "pack_cost_minor": 100, "max_packs": 20, "priority": 1, **kwargs})


def test_stockroom_first_whole_packs_and_surplus_without_double_counting_levels():
    report = audit()
    request = RestockOrderRequest(currency="KRW", budget_minor=1000, delivery_fee_minor=50, items=[item()])
    plan = plan_restock_order(report, request); action = plan.actions[0]
    assert (action.stockroom_used, action.packs_needed, action.packs_ordered, action.units_ordered) == (2, 2, 2, 12)
    assert (action.surplus_units, action.unfilled_units, action.cost_minor) == (4, 0, 200)
    assert action.levels == [1, 2] and plan.omitted_skus == ["snack"] and plan.unidentified_findings == 1
    assert (plan.goods_cost_minor, plan.delivery_charged_minor, plan.total_cost_minor, plan.remaining_budget_minor) == (200, 50, 250, 750)
    for finding in report.findings:
        finding.loss_per_day = -99999999
    assert plan_restock_order(report, request) == plan


def test_budget_and_supplier_limits_and_explicit_priority():
    request = RestockOrderRequest(currency="KRW", budget_minor=270, delivery_fee_minor=20, items=[
        item("tea", required_units=20, stockroom_units=0, max_packs=2, pack_cost_minor=200, priority=1),
        item("snack", required_units=7, stockroom_units=0, pack_size=3, pack_cost_minor=25, priority=2),
    ])
    plan = plan_restock_order(audit(), request); tea, snack = plan.actions
    assert tea.packs_ordered == 1 and tea.unfilled_units == 14
    assert tea.supplier_limited and tea.budget_limited
    assert snack.packs_ordered == 2 and snack.unfilled_units == 1 and snack.budget_limited
    assert plan.total_cost_minor == 270 and plan.remaining_budget_minor == 0
    request.items[1].priority = 1; request.items[0].priority = 2
    reordered = plan_restock_order(audit(), request)
    assert reordered.actions[0].item.sku == "snack" and reordered.actions[0].packs_ordered == 3
    assert reordered.actions[1].packs_ordered == 0


def test_equal_priority_is_stable_under_request_order():
    rows = [item("tea", stockroom_units=0, pack_cost_minor=1000), item("snack", stockroom_units=0, pack_cost_minor=50)]
    request = RestockOrderRequest(currency="KRW", budget_minor=100, items=rows)
    plan = plan_restock_order(audit(), request); request.items.reverse()
    assert plan == plan_restock_order(audit(), request)
    assert [row.item.sku for row in plan.actions] == ["snack", "tea"]
    assert [row.packs_ordered for row in plan.actions] == [2, 0]


@pytest.mark.parametrize("budget,fee,stock,packs,cost,expected_packs,charged", [
    (0, 10, 20, 20, 100, 0, 0), (99, 100, 0, 20, 0, 0, 0),
    (100, 100, 0, 20, 0, 2, 100), (100, 0, 0, 0, 100, 0, 0),
    (0, 0, 0, 20, 0, 2, 0), (100, 100, 0, 20, 1, 0, 0),
])
def test_zero_cost_fee_and_no_order_edges(budget, fee, stock, packs, cost, expected_packs, charged):
    plan = plan_restock_order(audit(), RestockOrderRequest(currency="KRW", budget_minor=budget, delivery_fee_minor=fee,
                              items=[item(stockroom_units=stock, max_packs=packs, pack_cost_minor=cost)]))
    assert plan.actions[0].packs_ordered == expected_packs and plan.delivery_charged_minor == charged
    assert plan.remaining_budget_minor == budget - plan.total_cost_minor


def test_random_plans_conserve_units_and_budget_with_integer_costs():
    rng = random.Random(71)
    for _ in range(100):
        request = RestockOrderRequest(currency="KRW", budget_minor=rng.randrange(100000), delivery_fee_minor=rng.randrange(1000),
                    items=[item(sku, required_units=rng.randrange(1000), stockroom_units=rng.randrange(1000),
                                pack_size=rng.randrange(1, 100), pack_cost_minor=rng.randrange(1000), max_packs=rng.randrange(20),
                                priority=rng.randrange(1, 4)) for sku in ("tea", "snack")])
        plan = plan_restock_order(audit(), request)
        assert plan.total_cost_minor <= request.budget_minor
        assert plan.total_cost_minor + plan.remaining_budget_minor == request.budget_minor
        assert sum(row.cost_minor for row in plan.actions) + plan.delivery_charged_minor == plan.total_cost_minor
        for row in plan.actions:
            assert row.stockroom_used <= row.item.stockroom_units and row.packs_ordered <= row.item.max_packs
            assert row.units_ordered == row.packs_ordered * row.item.pack_size
            assert row.stockroom_used + row.units_ordered + row.unfilled_units == row.item.required_units + row.surplus_units
            assert not (row.unfilled_units and row.surplus_units)


@pytest.mark.parametrize("field,value", [("pack_size", 0), ("pack_size", True), ("required_units", -1),
                                        ("stockroom_units", 1.0), ("pack_cost_minor", "1"), ("priority", 0),
                                        ("max_packs", 1000001), ("pack_cost_minor", 1000000000001)])
def test_invalid_or_coerced_inputs_are_rejected(field, value):
    with pytest.raises(ValidationError):
        item(**{field: value})


def test_duplicate_unknown_and_currency_mismatched_inputs_are_rejected():
    with pytest.raises(ValidationError, match="each SKU once"):
        RestockOrderRequest(currency="KRW", budget_minor=100, items=[item(), item()])
    for sku in ("other", "unknown"):
        with pytest.raises(ValueError, match="identified missing"):
            plan_restock_order(audit(), RestockOrderRequest(currency="KRW", budget_minor=100, items=[item(sku)]))
    with pytest.raises(ValueError, match="currency"):
        plan_restock_order(audit(), RestockOrderRequest(currency="USD", budget_minor=100, items=[item()]))


def test_csv_contains_inputs_source_budget_and_formula_safe_names():
    report = audit(); report.findings[0].name = " =HYPERLINK(\"bad\")"
    plan = plan_restock_order(report, RestockOrderRequest(currency="KRW", budget_minor=1000, items=[item()]))
    rows = list(csv.DictReader(io.StringIO(restock_order_csv(plan))))
    assert len(rows) == 1 and rows[0]["audit_id"] == "aud_test" and rows[0]["levels"] == "1;2"
    assert rows[0]["name"].startswith("' =") and rows[0]["required_units"] == "10"
    assert rows[0]["omitted_skus"] == "snack" and rows[0]["unidentified_findings"] == "1"
    assert rows[0]["total_cost_minor"] == "200" and rows[0]["surplus_units"] == "4"
