"""What a run of online sessions shows: web-analytics style measures of one site variant, and paired differences
between variants shopped by the same people.

Paired intervals are bootstrap percentiles of the per-shopper differences (the same method as layout comparisons);
they describe these virtual shoppers, not real traffic.
"""

import csv
import io
from collections import Counter, defaultdict
from statistics import mean

import numpy as np

from store_emulator.domain.online import (
    FUNNEL_STAGES,
    ActionKind,
    ClickPoint,
    ExitRow,
    FunnelRow,
    OnlineShopper,
    OnlineSite,
    PageKind,
    PairedDelta,
    ProductRow,
    SearchTermRow,
    SegmentRow,
    SessionResult,
    VariantSummary,
)

_TOP_PRODUCTS = 20
_TOP_SEARCHES = 25
_MAX_CLICKS = 1500
_BOOTSTRAP = 2000


def _share(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def _steps(session: SessionResult) -> int:
    return sum(1 for step in session.steps if step.choice is not None)


def summarize(site: OnlineSite, shoppers: dict[str, OnlineShopper], sessions: list[SessionResult]) -> VariantSummary:
    n = len(sessions)
    bought = [s for s in sessions if s.outcome == "purchased"]
    revenue = sum(s.order_total for s in bought)
    added = [s for s in sessions if "add_to_cart" in s.reached]
    actions: Counter[str] = Counter()
    views: Counter[str] = Counter()
    adds: Counter[str] = Counter()
    clicks: list[ClickPoint] = []
    for session in sessions:
        for step in session.steps:
            choice = step.choice
            if choice is None:
                continue
            actions[choice.kind.value] += 1
            if choice.kind == ActionKind.OPEN_PRODUCT:
                views[choice.target] += 1
            if choice.kind in (ActionKind.ADD_TO_CART, ActionKind.BUY_NOW):
                adds[choice.target] += 1
            if choice.box is not None and step.screen is not None and len(clicks) < _MAX_CLICKS:
                w, h = step.screen
                x0, y0, x1, y1 = choice.box
                clicks.append(ClickPoint(page=step.page, kind=choice.kind, device="mobile" if w < 700 else "desktop",
                                         x=round((x0 + x1) / 2 / w, 4),
                                         y=round((y0 + y1) / 2 / h, 4)))
    units: Counter[str] = Counter()
    product_revenue: Counter[str] = Counter()
    buyers: Counter[str] = Counter()
    for session in bought:
        for line in session.order:
            units[line.product_id] += line.quantity
            product_revenue[line.product_id] += line.price * line.quantity
            buyers[line.product_id] += 1
    ranked = sorted(set(views) | set(adds) | set(units), key=lambda pid: (-units[pid], -views[pid], pid))[:_TOP_PRODUCTS]
    products = [ProductRow(product_id=pid, name=p.name if (p := site.product(pid)) else pid, views=views[pid],
                           adds=adds[pid], purchases=buyers[pid], units=units[pid], revenue=product_revenue[pid])
                for pid in ranked]
    terms: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for session in sessions:
        for record in session.searches:
            row = terms[record.query.strip().lower()]
            row[0] += 1
            row[1] += record.results == 0
        for query in {r.query.strip().lower() for r in session.searches}:
            terms[query][2] += session.outcome == "purchased"
    searches = [SearchTermRow(query=q, count=c, zero_results=z, purchases=p)
                for q, (c, z, p) in sorted(terms.items(), key=lambda kv: (-kv[1][0], kv[0]))[:_TOP_SEARCHES]]
    exits = Counter(s.exit_page for s in sessions if s.outcome != "purchased")
    segments: list[SegmentRow] = []
    for dimension in ("mission", "device", "age_group", "gender"):
        groups: dict[str, list[SessionResult]] = defaultdict(list)
        for session in sessions:
            shopper = shoppers.get(session.shopper_id)
            if shopper is not None:
                groups[str(getattr(shopper, dimension))].append(session)
        for value, group in sorted(groups.items()):
            segments.append(SegmentRow(
                dimension=dimension, value=value, sessions=len(group),
                conversion=_share(sum(s.outcome == "purchased" for s in group), len(group)),
                revenue_per_session=round(sum(s.order_total for s in group) / len(group), 2),
                avg_steps=round(mean(_steps(s) for s in group), 2),
            ))
    return VariantSummary(
        site_id=site.id, site_name=site.name, sessions=n, purchases=len(bought), conversion=_share(len(bought), n),
        revenue=revenue, aov=round(revenue / len(bought), 2) if bought else 0.0,
        revenue_per_session=round(revenue / n, 2) if n else 0.0,
        bounce_rate=_share(sum(s.outcome == "bounced" for s in sessions), n),
        cart_abandonment=_share(sum(s.outcome != "purchased" for s in added), len(added)),
        add_to_cart_rate=_share(len(added), n),
        avg_steps=round(mean(_steps(s) for s in sessions), 2) if sessions else 0.0,
        avg_seconds=round(mean(s.seconds for s in sessions), 1) if sessions else 0.0,
        search_share=_share(sum(bool(s.searches) for s in sessions), n),
        zero_result_searches=sum(r.results == 0 for s in sessions for r in s.searches),
        outcomes=dict(Counter(s.outcome for s in sessions)), actions=dict(actions),
        funnel=[FunnelRow(stage=stage, sessions=(k := sum(stage in s.reached for s in sessions)), share=_share(k, n))
                for stage in FUNNEL_STAGES],
        exits=[ExitRow(page=PageKind(page), sessions=count) for page, count in exits.most_common()],
        segments=segments, products=products, searches=searches, clicks=clicks,
    )


def _metric(session: SessionResult, metric: str) -> float:
    if metric == "conversion":
        return float(session.outcome == "purchased")
    if metric == "revenue_per_session":
        return float(session.order_total)
    if metric == "add_to_cart_rate":
        return float("add_to_cart" in session.reached)
    if metric == "steps":
        return float(_steps(session))
    return session.seconds


def paired_deltas(control: list[SessionResult], variant: list[SessionResult], *, seed: int = 0) -> list[PairedDelta]:
    """Variant minus control per shopper, for each measure, with a 95 % bootstrap interval of the mean difference."""
    a = {s.shopper_id: s for s in control}
    b = {s.shopper_id: s for s in variant}
    ids = sorted(set(a) & set(b))
    rng = np.random.default_rng(abs(seed))
    out: list[PairedDelta] = []
    metrics: tuple[str, ...] = ("conversion", "revenue_per_session", "add_to_cart_rate", "steps", "seconds")
    for metric in metrics:
        xa = np.array([_metric(a[i], metric) for i in ids], dtype=float)
        xb = np.array([_metric(b[i], metric) for i in ids], dtype=float)
        if not ids:
            continue
        d = xb - xa
        low = high = None
        if len(ids) > 1:
            boot = d[rng.integers(0, len(ids), size=(_BOOTSTRAP, len(ids)))].mean(axis=1)
            low, high = round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)
        out.append(PairedDelta.model_validate({
            "metric": metric, "control": round(float(xa.mean()), 4), "variant": round(float(xb.mean()), 4),
            "diff": round(float(d.mean()), 4), "ci_low": low, "ci_high": high, "n": len(ids),
        }))
    return out


