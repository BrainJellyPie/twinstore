"""Paired A/B experiments on the twin: the same shoppers in the control and every variant.

The evaluator runs one fixed persona panel with one seed (common random numbers), so the difference a
shopper shows between control and variant comes from the change, not from different people or dice.
Store-level outcomes use `compare_runs`; focus-product outcomes (units, spend, buyers per visitor)
use the same paired percentile bootstrap over shoppers.
"""

from collections.abc import Callable
from typing import Literal

import math

import numpy as np

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.marketing import FocusOutcome, PricePoint, PriceResponse, SegmentLift, SkuSales, VariantResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.optimize.evaluate import LayoutEvaluator

FOCUS_METRICS = ("units", "spend", "buyers")


def _focus_values(result: CustomerResult, skus: set[str]) -> dict[str, float]:
    lines = [e for e in result.purchases if e.product_sku in skus]
    return {
        "units": float(sum(e.quantity for e in lines)),
        "spend": float(sum(e.price * e.quantity for e in lines)),
        "buyers": 1.0 if lines else 0.0,
    }


def focus_outcomes(
    control: list[CustomerResult],
    variant: list[CustomerResult],
    skus: list[str],
    names: dict[str, str],
    *,
    n_bootstrap: int = 2000,
    seed: int = 0,
) -> list[FocusOutcome]:
    """Paired per-visitor outcomes of each focus product and of all of them together ("*")."""
    a = {r.persona_id: r for r in control}
    b = {r.persona_id: r for r in variant}
    ids = sorted(set(a) & set(b))
    if not ids or not skus:
        return []
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(n_bootstrap, len(ids)))
    groups = [(sku, names.get(sku, sku), {sku}) for sku in skus]
    if len(skus) > 1:
        groups.append(("*", "all focus products", set(skus)))
    out: list[FocusOutcome] = []
    for sku, name, group in groups:
        va = [_focus_values(a[i], group) for i in ids]
        vb = [_focus_values(b[i], group) for i in ids]
        for metric in FOCUS_METRICS:
            xa = np.array([v[metric] for v in va])
            xb = np.array([v[metric] for v in vb])
            d = xb - xa
            boot = d[idx].mean(axis=1)
            ma, mb = float(xa.mean()), float(xb.mean())
            out.append(FocusOutcome(
                sku=sku, name=name, metric=metric, control=round(ma, 6), variant=round(mb, 6), diff=round(mb - ma, 6),
                rel_diff=round((mb - ma) / ma, 6) if ma else 0.0,
                ci_low=round(float(np.percentile(boot, 2.5)), 6), ci_high=round(float(np.percentile(boot, 97.5)), 6),
                prob_better=round(float((boot > 0).mean()), 4),
            ))
    return out


def sku_sales(results: list[CustomerResult], *, keep: list[str] | None = None, top: int = 8) -> list[SkuSales]:
    """Products by revenue (the `keep` SKUs always included)."""
    units: dict[str, int] = {}
    revenue: dict[str, int] = {}
    buyers: dict[str, set[str]] = {}
    names: dict[str, str] = {}
    for r in results:
        for e in r.purchases:
            units[e.product_sku] = units.get(e.product_sku, 0) + e.quantity
            revenue[e.product_sku] = revenue.get(e.product_sku, 0) + e.price * e.quantity
            buyers.setdefault(e.product_sku, set()).add(r.persona_id)
            names.setdefault(e.product_sku, e.product_name)
    ranked = sorted(revenue, key=lambda s: -revenue[s])[:top]
    for sku in keep or []:
        if sku not in ranked:
            ranked.append(sku)
    return [SkuSales(sku=s, name=names.get(s, s), units=units.get(s, 0), revenue=revenue.get(s, 0), buyers=len(buyers.get(s, set())))
            for s in ranked]


