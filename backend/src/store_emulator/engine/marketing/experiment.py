"""Paired A/B experiments on the twin: the same shoppers in the control and every variant.

The evaluator runs one fixed persona panel with one seed (common random numbers), so the difference a
shopper shows between control and variant comes from the change, not from different people or dice.
Store-level outcomes use `compare_runs`; focus-product outcomes (units, spend, buyers per visitor)
use the same paired percentile bootstrap over shoppers.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Literal

import math

import numpy as np

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.marketing import (
    FocusOutcome,
    PricePoint,
    PriceResponse,
    SegmentLift,
    SkuSales,
    VariantChange,
    VariantResult,
)
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
    rng = np.random.default_rng(abs(seed))
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


def _price_only(sku: str, changes: Sequence[VariantChange]) -> bool:
    """Whether an arm changes `sku` by its price alone: a price or discount change on it, and no sign, move, package
    or category price change touching it (a category change may cover it, so it always counts as touching)."""
    touching = [c for c in changes if c.kind == "category_price" or c.sku == sku]
    return any(c.kind in ("price", "discount") for c in touching) and all(c.kind in ("price", "discount") for c in touching)


def price_response(
    control: VariantResult, variants: list[VariantResult], changes: Mapping[str, Sequence[VariantChange]],
) -> PriceResponse | None:
    """Demand curve of the first tracked product whose price takes three or more values across the control and the
    arms that change only its price (`changes` maps arm names to their changes). An arm that also hangs a sign on it,
    moves it or changes a whole category's prices would put that effect on the curve as if it were the price's."""
    for sku in control.prices:
        arms = [v for v in variants if _price_only(sku, changes.get(v.name, ()))]
        prices = {control.prices[sku], *(v.prices.get(sku, control.prices[sku]) for v in arms)}
        if len(prices) < 3:
            continue
        units = [f for v in arms for f in v.focus if f.sku == sku and f.metric == "units"]
        spend = [f for v in arms for f in v.focus if f.sku == sku and f.metric == "spend"]
        if not units:
            continue
        base_units, base_spend = units[0].control, (spend[0].control if spend else 0.0)
        points = [PricePoint(arm=control.name, price=control.prices[sku], units=base_units, units_low=base_units,
                             units_high=base_units, revenue=base_spend)]
        for v in arms:
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
    rng = np.random.default_rng(abs(seed))
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
    waits = [r.queue_wait_sec for r in results if r.queue_wait_sec or r.purchases or r.left_queue]
    return VariantResult(
        name=name,
        customers=len(results),
        revenue_per_visitor=round(sum(r.total_spent for r in results) / n, 4),
        conversion=round(sum(1 for r in results if r.purchases) / n, 4),
        units_per_visitor=round(sum(r.units_bought for r in results) / n, 4),
        lost_units=sum(r.lost_units for r in results),
        left_line=sum(1 for r in results if r.left_queue),
        avg_wait_sec=round(sum(waits) / len(waits), 1) if waits else 0.0,
    )


async def run_experiment(
    evaluator: LayoutEvaluator,
    control: Store,
    variants: list[tuple[str, Store, list[str], list[str]]],
    panel: list[Persona],
    focus_skus: list[str],
    *,
    on_progress: Callable[[float, str], None] | None = None,
    on_outcomes: Callable[[list[CustomerResult], list[list[CustomerResult]]], None] | None = None,
    on_arm: Callable[[str], None] | None = None,
    seed: int = 0,
) -> tuple[VariantResult, list[VariantResult], str]:
    """Control and variant results on one panel, and the winner (best revenue per visitor with a CI above
    zero, "" when none). `variants` holds (name, store, applied changes, warnings). `on_arm` is called with each
    arm's name right after its shoppers ran (while the evaluator's engine metadata describes that arm); an
    exception it raises ends the experiment."""
    total = len(variants) + 1
    if on_progress:
        on_progress(0.0, "control")
    base = await evaluator.evaluate_customers(control, panel)
    if on_arm:
        on_arm("Control")
    common_ids = {p.id for p in panel} & {r.persona_id for r in base}
    if not common_ids:
        raise ValueError("Control produced no successful shopper results for the requested panel; the experiment cannot be compared.")
    runs: list[list[CustomerResult]] = []
    for k, (name, store, _, _) in enumerate(variants, start=1):
        if on_progress:
            on_progress(k / total, name)
        res = await evaluator.evaluate_customers(store, panel)
        if on_arm:
            on_arm(name)
        common_ids.intersection_update(r.persona_id for r in res)
        if not common_ids:
            raise ValueError(f"No common successful shoppers remain across Control and the variants through '{name}'; the experiment cannot be compared.")
        runs.append(res)

    if on_outcomes:
        on_outcomes(base, runs)

    # Every arm must describe the same shoppers, including headline scores and the price curve.
    base = [r for r in base if r.persona_id in common_ids]
    comparison_notes: list[str] = []
    if len(common_ids) < len(panel):
        comparison_notes.append(
            f"Only {len(common_ids)} of {len(panel)} requested shoppers succeeded in every arm. "
            "All summaries and comparisons use this common cohort; excluded shoppers may bias the result."
        )
    if len(common_ids) < 30:
        comparison_notes.append("Fewer than 30 paired customers: intervals are unreliable.")
    names = {e.product_sku: e.product_name for r in base for e in r.purchases}
    for rack in control.racks:
        for slot in rack.slots:
            for item in slot.items:
                names.setdefault(item.sku, item.name)
    control_result = _summary("Control", base)
    control_result.warnings = list(comparison_notes)
    control_result.top_skus = sku_sales(base, keep=focus_skus)
    control_result.prices = _prices(control, focus_skus)
    results: list[VariantResult] = []
    for (name, store, applied, warnings), outcomes in zip(variants, runs, strict=True):
        res = [r for r in outcomes if r.persona_id in common_ids]
        out = _summary(name, res)
        out.applied, out.warnings = applied, [*warnings, *comparison_notes]
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
