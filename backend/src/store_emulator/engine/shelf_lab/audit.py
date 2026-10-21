"""Planogram compliance: a field photo of a rack face against the layout's reference face.

The photo's products are first matched to the store's SKUs (by name, as when a capture is applied),
then compared level by level with the reference: products missing (out of stock or delisted),
products that should not be there, products on the wrong level or out of order, facing counts,
tag prices that differ from the reference price, and empty stretches. Compliance is the share of
reference facings found on their level.

The findings are then priced with paired simulations on one shopper panel (common random numbers):
the reference face against the face as photographed gives the revenue effect of the whole
deviation; the reference against the reference minus one missing product gives what that one
stock-out costs per day.
"""

from collections import Counter
from dataclasses import dataclass

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.capture import Box, CaptureGap, CaptureItem, CaptureResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import RACK_LEVELS, Rack
from store_emulator.domain.shelf_lab import AuditFinding, LevelCompliance
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.capture.planogram import (
    PlacementReport,
    match_store_skus,
    replace_rack_face,
)
from store_emulator.engine.optimize.evaluate import LayoutEvaluator
from store_emulator.engine.perception.shelf_render import face_slots
from store_emulator.engine.prompting import display_price


@dataclass(frozen=True)
class Run:
    """Consecutive facings of one product on one level."""
    sku: str
    name: str
    price: int
    facings: int


def reference_rows(rack: Rack, face: Face) -> dict[int, list[Run]]:
    rows: dict[int, list[Run]] = {}
    for level, row in zip(range(RACK_LEVELS, 0, -1), face_slots(rack, face), strict=True):
        runs: list[Run] = []
        for _, item in row:
            if runs and runs[-1].sku == item.sku:
                last = runs[-1]
                runs[-1] = Run(last.sku, last.name, last.price, last.facings + 1)
            else:
                runs.append(Run(item.sku, item.name, item.price, 1))
        rows[level] = runs
    return rows


def field_rows(result: CaptureResult) -> dict[int, list[CaptureItem]]:
    rows: dict[int, list[CaptureItem]] = {lv: [] for lv in range(1, RACK_LEVELS + 1)}
    for item in sorted(result.items, key=lambda i: (i.level, i.boxes[0].x1 if i.boxes else i.order)):
        rows.setdefault(item.level, []).append(item)
    return rows


def _union(boxes: list[Box]) -> Box | None:
    if not boxes:
        return None
    return Box(x1=min(b.x1 for b in boxes), y1=min(b.y1 for b in boxes), x2=max(b.x2 for b in boxes), y2=max(b.y2 for b in boxes))


def _nearest_gap(gaps: list[CaptureGap], fraction: float, items: list[CaptureItem]) -> CaptureGap | None:
    """The empty stretch of a level closest to where a product was expected (as a share of the level's width)."""
    if not gaps:
        return None
    xs = [b.x1 for i in items for b in i.boxes] + [b.x2 for i in items for b in i.boxes] + [g.box.x1 for g in gaps] + [g.box.x2 for g in gaps]
    lo, hi = min(xs), max(xs)
    target = lo + fraction * (hi - lo)
    return min(gaps, key=lambda g: abs(g.box.cx - target))


