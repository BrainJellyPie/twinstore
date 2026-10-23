"""Simulation-vs-reality fidelity metrics against point-of-sale (POS) data.

Answers "does the simulated store sell like the real one?" with the metrics used
in the README accuracy chart (Spearman, JS similarity, NDCG) plus basket-level
distribution checks that catch the common failure modes of LLM shoppers:
over-buying, too-uniform baskets (variance compression) and wrong time profiles.
"""

import math
from collections import Counter
from datetime import time

import numpy as np
from pydantic import BaseModel, Field

from store_emulator.domain.analysis import FidelityMetric, FidelityReport
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action


class PosLine(BaseModel):
    """One line of a real receipt."""
    transaction_id: str
    # Receipt numbers can restart on another date/store/register. Keep the original ID as a label.
    transaction_scope: tuple[tuple[str, str], ...] = ()
    sku: str
    quantity: float = Field(default=1.0, allow_inf_nan=False)
    unit_price: float = Field(default=0.0, allow_inf_nan=False)  # minor currency unit, same as the store's prices
    hour: int | None = None  # 0–23 when the POS export carries a timestamp


def fidelity_report(
    store: Store,
    results: list[CustomerResult],
    pos: list[PosLine],
    *,
    top_k: int = 10,
) -> FidelityReport:
    store_skus = {i.sku for r in store.racks for s in r.slots for i in s.items}
    sku_groups: dict[str, set[str]] = {}
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                sku_groups.setdefault(item.sku, set()).add(rack.rack_name or rack.id)
    sku_rack = {sku: next(iter(groups)) for sku, groups in sku_groups.items() if len(groups) == 1}
    real_lines = [line for line in pos if line.sku in store_skus]
    notes: list[str] = []
    dropped = len(pos) - len(real_lines)
    if dropped:
        notes.append(f"{dropped} POS lines reference SKUs not on the simulated shelves and were ignored.")

    sim_units: dict[str, float] = {}
    for cr in results:
        for e in cr.purchases:
            sim_units[e.product_sku] = sim_units.get(e.product_sku, 0.0) + e.quantity
    real_units: dict[str, float] = {}
    for line in real_lines:  # POS quantities may be fractional (weighed goods)
        real_units[line.sku] = real_units.get(line.sku, 0.0) + line.quantity

    skus = sorted(store_skus)
    s_vec = np.array([sim_units.get(k, 0) for k in skus], dtype=float)
    r_vec = np.array([real_units.get(k, 0) for k in skus], dtype=float)
    if (r_vec < 0).any():
        notes.append(
            "Some products have negative net POS units (returns exceed sales). SKU share similarity "
            "and NDCG are undefined; rack share similarity is also undefined where rack net units are negative."
        )

    ambiguous = [sku for sku, groups in sku_groups.items()
                 if len(groups) > 1 and (sim_units.get(sku, 0) != 0 or real_units.get(sku, 0) != 0)]
    if ambiguous:
        notes.append(f"Rack metrics are unavailable: {len(ambiguous)} sold SKUs appear in multiple rack/category groups, "
                     "and POS receipts do not identify the selling shelf.")
    racks = sorted({group for groups in sku_groups.values() for group in groups})
    s_rack = np.array([sum(sim_units.get(k, 0) for k in skus if sku_rack.get(k) == g) for g in racks], dtype=float)
    r_rack = np.array([sum(real_units.get(k, 0) for k in skus if sku_rack.get(k) == g) for g in racks], dtype=float)

    sim_baskets = [float(cr.units_bought) for cr in results if cr.purchases]
    sim_values = [float(cr.total_spent) for cr in results if cr.purchases]
    real_tx: dict[tuple[str, tuple[tuple[str, str], ...]], list[PosLine]] = {}
    for line in real_lines:
        real_tx.setdefault((line.transaction_id, line.transaction_scope), []).append(line)
    real_baskets = [sum(line.quantity for line in lines) for lines in real_tx.values()]
    real_values = [sum(line.quantity * line.unit_price for line in lines) for lines in real_tx.values()]

    sku_rank = spearman(s_vec, r_vec)
    rack_rank = math.nan if ambiguous else spearman(s_rack, r_rack)
    if math.isnan(sku_rank):
        notes.append("SKU rank correlation is unavailable: it needs at least two products and varying sales totals in both datasets.")
    if not ambiguous and math.isnan(rack_rank):
        notes.append("Rack rank correlation is unavailable: it needs at least two rack/category groups and varying sales totals in both datasets.")

    metrics = [
        FidelityMetric(name="sku_spearman", value=_round(sku_rank), better="higher",
                       description="Rank correlation of units sold per SKU"),
        FidelityMetric(name="sku_js_similarity", value=_round(1.0 - js_divergence(s_vec, r_vec)), better="higher",
                       description="1 − Jensen–Shannon divergence (base 2) of SKU unit shares"),
        FidelityMetric(name=f"sku_ndcg@{top_k}", value=_round(ndcg(s_vec, r_vec, top_k)), better="higher",
                       description="Does the simulated top-K match the real best sellers?"),
        FidelityMetric(name="sku_ndcg@all", value=_round(ndcg(s_vec, r_vec, len(skus))), better="higher",
                       description="NDCG over every SKU on the shelves"),
        FidelityMetric(name="rack_spearman", value=_round(rack_rank), better="higher",
                       description="Rank correlation of units per rack (category proxy)"),
        FidelityMetric(name="rack_js_similarity", value=None if ambiguous else _round(1.0 - js_divergence(s_rack, r_rack)), better="higher",
                       description="1 − JSD of rack unit shares"),
        FidelityMetric(name="basket_units_w1", value=_round(wasserstein_1d(sim_baskets, real_baskets)), better="lower",
                       description="Wasserstein-1 distance of units per paying basket"),
        FidelityMetric(name="basket_units_mean_ratio", value=_round(_mean_ratio(sim_baskets, real_baskets)), better="closer to 1",
                       description="Simulated / real mean units per basket"),
        FidelityMetric(name="basket_units_var_ratio", value=_round(_var_ratio(sim_baskets, real_baskets)), better="closer to 1",
                       description="Simulated / real variance — below 1 means variance compression"),
        FidelityMetric(name="basket_value_w1", value=_round(wasserstein_1d(sim_values, real_values)), better="lower",
                       description="Wasserstein-1 distance of basket value (minor currency unit)"),
        FidelityMetric(name="basket_value_mean_ratio", value=_round(_mean_ratio(sim_values, real_values)), better="closer to 1",
                       description="Simulated / real mean basket value"),
    ]

    real_hours: Counter[int] = Counter()
    for lines in real_tx.values():
        hour = min((line.hour for line in lines if line.hour is not None), default=None)
        if hour is not None:
            real_hours[hour] += 1
    if real_hours:
        transaction_hours = [_transaction_hour(cr) for cr in results if cr.purchases]
        sim_hours = Counter(hour for hour in transaction_hours if hour is not None)
        missing = sum(hour is None for hour in transaction_hours)
        if missing:
            notes.append(f"{missing} simulated buying visits have no usable recorded checkout time and were excluded from hourly scoring.")
        hours = list(range(24))
        metrics.append(FidelityMetric(
            name="hourly_js_similarity",
            value=None if missing and not sim_hours else _round(1.0 - js_divergence(
                np.array([sim_hours.get(h, 0) for h in hours], dtype=float),
                np.array([real_hours.get(h, 0) for h in hours], dtype=float),
            )),
            better="higher",
            description="1 − JSD of paying-transaction share per hour, using simulated checkout completion",
        ))
    else:
        notes.append("POS has no hour information; hourly profile not evaluated.")

    return FidelityReport(
        sim_customers=len(results),
        real_transactions=len(real_tx),
        matched_skus=int(((s_vec > 0) | (r_vec > 0)).sum()),
        metrics=metrics,
        notes=notes,
    )


