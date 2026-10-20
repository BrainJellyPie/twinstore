from collections import Counter

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import (
    AggregatedResult, ProductStats, RackStats, RunDiagnostics, SegmentStats, SimulationSummary,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action
from store_emulator.engine.routing.invariants import check_buy_consistency

# Persona attributes reported as segments. identity/purpose are free-ish labels, still useful to slice.
_SEGMENT_DIMENSIONS = ("age_group", "gender", "purpose", "identity")


def summary_currency_label(currency: str) -> str:
    """Legacy label for USD runs ("USD_CENTS"); ISO code otherwise (minor unit implied)."""
    return "USD_CENTS" if currency.upper() == "USD" else currency.upper()


def aggregate(
    store: Store,
    results: list[CustomerResult],
    personas: list[Persona],
    pathcalc_heatmap: list[list[float]],
    *,
    block_move_sec: int = 1,
    currency: str = "USD",
) -> AggregatedResult:
    persona_map = {p.id: p for p in personas}
    w, h = store.grid_size
    rack_names = {r.id: r.rack_name for r in store.racks}

    product_revenue: Counter[str] = Counter()  # legacy: keyed by product name
    product_units: Counter[str] = Counter()
    products: dict[str, ProductStats] = {}
    product_buyers: dict[str, set[str]] = {}
    racks: dict[str, RackStats] = {}
    rack_people: dict[str, tuple[set[str], set[str], set[str]]] = {}  # visitors, browsers, buyers
    behavioral: list[list[int]] = [[0] * w for _ in range(h)]
    dwell: list[list[float]] = [[0.0] * w for _ in range(h)]
    hourly: Counter[str] = Counter()

    buyers = units = revenue = impulse_units = impulse_revenue = 0
    visit_sec = path_tiles = 0

    for cr in results:
        hourly[cr.arrival_time[:2]] += 1
        visit_sec += cr.duration_sec
        bought_any = False
        for event in cr.timeline:
            if 0 <= event.x < w and 0 <= event.y < h:
                behavioral[event.y][event.x] += 1
                dwell[event.y][event.x] += block_move_sec if event.action == Action.MOVE else event.duration
            if event.action == Action.MOVE:
                path_tiles += 1
            if event.action not in (Action.BROWSE, Action.BUY) or not event.target_rack:
                continue
            visitors_set, browsers_set, buyers_set = rack_people.setdefault(event.target_rack, (set(), set(), set()))
            rs = racks.setdefault(event.target_rack, RackStats(
                rack_id=event.target_rack, rack_name=rack_names.get(event.target_rack, ""),
            ))
            visitors_set.add(cr.persona_id)
            if event.action == Action.BROWSE:
                browsers_set.add(cr.persona_id)
                continue
            line = event.price * event.quantity
            is_impulse = event.origin == "impulse"
            bought_any = True
            buyers_set.add(cr.persona_id)
            rs.units += event.quantity
            rs.revenue += line
            units += event.quantity
            revenue += line
            if is_impulse:
                rs.impulse_units += event.quantity
                impulse_units += event.quantity
                impulse_revenue += line
            if event.product_sku:
                ps = products.setdefault(event.product_sku, ProductStats(sku=event.product_sku, name=event.product_name))
                ps.units += event.quantity
                ps.revenue += line
                if is_impulse:
                    ps.impulse_units += event.quantity
                product_buyers.setdefault(event.product_sku, set()).add(cr.persona_id)
            product_revenue[event.product_name] += line
            product_units[event.product_name] += event.quantity
        if bought_any:
            buyers += 1

    for rack_id, (visitors_set, browsers_set, buyers_set) in rack_people.items():
        racks[rack_id].visitors = len(visitors_set)
        racks[rack_id].browsers = len(browsers_set)
        racks[rack_id].buyers = len(buyers_set)
    for sku, people in product_buyers.items():
        products[sku].buyers = len(people)

    visitors = len(results)
    summary = SimulationSummary(
        store_id=store.id,
        currency=summary_currency_label(currency),
        total_customers=visitors,
        total_revenue=revenue,
        top_products=[name for name, _ in product_revenue.most_common(10)],
        buyers=buyers,
        conversion_rate=_ratio(buyers, visitors),
        units_sold=units,
        avg_units_per_buyer=_ratio(units, buyers),
        avg_basket_value=_ratio(revenue, buyers),
        revenue_per_visitor=_ratio(revenue, visitors),
        impulse_revenue_share=_ratio(impulse_revenue, revenue),
        impulse_unit_share=_ratio(impulse_units, units),
        avg_visit_sec=_ratio(visit_sec, visitors),
        avg_path_tiles=_ratio(path_tiles, visitors),
        top_products_by_units=[name for name, _ in product_units.most_common(10)],
        products=sorted(products.values(), key=lambda p: (-p.revenue, p.sku)),
        racks=sorted(racks.values(), key=lambda r: (-r.revenue, r.rack_id)),
        segments=_segments(results, persona_map),
        hourly_visitors=dict(sorted(hourly.items())),
    )
    legacy = _legacy_counts(results, persona_map)
    summary.by_purpose, summary.by_identity, summary.by_age, summary.by_gender = legacy

    violations: Counter[str] = Counter(v.kind for v in check_buy_consistency(store, results))
    diagnostics = RunDiagnostics(
        requested_customers=visitors,
        succeeded_customers=visitors,
        dropped_invalid_buys=sum(cr.dropped_invalid_buys for cr in results),
        dropped_over_budget=sum(cr.dropped_over_budget for cr in results),
        buy_violations=dict(violations),
    )

    return AggregatedResult(
        summary=summary,
        pathcalc_heatmap=pathcalc_heatmap,
        persona_heatmap=behavioral,
        dwell_heatmap=dwell,
        diagnostics=diagnostics,
    )


def _ratio(num: float, den: float) -> float:
    return round(num / den, 6) if den else 0.0


def _segments(
    results: list[CustomerResult], persona_map: dict[str, Persona],
) -> dict[str, dict[str, SegmentStats]]:
    out: dict[str, dict[str, SegmentStats]] = {d: {} for d in _SEGMENT_DIMENSIONS}
    for cr in results:
        p = persona_map.get(cr.persona_id)
        if p is None:
            continue
        values = {"age_group": p.age_group, "gender": p.gender, "purpose": p.purpose, "identity": p.identity}
        for dim, value in values.items():
            s = out[dim].setdefault(value, SegmentStats())
            s.visitors += 1
            s.revenue += cr.total_spent
            s.units += cr.units_bought
            if cr.purchases:
                s.buyers += 1
    for by_value in out.values():
        for s in by_value.values():
            s.conversion_rate = _ratio(s.buyers, s.visitors)
            s.revenue_per_visitor = _ratio(s.revenue, s.visitors)
    return out


def _legacy_counts(
    results: list[CustomerResult], persona_map: dict[str, Persona],
) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    by_purpose: Counter[str] = Counter()
    by_identity: Counter[str] = Counter()
    by_age: Counter[str] = Counter()
    by_gender: Counter[str] = Counter()
    for cr in results:
        p = persona_map.get(cr.persona_id)
        if not p:
            continue
        by_purpose[p.purpose] += 1
        by_identity[p.identity] += 1
        by_age[p.age_group] += 1
        by_gender[p.gender] += 1
    return dict(by_purpose), dict(by_identity), dict(by_age), dict(by_gender)