def diff_face(rack: Rack, face: Face, field: CaptureResult, currency: str) -> tuple[list[LevelCompliance], list[AuditFinding]]:
    """Level-by-level comparison of the reference face with the (store-matched) field planogram."""
    ref = reference_rows(rack, face)
    got = field_rows(field)
    ref_level_of: dict[str, set[int]] = {}
    got_level_of: dict[str, set[int]] = {}
    for lv, runs in ref.items():
        for r in runs:
            ref_level_of.setdefault(r.sku, set()).add(lv)
    for lv, items in got.items():
        for it in items:
            got_level_of.setdefault(it.sku, set()).add(lv)

    levels: list[LevelCompliance] = []
    findings: list[AuditFinding] = []
    used_gaps: set[int] = set()
    for lv in range(RACK_LEVELS, 0, -1):
        runs, items = ref.get(lv, []), got.get(lv, [])
        if not runs and not items:
            continue
        ref_count: Counter[str] = Counter()
        for r in runs:
            ref_count[r.sku] += r.facings
        got_count: Counter[str] = Counter()
        for it in items:
            got_count[it.sku] += it.facings
        matched = sum(min(n, got_count[sku]) for sku, n in ref_count.items())
        expected = sum(ref_count.values())
        levels.append(LevelCompliance(level=lv, expected_facings=expected, found_facings=sum(got_count.values()),
                                      matched_facings=matched, score=round(matched / expected, 4) if expected else 1.0))
        names = {r.sku: r for r in runs}
        for pos, r in enumerate(runs):
            if r.sku in got_count:
                continue
            elsewhere = sorted(got_level_of.get(r.sku, set()) - {lv})
            if elsewhere:
                where = [it for it in field.items if it.sku == r.sku]
                findings.append(AuditFinding(kind="misplaced", level=lv, sku=r.sku, name=r.name, expected=f"level {lv}",
                                             found=f"level {elsewhere[0]}", box=_union([b for it in where for b in it.boxes])))
                continue
            gap = _nearest_gap([g for k, g in enumerate(field.gaps) if g.level == lv and k not in used_gaps],
                               (pos + 0.5) / max(1, len(runs)), items)
            if gap is not None:
                used_gaps.add(field.gaps.index(gap))
            findings.append(AuditFinding(kind="missing", level=lv, sku=r.sku, name=r.name,
                                         expected=f"{r.facings} facing{'s' if r.facings > 1 else ''}", found="none",
                                         box=gap.box if gap is not None else None))
        for it in items:
            if it.sku in ref_count:
                continue
            if lv not in ref_level_of.get(it.sku, set()) and ref_level_of.get(it.sku):
                continue  # reported as misplaced from its reference level
            findings.append(AuditFinding(kind="unexpected", level=lv, sku=it.sku, name=it.name, expected="not on this level",
                                         found=f"{it.facings} facing{'s' if it.facings > 1 else ''}", box=_union(it.boxes)))
        common_ref = [r.sku for r in runs if r.sku in got_count]
        common_got = list(dict.fromkeys(it.sku for it in items if it.sku in ref_count))
        for sku in common_ref:
            n_ref, n_got = ref_count[sku], got_count[sku]
            where = [it for it in items if it.sku == sku]
            box = _union([b for it in where for b in it.boxes])
            if n_ref != n_got:
                findings.append(AuditFinding(kind="facings", level=lv, sku=sku, name=names[sku].name,
                                             expected=str(n_ref), found=str(n_got), box=box))
            if common_ref.index(sku) != common_got.index(sku):
                findings.append(AuditFinding(kind="misplaced", level=lv, sku=sku, name=names[sku].name,
                                             expected=f"position {common_ref.index(sku) + 1}",
                                             found=f"position {common_got.index(sku) + 1}", box=box))
            tagged = [it for it in where if it.price is not None and not it.price_estimated]
            ref_price = names[sku].price
            if tagged and ref_price > 0:
                p = tagged[0].price or 0
                if abs(p - ref_price) > max(1, round(0.02 * ref_price)):
                    findings.append(AuditFinding(kind="price", level=lv, sku=sku, name=names[sku].name,
                                                 expected=display_price(ref_price, currency), found=display_price(p, currency), box=box))
        for k, g in enumerate(field.gaps):
            if g.level == lv and k not in used_gaps:
                findings.append(AuditFinding(kind="gap", level=lv, expected="stocked", found=f"{g.facings:g} facing(s) empty", box=g.box))
    return levels, findings


def match_field(store: Store, field: CaptureResult) -> CaptureResult:
    """The capture with products the store already sells carrying the store's SKUs."""
    return match_store_skus(store, field, PlacementReport())


def without_sku(store: Store, rack_id: str, face: Face, sku: str) -> Store:
    """Copy of `store` with `sku` taken off one rack face (its slots keep their other products)."""
    new = store.model_copy(deep=True)
    rack = next(r for r in new.racks if r.id == rack_id)
    for slot in rack.slots:
        if slot.face == face:
            slot.items = [i for i in slot.items if i.sku != sku]
    return new


@dataclass
class Impact:
    whole: MetricComparison | None
    losses: dict[str, tuple[float, float, float]]   # sku → (loss per day, CI low, CI high)


def _spend(report_metrics: list[MetricComparison]) -> MetricComparison | None:
    return next((m for m in report_metrics if m.metric == "spend"), None)


async def price_findings(
    evaluator: LayoutEvaluator,
    store: Store,
    field: CaptureResult,
    rack_id: str,
    face: Face,
    panel: list[Persona],
    *,
    missing: list[str],
    visitors_per_day: float,
    max_stockouts: int = 8,
) -> tuple[Impact, Store]:
    """Paired simulations: reference vs as photographed, and reference vs each stock-out."""
    as_photographed, _ = replace_rack_face(store, field, rack_id, face)
    base = await evaluator.evaluate_customers(store, panel)
    seen = await evaluator.evaluate_customers(as_photographed, panel)
    whole = _spend(compare_runs(base, seen, run_a="reference", run_b="photo").metrics)
    losses: dict[str, tuple[float, float, float]] = {}
    for sku in missing[:max_stockouts]:
        out = await evaluator.evaluate_customers(without_sku(store, rack_id, face, sku), panel)
        m = _spend(compare_runs(base, out, run_a="reference", run_b=f"no {sku}").metrics)
        if m is not None:
            losses[sku] = (round(-m.diff * visitors_per_day, 1), round(-m.ci_high * visitors_per_day, 1), round(-m.ci_low * visitors_per_day, 1))
    return Impact(whole=whole, losses=losses), as_photographed
