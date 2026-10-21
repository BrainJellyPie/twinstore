"""Whole-pack allocation in explicit operator priority order, without sales forecasts."""

import csv
import io

from store_emulator.domain.restock_order import RestockOrderAction, RestockOrderPlan, RestockOrderRequest
from store_emulator.domain.shelf_lab import AuditReport


def plan_restock_order(audit: AuditReport, request: RestockOrderRequest) -> RestockOrderPlan:
    if request.currency != audit.currency:
        raise ValueError("Costs and budget must use the audit currency; no currency conversion is performed")
    names: dict[str, str] = {}
    levels: dict[str, set[int]] = {}
    unidentified = 0
    for finding in audit.findings:
        if finding.kind != "missing":
            continue
        if not finding.sku:
            unidentified += 1
            continue
        names.setdefault(finding.sku, finding.name)
        levels.setdefault(finding.sku, set()).add(finding.level)
    if any(item.sku not in names for item in request.items):
        raise ValueError("Plan only identified missing SKUs from this saved audit")
    available = max(0, request.budget_minor - request.delivery_fee_minor)
    actions: list[RestockOrderAction] = []
    for item in sorted(request.items, key=lambda row: (row.priority, row.sku)):
        stockroom_used = min(item.required_units, item.stockroom_units)
        shortfall = item.required_units - stockroom_used
        needed = (shortfall + item.pack_size - 1) // item.pack_size
        supplier_packs = min(needed, item.max_packs)
        affordable = available // item.pack_cost_minor if item.pack_cost_minor else supplier_packs
        ordered = min(supplier_packs, affordable) if request.budget_minor >= request.delivery_fee_minor else 0
        cost = ordered * item.pack_cost_minor
        available -= cost
        units = ordered * item.pack_size
        actions.append(RestockOrderAction(
            item=item, name=names[item.sku], levels=sorted(levels[item.sku]), stockroom_used=stockroom_used,
            packs_needed=needed, packs_ordered=ordered, units_ordered=units, cost_minor=cost,
            surplus_units=max(0, units - shortfall), unfilled_units=max(0, shortfall - units),
            supplier_limited=needed > item.max_packs, budget_limited=ordered < supplier_packs,
        ))
    goods = sum(action.cost_minor for action in actions)
    delivery = request.delivery_fee_minor if any(action.packs_ordered for action in actions) else 0
    return RestockOrderPlan(
        audit_id=audit.job_id, capture_id=audit.capture_id, setup_id=audit.setup_id, rack_id=audit.rack_id,
        face=audit.face, currency=audit.currency, budget_minor=request.budget_minor,
        delivery_fee_minor=request.delivery_fee_minor, delivery_charged_minor=delivery,
        goods_cost_minor=goods, total_cost_minor=goods + delivery,
        remaining_budget_minor=request.budget_minor - goods - delivery,
        omitted_skus=sorted(set(names) - {item.sku for item in request.items}), unidentified_findings=unidentified,
        actions=actions, notes=[
            "Required units, available stockroom units, pack sizes, costs and supplier limits are operator inputs. A photo's facings or a simulated revenue loss do not establish physical inventory quantities.",
            "Use stockroom inventory first, then allocate whole packs by ascending priority number; ties use case-sensitive SKU order. Each SKU is counted once across all audit levels. Partial pack counts may leave demand unfilled; pack rounding may create surplus.",
            "This is a sequential budget allocation, not a profit-maximizing optimizer. Earlier priorities may consume the budget; a cheaper later SKU can still receive packs when an earlier pack is unaffordable.",
            "The delivery fee is reserved once and charged only if any pack is ordered. All amounts are integer currency minor units. Include applicable taxes and charges in your inputs; separate suppliers or fees require separate plans.",
            "This worksheet does not place orders, reserve or update inventory, check expiry or lead time, or predict sales recovery. Verify counts, storage capacity, supplier availability and prices before acting. Reusing stockroom units in another plan can double-allocate them.",
        ],
    )


def restock_order_csv(plan: RestockOrderPlan) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["audit_id", "capture_id", "setup_id", "rack_id", "face", "currency", "budget_minor",
                     "delivery_fee_minor", "delivery_charged_minor", "total_cost_minor", "remaining_budget_minor", "omitted_skus", "unidentified_findings",
                     "sku", "name", "levels", "priority", "required_units", "stockroom_units", "pack_size",
                     "pack_cost_minor", "max_packs", "stockroom_used", "packs_needed", "packs_ordered",
                     "units_ordered", "surplus_units", "unfilled_units", "goods_cost_minor", "supplier_limited", "budget_limited"])
    for action in plan.actions:
        item = action.item
        row: list[str | int] = [plan.audit_id, plan.capture_id, plan.setup_id, plan.rack_id, plan.face, plan.currency,
                               plan.budget_minor, plan.delivery_fee_minor, plan.delivery_charged_minor,
                               plan.total_cost_minor, plan.remaining_budget_minor, ";".join(plan.omitted_skus), plan.unidentified_findings, item.sku, action.name,
                               ";".join(map(str, action.levels)), item.priority, item.required_units, item.stockroom_units,
                               item.pack_size, item.pack_cost_minor, item.max_packs, action.stockroom_used,
                               action.packs_needed, action.packs_ordered, action.units_ordered, action.surplus_units,
                               action.unfilled_units, action.cost_minor, int(action.supplier_limited), int(action.budget_limited)]
        writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
    return out.getvalue()