def _transaction_hour(customer: CustomerResult) -> int | None:
    completed = max((event.elapsed_sec + event.duration for event in customer.timeline
                     if event.action == Action.PAY and event.elapsed_sec >= 0 and event.duration >= 0), default=None)
    if completed is None:
        return None
    try:
        arrival = time.fromisoformat(customer.arrival_time)
    except ValueError:
        return None
    if arrival.tzinfo is not None:
        return None
    seconds = arrival.hour * 3600 + arrival.minute * 60 + arrival.second + completed
    return seconds // 3600 % 24


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen–Shannon divergence in bits (0 = identical, 1 = disjoint); undefined for negative counts."""
    if (p < 0).any() or (q < 0).any():
        return math.nan
    if p.sum() == 0 or q.sum() == 0:
        return 1.0
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    def kl(x: np.ndarray, y: np.ndarray) -> float:
        mask = x > 0
        return float((x[mask] * np.log2(x[mask] / y[mask])).sum())

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Rank correlation, undefined when either side has no variation in ranks."""
    if len(x) < 2:
        return math.nan
    rx, ry = _rank(x), _rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return math.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def ndcg(predicted: np.ndarray, relevance: np.ndarray, k: int) -> float:
    """NDCG@k with tied predictions averaged over their possible orders."""
    if (relevance < 0).any():
        return math.nan
    if relevance.sum() == 0 or k <= 0:
        return 0.0
    order = np.argsort(-predicted, kind="stable")
    scores = predicted[order]
    starts = np.r_[0, np.flatnonzero(scores[1:] != scores[:-1]) + 1]
    counts = np.diff(np.r_[starts, len(order)])
    # Include every member of a tie crossing k; each can occupy any of its discounted positions.
    gains = np.add.reduceat(relevance[order].astype(float), starts) / counts
    cutoff = min(k, len(order))
    discounts = np.zeros(len(order))
    discounts[:cutoff] = 1.0 / np.log2(np.arange(2, cutoff + 2))
    dcg = float((gains * np.add.reduceat(discounts, starts)).sum())
    idcg = float((np.sort(relevance)[::-1] * discounts).sum())
    return dcg / idcg if idcg else 0.0