def _prices(store: Store, skus: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                if item.sku in skus:
                    out[item.sku] = min(out.get(item.sku, item.price), item.price)
    return out


def price_response(control: VariantResult, variants: list[VariantResult]) -> PriceResponse | None:
    """Demand curve of the first tracked product whose price takes three or more values across the arms."""
    for sku in control.prices:
        prices = {control.prices[sku], *(v.prices.get(sku, control.prices[sku]) for v in variants)}
        if len(prices) < 3:
            continue
        units = [f for v in variants for f in v.focus if f.sku == sku and f.metric == "units"]
        spend = [f for v in variants for f in v.focus if f.sku == sku and f.metric == "spend"]
        if not units:
            continue
        base_units, base_spend = units[0].control, (spend[0].control if spend else 0.0)
        points = [PricePoint(arm=control.name, price=control.prices[sku], units=base_units, units_low=base_units,
                             units_high=base_units, revenue=base_spend)]
        for v in variants:
            u = next((f for f in v.focus if f.sku == sku and f.metric == "units"), None)
            m = next((f for f in v.focus if f.sku == sku and f.metric == "spend"), None)
            if u is None:
                continue
            points.append(PricePoint(arm=v.name, price=v.prices.get(sku, control.prices[sku]), units=u.variant,
                                     units_low=max(0.0, base_units + u.ci_low), units_high=base_units + u.ci_high,
                                     revenue=m.variant if m else 0.0))
        points.sort(key=lambda p: p.price)
        logs = [(math.log(p.price), math.log(p.units)) for p in points if p.price > 0 and p.units > 0]
        elasticity = None
        if len({x for x, _ in logs}) >= 3:
            mx = sum(x for x, _ in logs) / len(logs)
            my = sum(y for _, y in logs) / len(logs)
            sxx = sum((x - mx) ** 2 for x, _ in logs)
            elasticity = round(sum((x - mx) * (y - my) for x, y in logs) / sxx, 3) if sxx else None
        best = max(points, key=lambda p: p.revenue)
        name = units[0].name
        return PriceResponse(sku=sku, name=name, points=points, elasticity=elasticity, best_price=best.price if best.revenue > 0 else None)
    return None


MIN_SEGMENT = 20


def segment_lifts(
    control: list[CustomerResult], variant: list[CustomerResult], panel: list[Persona], focus_skus: list[str],
    *, n_bootstrap: int = 1000, seed: int = 0,
) -> list[SegmentLift]:
    """Paired differences within each age group and gender of the panel (segments under 20 shoppers skipped)."""
    a = {r.persona_id: r for r in control}
    b = {r.persona_id: r for r in variant}
    groups: dict[str, list[str]] = {}
    for p in panel:
        if p.id in a and p.id in b:
            groups.setdefault(f"age {p.age_group}", []).append(p.id)
            groups.setdefault(f"gender {p.gender}", []).append(p.id)
    focus = set(focus_skus)
    metrics: list[tuple[Literal["spend", "focus_units"], Callable[[CustomerResult], float]]] = [("spend", lambda r: float(r.total_spent))]
    if focus:
        metrics.append(("focus_units", lambda r: float(sum(e.quantity for e in r.purchases if e.product_sku in focus))))
    rng = np.random.default_rng(seed)
    out: list[SegmentLift] = []
    for segment in sorted(groups):
        ids = groups[segment]
        if len(ids) < MIN_SEGMENT:
            continue
        idx = rng.integers(0, len(ids), size=(n_bootstrap, len(ids)))
        for metric, value in metrics:
            xa = np.array([value(a[i]) for i in ids])
            xb = np.array([value(b[i]) for i in ids])
            boot = (xb - xa)[idx].mean(axis=1)
            out.append(SegmentLift(segment=segment, n=len(ids), metric=metric, control=round(float(xa.mean()), 6),
                                   variant=round(float(xb.mean()), 6), diff=round(float(xb.mean() - xa.mean()), 6),
                                   ci_low=round(float(np.percentile(boot, 2.5)), 6), ci_high=round(float(np.percentile(boot, 97.5)), 6)))
    return out


def _summary(name: str, results: list[CustomerResult]) -> VariantResult:
    n = max(1, len(results))
    return VariantResult(
        name=name,
        revenue_per_visitor=round(sum(r.total_spent for r in results) / n, 4),
        conversion=round(sum(1 for r in results if r.purchases) / n, 4),
        units_per_visitor=round(sum(r.units_bought for r in results) / n, 4),
    )


async def run_experiment(
    evaluator: LayoutEvaluator,
    control: Store,
    variants: list[tuple[str, Store, list[str], list[str]]],
    panel: list[Persona],
    focus_skus: list[str],
    *,
    on_progress: Callable[[float, str], None] | None = None,
    seed: int = 0,
) -> tuple[VariantResult, list[VariantResult], str]:
    """Control and variant results on one panel, and the winner (best revenue per visitor with a CI above
    zero, "" when none). `variants` holds (name, store, applied changes, warnings)."""
    total = len(variants) + 1
    if on_progress:
        on_progress(0.0, "control")
    base = await evaluator.evaluate_customers(control, panel)
    names = {e.product_sku: e.product_name for r in base for e in r.purchases}
    for rack in control.racks:
        for slot in rack.slots:
            for item in slot.items:
                names.setdefault(item.sku, item.name)
    control_result = _summary("Control", base)
    control_result.top_skus = sku_sales(base, keep=focus_skus)
    control_result.prices = _prices(control, focus_skus)
    results: list[VariantResult] = []
    for k, (name, store, applied, warnings) in enumerate(variants, start=1):
        if on_progress:
            on_progress(k / total, name)
        res = await evaluator.evaluate_customers(store, panel)
        out = _summary(name, res)
        out.applied, out.warnings = applied, warnings
        out.prices = _prices(store, focus_skus)
        out.segments = segment_lifts(base, res, panel, focus_skus, seed=seed)
        out.vs_control = compare_runs(base, res, run_a="Control", run_b=name, seed=seed).metrics
        out.focus = focus_outcomes(base, res, focus_skus, names, seed=seed)
        out.top_skus = sku_sales(res, keep=focus_skus)
        results.append(out)
    winner, best = "", 0.0
    for r in results:
        spend = next((m for m in r.vs_control if m.metric == "spend"), None)
        if spend is not None and spend.ci_low > 0 and spend.diff > best:
            winner, best = r.name, spend.diff
    if on_progress:
        on_progress(1.0, "done")
    return control_result, results, winner