CLICKSTREAM_COLUMNS = (
    "variant", "site", "shopper", "mission", "device", "age_group", "gender", "step", "page", "url", "option", "action",
    "target", "label", "search_text", "thought", "seconds", "load_seconds", "source", "outcome", "order_total",
)


def _cell(value: object) -> object:
    """Text that a spreadsheet would read as a formula is kept as text."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "'")):
        return "'" + value
    return value


def clickstream_csv(variants: list[tuple[OnlineSite, list[SessionResult]]], shoppers: dict[str, OnlineShopper]) -> str:
    """Every click of every session, one row each (an event export in the manner of web analytics)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CLICKSTREAM_COLUMNS)
    for index, (site, sessions) in enumerate(variants):
        for session in sessions:
            shopper = shoppers.get(session.shopper_id)
            for step in session.steps:
                choice = step.choice
                if choice is None:
                    continue
                writer.writerow([_cell(v) for v in (
                    index, site.name, session.shopper_id, shopper.mission if shopper else "",
                    shopper.device if shopper else "", shopper.age_group if shopper else "",
                    shopper.gender if shopper else "", step.index, step.page.value, step.url, choice.number,
                    choice.kind.value, choice.target, choice.label, step.search_text, step.thought, step.seconds,
                    step.load_seconds, step.source, session.outcome, session.order_total,
                )])
    return out.getvalue()