def wasserstein_1d(a: list[float], b: list[float]) -> float:
    """W1 between two empirical 1-D distributions (exact, via merged quantile functions)."""
    if not a or not b:
        return math.nan
    xa, xb = np.sort(np.array(a, dtype=float)), np.sort(np.array(b, dtype=float))
    grid = np.union1d(np.linspace(0, 1, len(xa) + 1), np.linspace(0, 1, len(xb) + 1))
    mids = (grid[:-1] + grid[1:]) / 2
    widths = np.diff(grid)
    qa = xa[np.minimum((mids * len(xa)).astype(int), len(xa) - 1)]
    qb = xb[np.minimum((mids * len(xb)).astype(int), len(xb) - 1)]
    return float((np.abs(qa - qb) * widths).sum())


def _rank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x), dtype=float)
    ranks[order] = np.arange(len(x), dtype=float)
    for value in np.unique(x):  # average ranks for ties
        mask = x == value
        ranks[mask] = ranks[mask].mean()
    return ranks


def _mean_ratio(sim: list[float], real: list[float]) -> float:
    if not sim or not real or sum(real) == 0:
        return math.nan
    return (sum(sim) / len(sim)) / (sum(real) / len(real))


def _var_ratio(sim: list[float], real: list[float]) -> float:
    if len(sim) < 2 or len(real) < 2:
        return math.nan
    vr = float(np.var(real, ddof=1))
    return float(np.var(sim, ddof=1)) / vr if vr else math.nan


def _round(v: float) -> float | None:
    return None if math.isnan(v) else round(v, 6)
