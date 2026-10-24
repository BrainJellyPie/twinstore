"""The A/B test write-up: an executive summary with a rule-based recommendation, the test design, results
with paired 95 % intervals and charts, tracked products, method and caveats — as Markdown and as one
self-contained, print-ready HTML page. Every number comes from the experiment report; an optional
model-written commentary (`ReportNarrative`) is added verbatim and labelled as such.
"""

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.marketing import (
    ConjointReport,
    ExperimentReport,
    FocusOutcome,
    PriceRange,
    PriceResponse,
    ShelfTestReport,
    SurveyReport,
    VariantResult,
)

from .reading import StudyReading, reading_html

_ZERO_DECIMAL = {"KRW", "JPY", "VND", "IDR", "CLP", "ISK", "HUF", "TWD"}
_SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "KRW": "₩"}


def money(minor: float, currency: str, *, signed: bool = False) -> str:
    """Minor units as a price; fractional cents keep two decimals of the major unit."""
    code = currency.upper()
    major = minor if code in _ZERO_DECIMAL else minor / 100
    digits = 0 if code in _ZERO_DECIMAL else 2
    sign = ("+" if major >= 0 else "−") if signed else ("−" if major < 0 else "")
    body = f"{abs(major):,.{digits}f}"
    sym = _SYMBOL.get(code)
    return f"{sign}{sym}{body}" if sym else f"{sign}{body} {code}"


def pct(x: float, digits: int = 1) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x) * 100:.{digits}f} %"


def _metric(v: VariantResult, name: str) -> MetricComparison | None:
    return next((m for m in v.vs_control if m.metric == name), None)


def _focus(v: VariantResult, sku: str, metric: str) -> FocusOutcome | None:
    return next((f for f in v.focus if f.sku == sku and f.metric == metric), None)


@dataclass
class Finding:
    headline: str
    recommendation: list[str]


def _sampled(r: ExperimentReport) -> bool:
    return 0 < r.simulated_visitors_per_day < r.visitors_per_day


def _visitors_a_day(r: ExperimentReport) -> str:
    """Per-day money scales by the store's estimated visitors; the simulated customers are a sample of them."""
    if _sampled(r):
        return f"{r.visitors_per_day:,.0f} visitors a day estimated ({r.simulated_visitors_per_day:,.0f} a day simulated)"
    return f"{r.visitors_per_day:,.0f} visitors a day"


def findings(r: ExperimentReport) -> Finding:
    """What the numbers say, in plain sentences (no model involved)."""
    vpd = r.visitors_per_day
    cur = r.currency
    wins: list[tuple[VariantResult, MetricComparison]] = []
    losses: list[VariantResult] = []
    product_only: list[tuple[VariantResult, FocusOutcome]] = []
    needed = 0
    tracked = "*" if len(r.focus_skus) > 1 else (r.focus_skus[0] if r.focus_skus else "")
    for v in r.variants:
        spend = _metric(v, "spend")
        if spend is None:
            continue
        needed = max(needed, spend.n_for_5pct_effect)
        if spend.ci_low > 0:
            wins.append((v, spend))
        elif spend.ci_high < 0:
            losses.append(v)
        else:
            units = _focus(v, tracked, "units") if tracked else None
            if units is not None and units.ci_low > 0:
                product_only.append((v, units))
    rec: list[str] = []
    winner = next(((v, m) for v, m in wins if v.name == r.winner), wins[0] if wins else None)
    if winner:
        v, m = winner
        headline = (f"{v.name} earns {money(m.diff, cur, signed=True)} per visitor ({pct(m.rel_diff) if m.mean_a else 'from zero'}) over the control, "
                    f"beyond the noise of {r.panel_size} shoppers.")
        rec.append(f"Roll out {v.name}: about {money(m.diff * vpd, cur, signed=True)} a day and "
                   f"{money(m.diff * vpd * 30, cur, signed=True)} a month at {vpd:,.0f} visitors a day "
                   f"(95 % interval {money(m.ci_low * vpd, cur, signed=True)} to {money(m.ci_high * vpd, cur, signed=True)} a day).")
        for other, om in wins:
            if other is not v:
                rec.append(f"{other.name} also beats the control ({money(om.diff, cur, signed=True)} per visitor); "
                           f"compare it with {v.name} head to head before choosing.")
    elif losses:
        headline = (f"Revenue per visitor falls for {', '.join(v.name for v in losses)} "
                    f"beyond the noise of {r.panel_size} shoppers.")
    else:
        headline = f"No variant changes revenue per visitor beyond the noise of {r.panel_size} shoppers."
    for v, u in product_only:
        rec.append(f"{v.name} sells more of the tracked product ({u.diff * 100:+.1f} units per 100 visitors, {pct(u.rel_diff, 0) if u.control else 'from zero'}) "
                   "without moving the basket: worth it for that product's margin or brand goals, not for store revenue.")
    if losses:
        rec.append(f"Avoid {', '.join(v.name for v in losses)}: revenue per visitor falls beyond noise.")
    if not wins and needed > r.panel_size:
        rec.append(f"To detect a 5 % change in revenue per visitor, run about {needed:,} shoppers per arm "
                   f"(this test had {r.panel_size}).")
    pr = r.price_response
    if pr and pr.best_price is not None:
        rec.append(_price_advice(pr, cur))
    if not rec:
        rec.append("Keep the control: none of the changes moved sales of the store or the tracked products.")
    return Finding(headline=headline, recommendation=rec)


def _price_advice(pr: PriceResponse, cur: str) -> str:
    """The best tested price, with the elasticity only where it tells the same story: elastic demand puts the most
    revenue at the lowest price, inelastic demand at the highest."""
    text = f"Of the prices tested for {pr.name}, {money(pr.best_price or 0, cur)} brings the most {pr.name} revenue per visitor"
    e = pr.elasticity
    if e is None:
        return text + "."
    if e < -1 and pr.best_price == pr.points[0].price:
        return text + f"; its price elasticity across the arms is about {e:.2f} (elastic: a price cut grows its revenue)."
    if -1 <= e <= 0 and pr.best_price == pr.points[-1].price:
        return text + f"; its price elasticity across the arms is about {e:.2f} (inelastic: a price rise grows its revenue)."
    return (text + f", but the price elasticity across the arms (about {e:.2f}) does not point to that price: "
            "the arms do not follow one demand curve, so read both as within noise.")


# ── model commentary (optional) ─────────────────────────────────────────────────

REPORT_NARRATIVE_PROMPT = """You are a retail analyst writing the commentary of an A/B test report for a brand or category
manager. The test ran on a digital twin of the store with synthetic shoppers; every arm used the same shoppers. Use only
the numbers in the report below; do not invent figures, products or causes you cannot support from them. Say plainly
when a difference is within noise (its 95 % interval crosses zero). Always provide a nonblank summary of what the
report shows. Write in English, short paragraphs, no headings."""


class ReportNarrative(BaseModel):
    summary: str = Field(max_length=1200, description="what happened, two to four sentences")
    interpretation: str = Field(max_length=1200, description="why it may have happened, as hypotheses tied to the numbers")
    next_steps: str = Field(max_length=900, description="what to test or do next")
    model: str = ""


class _NarrativeResponse(ReportNarrative):
    """Require new model output without rejecting old saved commentary."""
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=1200, description="what happened, two to four sentences")


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


async def write_narrative(llm: StructuredLLM, r: ExperimentReport, layout: str = "") -> ReportNarrative:
    return await llm.generate_structured_async(_NarrativeResponse, REPORT_NARRATIVE_PROMPT, report_markdown(r, layout), max_retries=2, seed=0)


# ── Markdown ────────────────────────────────────────────────────────────────────

def _arm_rows(r: ExperimentReport) -> list[list[str]]:
    cur = r.currency
    rows: list[list[str]] = []
    for i, a in enumerate([r.control, *r.variants]):
        spend, bought, units = _metric(a, "spend"), _metric(a, "bought"), _metric(a, "units")
        rows.append([
            f"{chr(65 + i)} · {a.name}", money(a.revenue_per_visitor, cur),
            f"{money(spend.diff, cur, signed=True)} [{money(spend.ci_low, cur, signed=True)}, {money(spend.ci_high, cur, signed=True)}]" if spend else "–",
            f"{a.conversion * 100:.1f} %" + (f" ({bought.diff * 100:+.1f} pt)" if bought else ""),
            f"{a.units_per_visitor:.2f}" + (f" ({pct(units.rel_diff) if units.mean_a else f'{units.diff:+.2f} from zero'})" if units else ""),
            f"{spend.prob_b_greater * 100:.0f} %" if spend else "–",
        ])
    return rows


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    out += ["| " + " | ".join(c.replace("|", "\\|") for c in row) + " |" for row in rows]
    return "\n".join(out)


def report_markdown(r: ExperimentReport, layout: str = "", narrative: ReportNarrative | None = None) -> str:
    f = findings(r)
    cur = r.currency
    lines = [
        f"# {r.name}",
        "",
        f"A/B test on {layout or r.setup_id} · {'vision shoppers' + (f' ({r.model})' if r.model else '') if r.engine == 'vlm' else 'rule shoppers'} · "
        f"{r.panel_size} shoppers per arm · {_visitors_a_day(r)}",
        "",
        "## Summary",
        "",
        f.headline,
        "",
        *[f"- {x}" for x in f.recommendation],
    ]
    if narrative:
        lines += ["", "### Commentary (model-written)", "", narrative.summary, "", narrative.interpretation, "", narrative.next_steps]
    lines += ["", "## What was tested", ""]
    for i, v in enumerate(r.variants):
        lines.append(f"- **{chr(66 + i)} · {v.name}**: " + "; ".join(v.applied))
        lines += [f"  - warning: {w}" for w in v.warnings]
    lines += ["", "## Results", "", _md_table(
        ["Arm", "Revenue / visitor", "vs control [95 % CI]", "Conversion", "Units / visitor", "P(better)"], _arm_rows(r))]
    focus_rows: list[list[str]] = []
    for v in r.variants:
        for fo in v.focus:
            if fo.metric != "units":
                continue
            focus_rows.append([v.name, fo.name, f"{fo.control * 100:.1f}", f"{fo.variant * 100:.1f}",
                               f"{fo.diff * 100:+.1f} [{fo.ci_low * 100:+.1f}, {fo.ci_high * 100:+.1f}]", f"{fo.prob_better * 100:.0f} %"])
    if focus_rows:
        lines += ["", "## Tracked products (units per 100 visitors)", "",
                  _md_table(["Variant", "Product", "Control", "Variant", "Difference [95 % CI]", "P(more)"], focus_rows)]
    if r.price_response:
        pr = r.price_response
        lines += ["", f"## Price response · {pr.name}", "", _md_table(
            ["Arm", "Price", "Units / 100 visitors [95 % CI]", "Product revenue / 100 visitors"],
            [[p.arm, money(p.price, cur), f"{p.units * 100:.1f} [{p.units_low * 100:.1f}, {p.units_high * 100:.1f}]", money(p.revenue * 100, cur)]
             for p in pr.points])]
        if pr.elasticity is not None:
            lines.append(f"\nPrice elasticity across the arms: {pr.elasticity:.2f}.")
    header, seg_rows = _segment_rows(r)
    if seg_rows:
        lines += ["", "## By segment (paired difference; ▲/▼ = 95 % interval above/below zero)", "",
                  _md_table(["Segment", "n", *header], [[seg, str(n), *cells] for seg, n, cells in seg_rows])]
    lines += ["", "## Best sellers per arm", ""]
    for a in [r.control, *r.variants]:
        top = ", ".join(f"{s.name} ({money(s.revenue, cur)})" for s in a.top_skus[:5])
        lines.append(f"- **{a.name}**: {top or '–'}")
    lines += ["", "## Method and caveats", "", *[f"- {x}" for x in _method(r)]]
    return "\n".join(lines) + "\n"


def _method(r: ExperimentReport) -> list[str]:
    return [
        f"Every arm ran the same {r.panel_size} synthetic shoppers with the same random numbers (common random numbers), "
        "so differences come from the change, not from different people.",
        "Intervals are 95 % paired percentile bootstraps over shoppers; a difference whose interval crosses zero is within noise.",
        "Daily and monthly figures scale the per-visitor difference by the store's visitors a day; they assume the change "
        "does not alter footfall.",
        "Synthetic shoppers are for screening and direction: confirm large decisions with a field test.",
        *r.notes,
    ]


def _demand_svg(pr: PriceResponse, currency: str) -> str:
    """Units per 100 visitors against price, with the arms' 95 % intervals."""
    w, h, left, bottom = 640, 220, 46, 30
    lo_p, hi_p = pr.points[0].price, pr.points[-1].price
    top = max(p.units_high for p in pr.points) * 100 * 1.15 or 1.0

    def px(v: float) -> float:
        return left + (v - lo_p) / max(1, hi_p - lo_p) * (w - left - 20)

    def py(u: float) -> float:
        return 10 + (1 - u * 100 / top) * (h - bottom - 10)

    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for t in (0, 0.5, 1):
        y = 10 + (1 - t) * (h - bottom - 10)
        parts.append(f'<line x1="{left}" x2="{w - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e7eb"/>'
                     f'<text x="{left - 6}" y="{y + 4:.1f}" font-size="10" text-anchor="end" fill="#5f6368">{top * t:.1f}</text>')
    pts = " ".join(f"{px(p.price):.1f},{py(p.units):.1f}" for p in pr.points)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#2a78d6" stroke-width="2"/>')
    for p in pr.points:
        x = px(p.price)
        parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{py(p.units_high):.1f}" y2="{py(p.units_low):.1f}" stroke="#2a78d6" stroke-opacity="0.45" stroke-width="6" stroke-linecap="round"/>'
                     f'<circle cx="{x:.1f}" cy="{py(p.units):.1f}" r="5" fill="{"#eb6834" if p.price == pr.best_price else "#2a78d6"}" stroke="#fff" stroke-width="2"/>'
                     f'<text x="{x:.1f}" y="{h - 10}" font-size="10" text-anchor="middle" fill="#5f6368">{escape(money(p.price, currency))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _segment_rows(r: ExperimentReport) -> tuple[list[str], list[tuple[str, int, list[str]]]]:
    """Header (one column per variant and metric) and rows of formatted paired differences by segment."""
    cur = r.currency
    metrics = [m for m in ("spend", "focus_units") if any(s.metric == m for v in r.variants for s in v.segments)]
    header = [f"{v.name} · {'revenue / visitor' if m == 'spend' else 'units / 100'}" for v in r.variants for m in metrics]
    segments = list(dict.fromkeys(s.segment for v in r.variants for s in v.segments))
    rows: list[tuple[str, int, list[str]]] = []
    for seg in segments:
        cells: list[str] = []
        n = 0
        for v in r.variants:
            for m in metrics:
                x = next((s for s in v.segments if s.segment == seg and s.metric == m), None)
                if x is None:
                    cells.append("–")
                    continue
                n = x.n
                mark = " ▲" if x.ci_low > 0 else " ▼" if x.ci_high < 0 else ""
                cells.append((money(x.diff, cur, signed=True) if m == "spend" else f"{x.diff * 100:+.1f}") + mark)
        rows.append((seg, n, cells))
    return header, rows


def _segment_section(r: ExperimentReport) -> str:
    header, rows = _segment_rows(r)
    if not rows:
        return ""
    body = "".join(f"<tr><td>{escape(seg.replace('age ', 'Age ').replace('gender ', ''))}</td><td class=n>{n}</td>"
                   + "".join(f"<td class=n>{escape(c)}</td>" for c in cells) + "</tr>" for seg, n, cells in rows)
    return ("<h2>By segment</h2><p class='note'>Paired difference to control within each segment; ▲ / ▼ = 95 % interval above / below zero. "
            "Segments are smaller than the panel, so expect wider intervals.</p>"
            f"<table><tr><th>Segment</th><th>n</th>{''.join(f'<th>{escape(h)}</th>' for h in header)}</tr>{body}</table>")


def _price_section(r: ExperimentReport) -> str:
    pr = r.price_response
    if pr is None:
        return ""
    cur = r.currency
    rows = "".join(
        f"<tr><td>{escape(p.arm)}</td><td class=n>{escape(money(p.price, cur))}</td><td class=n>{p.units * 100:.1f} "
        f"<span class=note>[{p.units_low * 100:.1f}, {p.units_high * 100:.1f}]</span></td><td class=n>{escape(money(p.revenue * 100, cur))}"
        f"{' ★' if p.price == pr.best_price else ''}</td></tr>" for p in pr.points)
    el = f" · elasticity across the arms ≈ {pr.elasticity:.2f}" if pr.elasticity is not None else ""
    return (f"<h2>Price response · {escape(pr.name)}</h2><p class='note'>Units per 100 visitors at each tested price (bars: 95 % intervals){el}. "
            "★ = most product revenue.</p>" + _demand_svg(pr, cur)
            + f"<table><tr><th>Arm</th><th>Price</th><th>Units / 100 visitors</th><th>Product revenue / 100 visitors</th></tr>{rows}</table>")


# ── HTML ────────────────────────────────────────────────────────────────────────

def _forest(rows: list[tuple[str, str, float, float, float]], fmt: str, currency: str) -> str:
    """Horizontal dot-and-interval chart around zero. rows: (label, sub, diff, lo, hi)."""
    if not rows:
        return ""
    span = max(1e-9, *(max(abs(a), abs(b), abs(c)) for _, _, a, b, c in rows)) * 1.15
    w, left, right, row_h = 720, 190, 120, 40
    plot = w - left - right
    h = row_h * len(rows) + 34

    def x(v: float) -> float:
        return left + (v / span + 1) / 2 * plot

    def label(v: float) -> str:
        return escape(money(v, currency, signed=True) if fmt == "money" else f"{v:+.1f}")

    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" xmlns="http://www.w3.org/2000/svg">',
             f'<line x1="{x(0):.1f}" y1="6" x2="{x(0):.1f}" y2="{h - 26}" stroke="#9aa0a6" stroke-width="1"/>']
    for i, (name, sub, d, lo, hi) in enumerate(rows):
        y = 8 + i * row_h + row_h / 2
        tone, verdict = ("#0d9768", "clearly up") if lo > 0 else ("#d03b3b", "clearly down") if hi < 0 else ("#5f6368", "within noise")
        parts += [
            f'<text x="0" y="{y - 3:.1f}" font-size="13" font-weight="600" fill="#111">{escape(name)}</text>',
            f'<text x="0" y="{y + 13:.1f}" font-size="11" fill="#5f6368">{escape(sub)}</text>',
            f'<rect x="{x(min(lo, hi)):.1f}" y="{y - 4:.1f}" width="{max(1.0, abs(hi - lo) / span / 2 * plot):.1f}" height="8" rx="4" fill="#2a78d6" opacity="0.35"/>',
            f'<circle cx="{x(d):.1f}" cy="{y:.1f}" r="6" fill="#2a78d6" stroke="#fff" stroke-width="2"/>',
            f'<text x="{w}" y="{y - 1:.1f}" font-size="13" font-weight="600" text-anchor="end" fill="#111">{label(d)}</text>',
            f'<text x="{w}" y="{y + 14:.1f}" font-size="11" text-anchor="end" fill="{tone}">{verdict}</text>',
        ]
    parts += [
        f'<text x="{left}" y="{h - 8}" font-size="11" fill="#5f6368">{label(-span)}</text>',
        f'<text x="{x(0):.1f}" y="{h - 8}" font-size="11" text-anchor="middle" fill="#5f6368">0 = control</text>',
        f'<text x="{left + plot}" y="{h - 8}" font-size="11" text-anchor="end" fill="#5f6368">{label(span)}</text>',
        "</svg>",
    ]
    return "".join(parts)


_CSS = """
:root{--ink:#111;--muted:#5f6368;--line:#e5e7eb;--accent:#2a78d6}
*{box-sizing:border-box}body{margin:0;background:#f4f5f7;color:var(--ink);font:14px/1.55 "Inter","Segoe UI",system-ui,sans-serif}
main{max-width:860px;margin:32px auto;background:#fff;padding:48px 56px;border-radius:18px;box-shadow:0 20px 60px -30px rgba(0,0,0,.25)}
h1{font-size:28px;letter-spacing:-.02em;margin:0 0 4px}h2{font-size:17px;margin:34px 0 10px;padding-top:18px;border-top:1px solid var(--line)}
h3{font-size:14px;margin:18px 0 6px}.meta{color:var(--muted);font-size:13px}.brand{font-weight:700;letter-spacing:-.03em;color:var(--accent)}
.headline{font-size:18px;font-weight:600;margin:14px 0 8px}.win{border-left:4px solid #0d9768;padding:10px 14px;background:#eefaf4;border-radius:8px}
.flat{border-left:4px solid #9aa0a6;padding:10px 14px;background:#f6f7f8;border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}.kpi{border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.kpi b{display:block;font-size:20px}.kpi span{color:var(--muted);font-size:12px}.note{color:var(--muted);font-size:12px}
.ai{background:#f5f3ff;border-radius:10px;padding:12px 14px}.ai small{color:var(--muted)}
footer{margin-top:30px;color:var(--muted);font-size:11.5px}
@media print{body{background:#fff}main{box-shadow:none;margin:0;max-width:none;padding:0 6mm}h2{break-after:avoid}table,svg{break-inside:avoid}}
@page{size:A4;margin:14mm}
"""


def report_html(r: ExperimentReport, layout: str = "", narrative: ReportNarrative | None = None) -> str:
    f = findings(r)
    cur = r.currency
    e = escape
    best = max([r.control, *r.variants], key=lambda v: v.revenue_per_visitor)
    spend_rows = [(v.name, f"{pct(m.rel_diff)} vs control" if m.mean_a else "from zero", m.diff, m.ci_low, m.ci_high)
                  for v in r.variants if (m := _metric(v, "spend")) is not None]
    focus_blocks: list[str] = []
    skus = list(dict.fromkeys(fo.sku for v in r.variants for fo in v.focus))
    for sku in skus:
        rows = [(v.name, f"{pct(fo.rel_diff, 0)} units" if fo.control else "new sales", fo.diff * 100, fo.ci_low * 100, fo.ci_high * 100)
                for v in r.variants if (fo := _focus(v, sku, "units")) is not None]
        name = next((fo.name for v in r.variants for fo in v.focus if fo.sku == sku), sku)
        focus_blocks.append(f"<h3>{e('All tracked products' if sku == '*' else name)} <span class='note'>· units per 100 visitors</span></h3>"
                            + _forest(rows, "units", cur))
    arms = "".join("<tr>" + "".join(f"<td{' class=n' if j else ''}>{e(c)}</td>" for j, c in enumerate(row)) + "</tr>" for row in _arm_rows(r))
    design = "".join(
        f"<tr><td><b>{chr(66 + i)} · {e(v.name)}</b></td><td>{'<br>'.join(e(a) for a in v.applied)}"
        + "".join(f"<br><span class='note'>⚠ {e(w)}</span>" for w in v.warnings) + "</td></tr>"
        for i, v in enumerate(r.variants)
    )
    tops = "".join(f"<tr><td><b>{e(a.name)}</b></td><td>{e(', '.join(f'{s.name} ({money(s.revenue, cur)})' for s in a.top_skus[:5]) or '–')}</td></tr>"
                   for a in [r.control, *r.variants])
    ai = ""
    if narrative:
        ai = (f"<div class='ai'><small>Commentary written by {e(narrative.model or 'a language model')} from the numbers in this report</small>"
              f"<p>{e(narrative.summary)}</p><p>{e(narrative.interpretation)}</p><p>{e(narrative.next_steps)}</p></div>")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    engine = f"Vision shoppers{f' ({r.model})' if r.model else ''}" if r.engine == "vlm" else "Rule shoppers"
    kpis = "".join([
        f"<div class='kpi'><span>Control revenue / visitor</span><b>{e(money(r.control.revenue_per_visitor, cur))}</b></div>",
        f"<div class='kpi'><span>Highest observed revenue / visitor</span><b>{e(best.name)}</b></div>",
        f"<div class='kpi'><span>Shoppers per arm</span><b>{r.panel_size:,}</b></div>",
        (f"<div class='kpi'><span>Visitors a day</span><b>{r.visitors_per_day:,.0f}</b>"
         f"{f'<small>estimated; {r.simulated_visitors_per_day:,.0f} simulated a day</small>' if _sampled(r) else ''}</div>"),
    ])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(r.name)} · A/B test report</title><style>{_CSS}</style></head><body><main>
<div class="meta"><span class="brand">twinstore</span> · A/B test report · {now}</div>
<h1>{e(r.name)}</h1>
<div class="meta">Control layout: {e(layout or r.setup_id)} · {e(engine)} · {r.panel_size:,} shoppers per arm · {len(r.variants)} variant{'s' if len(r.variants) != 1 else ''}</div>
<div class="kpis">{kpis}</div>
<h2>Summary</h2>
<div class="{'win' if r.winner else 'flat'}"><div class="headline">{e(f.headline)}</div><ul>{''.join(f'<li>{e(x)}</li>' for x in f.recommendation)}</ul></div>
{ai}
<h2>What was tested</h2><table><tr><th>Arm</th><th>Changes against the control</th></tr>{design}</table>
<h2>Revenue per visitor vs control</h2>
<p class="note">Dot = paired difference; bar = 95 % interval. A bar crossing zero is within noise.</p>
{_forest(spend_rows, "money", cur)}
<table><tr><th>Arm</th><th>Revenue / visitor</th><th>vs control [95 % CI]</th><th>Conversion</th><th>Units / visitor</th><th>P(better)</th></tr>{arms}</table>
{_price_section(r)}
{('<h2>Tracked products</h2>' + ''.join(focus_blocks)) if focus_blocks else ''}
{_segment_section(r)}
<h2>Best sellers per arm</h2><table>{tops}</table>
<h2>Method and caveats</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in _method(r))}</ul>
<footer>Generated by TwinStore from experiment {e(r.experiment_id)} in {r.seconds:.1f} s. Print this page to save it as PDF.</footer>
</main></body></html>"""


# ── concept test report ─────────────────────────────────────────────────────────

_SCALE_LABEL = {"purchase_intent": "Purchase intent", "appeal": "Pack appeal", "value": "Value for money", "uniqueness": "Stand-out"}
_LIKERT = ["#e34948", "#f0a09f", "#e3e2de", "#86b6ef", "#2a78d6"]


def _likert_svg(counts: list[int]) -> str:
    n = sum(counts) or 1
    x = 0.0
    parts = ['<svg viewBox="0 0 300 16" width="300" height="16" xmlns="http://www.w3.org/2000/svg">']
    for k, c in enumerate(counts):
        w = c / n * 300
        if w <= 0:
            continue
        parts.append(f'<rect x="{x:.1f}" y="0" width="{max(0.0, w - 2):.1f}" height="16" rx="3" fill="{_LIKERT[k]}"><title>{k + 1}: {c}</title></rect>')
        if w > 26:
            ink = "#fff" if k in (0, 4) else "#111"
            parts.append(f'<text x="{x + w / 2 - 1:.1f}" y="12" font-size="10" text-anchor="middle" fill="{ink}">{round(c / n * 100)}</text>')
        x += w
    parts.append("</svg>")
    return "".join(parts)


def _price_svg(price: PriceRange, currency: str) -> str:
    if not price.curve:
        return ""
    w, h, left, bottom = 640, 220, 40, 26
    xs = [p[0] for p in price.curve]
    lo, hi = min(xs), max(xs)
    span = max(1, hi - lo)

    def px(v: float) -> float:
        return left + (v - lo) / span * (w - left - 10)

    def py(s: float) -> float:
        return 8 + (1 - s) * (h - bottom - 8)

    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    names = ["Too cheap", "A bargain", "Getting expensive", "Too expensive"]
    parts = [f'<svg viewBox="0 0 {w} {h + 22}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    if price.point_of_marginal_cheapness is not None and price.point_of_marginal_expensiveness is not None:
        a, b = px(price.point_of_marginal_cheapness), px(price.point_of_marginal_expensiveness)
        parts.append(f'<rect x="{a:.1f}" y="8" width="{max(0.0, b - a):.1f}" height="{h - bottom - 8}" fill="#2a78d6" opacity="0.07"/>')
    for t in (0, 0.5, 1):
        parts.append(f'<line x1="{left}" x2="{w - 10}" y1="{py(t):.1f}" y2="{py(t):.1f}" stroke="#e5e7eb"/>'
                     f'<text x="{left - 6}" y="{py(t) + 4:.1f}" font-size="10" text-anchor="end" fill="#5f6368">{int(t * 100)}%</text>')
    for k in range(4):
        pts = " ".join(f"{px(p[0]):.1f},{py(p[k + 1]):.1f}" for p in price.curve)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{colors[k]}" stroke-width="2"/>')
    if price.optimal_price_point is not None:
        x = px(price.optimal_price_point)
        parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="8" y2="{h - bottom}" stroke="#111" stroke-opacity="0.5"/>'
                     f'<text x="{x + 4:.1f}" y="18" font-size="10" fill="#111">optimal {escape(money(price.optimal_price_point, currency))}</text>')
    for v, anchor in ((lo, "start"), ((lo + hi) / 2, "middle"), (hi, "end")):
        parts.append(f'<text x="{px(v):.1f}" y="{h - 8}" font-size="10" text-anchor="{anchor}" fill="#5f6368">{escape(money(v, currency))}</text>')
    for k in range(4):
        parts.append(f'<rect x="{left + k * 150}" y="{h + 6}" width="14" height="3" fill="{colors[k]}"/>'
                     f'<text x="{left + k * 150 + 20}" y="{h + 11}" font-size="11" fill="#111">{names[k]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def survey_report_html(r: SurveyReport, board_jpeg: bytes | None = None, reading: StudyReading | None = None) -> str:
    e = escape
    letters = "ABCD"

    def name(i: int) -> str:
        return r.stimulus_names[i] if i < len(r.stimulus_names) and r.stimulus_names[i] else letters[i]

    board = f'<img src="data:image/jpeg;base64,{b64encode(board_jpeg).decode()}" alt="What respondents saw" style="display:block;margin:16px auto 0;max-width:100%;max-height:360px;border-radius:12px;background:#f6f5f2">' if board_jpeg else ""
    leads: list[str] = []
    for q in _SCALE_LABEL:
        rows = [s for s in r.scales if s.question == q]
        if len(rows) > 1:
            best = max(rows, key=lambda s: s.mean)
            second = sorted((s.mean for s in rows), reverse=True)[1]
            label = _SCALE_LABEL[q].lower()
            if round(best.mean, 2) == round(second, 2):
                level = [name(s.stimulus) for s in rows if round(s.mean, 2) == round(best.mean, 2)]
                leads.append(f"{', '.join(level[:-1])} and {level[-1]} are level on {label} ({best.mean:.2f} out of 5).")
            elif best.ci_low > max(s.ci_high for s in rows if s is not best):
                leads.append(f"{name(best.stimulus)} leads on {label} ({best.mean:.2f} vs {second:.2f} out of 5).")
            else:
                leads.append(f"No clear leader on {label}: {name(best.stimulus)} {best.mean:.2f} vs {second:.2f} out of 5, "
                             "intervals overlap.")
        elif rows:
            leads.append(f"{_SCALE_LABEL[q]}: {rows[0].mean:.2f} out of 5, {rows[0].top2 * 100:.0f} % answer 4 or 5.")
    if r.preference:
        top = max(r.preference, key=lambda p: p.share)
        leads.append(f"{top.share * 100:.0f} % would take {top.name} home (95 % interval {top.ci_low * 100:.0f}–{top.ci_high * 100:.0f} %).")
    if r.price and r.price.optimal_price_point is not None:
        leads.append(f"Acceptable price for {name(0)}: {money(r.price.point_of_marginal_cheapness or 0, r.currency)}–"
                     f"{money(r.price.point_of_marginal_expensiveness or 0, r.currency)}, optimal {money(r.price.optimal_price_point, r.currency)}.")
    scale_rows = "".join(
        f"<tr><td>{e(_SCALE_LABEL.get(s.question, s.question))}</td><td>{letters[s.stimulus]} · {e(name(s.stimulus))}</td>"
        f"<td>{_likert_svg(s.distribution)}</td><td class=n>{s.mean:.2f}</td><td class=n>{s.ci_low:.2f}–{s.ci_high:.2f}</td>"
        f"<td class=n>{s.top2 * 100:.0f} %</td></tr>"
        for s in r.scales
    )
    pref = "".join(f"<tr><td>{letters[p.stimulus]} · {e(p.name)}</td><td class=n>{p.share * 100:.0f} %</td>"
                   f"<td class=n>{p.ci_low * 100:.0f}–{p.ci_high * 100:.0f} %</td></tr>" for p in r.preference)
    cols = list(dict.fromkeys(k for s in r.segments for k in s.values))

    def col_label(c: str) -> str:
        q, _, letter = c.partition("·")
        return f"{'Prefer' if q == 'prefer' else _SCALE_LABEL.get(q, q)} {letter}"

    said: dict[str, int] = {}
    for v in r.verbatims:
        said[v] = said.get(v, 0) + 1
    seg = "".join(
        f"<tr><td>{e(s.segment)}</td><td class=n>{s.n}</td>"
        + "".join(f"<td class=n>{(f'{s.values[c] * 100:.0f} %' if c.startswith('prefer') else f'{s.values[c]:.2f}') if c in s.values else '–'}</td>" for c in cols)
        + "</tr>"
        for s in r.segments
    )
    price = ""
    if r.price:
        p = r.price
        price = (f"<h2>Price range for {e(name(0))} <span class='note'>· Van Westendorp, n = {p.n}</span></h2>{_price_svg(p, r.currency)}"
                 "<table><tr><th>Floor</th><th>Optimal</th><th>Indifference</th><th>Ceiling</th></tr><tr>"
                 + "".join(f"<td>{e(money(v, r.currency)) if v is not None else '–'}</td>" for v in
                           (p.point_of_marginal_cheapness, p.optimal_price_point, p.indifference_price_point, p.point_of_marginal_expensiveness))
                 + "</tr></table>")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(r.name)} · concept test report</title><style>{_CSS}</style></head><body><main>
<div class="meta"><span class="brand">twinstore</span> · Concept test report · {now}</div>
<h1>{e(r.name)}</h1>
<div class="meta">{r.respondents} synthetic respondents · {len(r.stimuli)} product{'s' if len(r.stimuli) != 1 else ''} · {e(r.model)}</div>
{board}
<h2>Summary</h2><div class="flat"><ul>{''.join(f'<li>{e(x)}</li>' for x in leads) or '<li>No scale questions were asked.</li>'}</ul></div>
{reading_html(reading)}
{f'<h2>Scales <span class="note">· 1–5, red = low, blue = high; mean with 95 % interval; share answering 4–5</span></h2><table><tr><th>Question</th><th>Product</th><th>Answers</th><th>Mean</th><th>95 % CI</th><th>Top-2</th></tr>{scale_rows}</table>' if scale_rows else ''}
{f'<h2>Would take home</h2><table><tr><th>Product</th><th>Share</th><th>95 % Wilson interval</th></tr>{pref}</table>' if pref else ''}
{price}
{f'<h2>By segment</h2><table><tr><th>Segment</th><th>n</th>{"".join(f"<th>{e(col_label(c))}</th>" for c in cols)}</tr>{seg}</table>' if seg else ''}
{f'<h2>In their words</h2><ul>{"".join(f"<li>{e(v)}{f' <span class=note>×{k}</span>' if k > 1 else ''}</li>" for v, k in sorted(said.items(), key=lambda x: -x[1])[:16])}</ul>' if said else ''}
<h2>Method and caveats</h2><ul>{''.join(f'<li>{e(n)}</li>' for n in [
        "Each respondent is one of the project's personas, answering through a vision-language model that sees the products side by side.",
        "Means use normal-approximation 95 % intervals; shares use Wilson intervals; price points follow Van Westendorp (inconsistent answer sets dropped).",
        *r.notes,
    ])}</ul>
<footer>Generated by TwinStore from concept test {e(r.survey_id)}. Print this page to save it as PDF.</footer>
</main></body></html>"""


# ── shelf test report ───────────────────────────────────────────────────────────

_SHELF_METRIC = {"pick": "Would take it", "noticed": "Noticed (top three)", "noticed_first": "Noticed first"}


def shelf_report_html(r: ShelfTestReport, control_png: bytes, test_png: bytes, reading: StudyReading | None = None) -> str:
    e = escape
    pick = next((c for c in r.comparisons if c.metric == "pick"), None)

    def pts(v: float) -> str:
        return f"{'+' if v >= 0 else '−'}{abs(v) * 100:.1f}"

    if pick is None:
        headline = "No respondent answered both shelves."
    elif pick.ci_low > 0 or pick.ci_high < 0:
        headline = (f"{'More' if pick.ci_low > 0 else 'Fewer'} respondents take {r.target_name} on the test shelf: "
                    f"{pick.control * 100:.0f} % → {pick.test * 100:.0f} % ({pts(pick.diff)} pt, 95 % interval {pts(pick.ci_low)} to {pts(pick.ci_high)} pt).")
    else:
        headline = (f"The change does not move {r.target_name}'s pick share beyond noise: {pick.control * 100:.0f} % → {pick.test * 100:.0f} % "
                    f"(95 % interval {pts(pick.ci_low)} to {pts(pick.ci_high)} pt).")
    rows = [(_SHELF_METRIC.get(c.metric, c.metric), f"{c.control * 100:.0f} % → {c.test * 100:.0f} %", c.diff * 100, c.ci_low * 100, c.ci_high * 100)
            for c in r.comparisons]
    forest = _forest(rows, "units", r.currency)
    picks = "".join(f"<tr><td>{e(p.name)}{' ★' if p.sku == r.target_sku else ''}</td><td class=n>{p.control * 100:.0f} %</td><td class=n>{p.test * 100:.0f} %</td></tr>"
                    for p in r.picks)
    why = [c.why for c in r.choices if c.arm == "test" and c.pick_sku == r.target_sku and c.why][:10]

    def img(png: bytes) -> str:
        return f"data:image/png;base64,{b64encode(png).decode()}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(r.name)} · shelf test report</title><style>{_CSS}
.shelves{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}}.shelves img{{width:100%;border-radius:10px;border:1px solid var(--line)}}</style></head><body><main>
<div class="meta"><span class="brand">twinstore</span> · Shelf test report · {now}</div>
<h1>{e(r.name)}</h1>
<div class="meta">{e(r.rack_name)} · {e(r.face)} side · {r.respondents} respondents saw both shelves · {e(r.model)}</div>
<div class="shelves"><figure><img src="{img(control_png)}" alt="Control shelf"><figcaption class="note">Control</figcaption></figure>
<figure><img src="{img(test_png)}" alt="Test shelf"><figcaption class="note">Test · {e('; '.join(r.applied))}</figcaption></figure></div>
<h2>Summary</h2><div class="{'win' if pick and pick.ci_low > 0 else 'flat'}"><div class="headline">{e(headline)}</div></div>
{reading_html(reading)}
<h2>{e(r.target_name)}: test vs control <span class="note">· percentage points, paired 95 % intervals</span></h2>
{forest}
<h2>What respondents take</h2><table><tr><th>Product</th><th>Control</th><th>Test</th></tr>{picks}</table>
{f'<h2>Why they took {e(r.target_name)} on the test shelf</h2><ul>{"".join(f"<li>{e(w)}</li>" for w in why)}</ul>' if why else ''}
<h2>Method and caveats</h2><ul>{''.join(f'<li>{e(n)}</li>' for n in [
        "Each respondent, one of the project's personas, saw the control and the test shelf through a vision model, with the badge numbers shuffled per respondent.",
        "They named up to three products that caught their eye first and the one they would take; differences are paired by respondent (bootstrap 95 % intervals).",
        *r.warnings, *r.notes,
    ])}</ul>
<footer>Generated by TwinStore from shelf test {e(r.test_id)}. Print this page to save it as PDF.</footer>
</main></body></html>"""


# ── conjoint report ─────────────────────────────────────────────────────────────

def _utility_bar(u: float, lo: float, hi: float, span: float) -> str:
    w, mid = 180, 90

    def x(v: float) -> float:
        return mid + max(-1.0, min(1.0, v / span)) * (mid - 6)

    colour = "#2a78d6" if u >= 0 else "#e34948"
    return (f'<svg width="{w}" height="18" viewBox="0 0 {w} 18" role="img" aria-label="utility {u:+.2f}">'
            f'<line x1="{mid}" y1="0" x2="{mid}" y2="18" stroke="#c4c7cc"/>'
            f'<rect x="{min(x(0), x(u)):.1f}" y="5" width="{abs(x(u) - x(0)):.1f}" height="8" rx="2" fill="{colour}"/>'
            f'<line x1="{x(lo):.1f}" y1="9" x2="{x(hi):.1f}" y2="9" stroke="#111" stroke-width="1.2"/></svg>')


def conjoint_report_html(r: ConjointReport, reading: StudyReading | None = None) -> str:
    e = escape
    cur = r.currency
    ranked = sorted(r.importances, key=lambda i: -i.importance)
    leads: list[str] = []
    if ranked:
        top = ranked[0]
        clear = len(ranked) == 1 or top.ci_low > ranked[1].ci_high
        leads.append(f"{top.attribute} matters most: {top.importance * 100:.0f} % of what drives the choice "
                     f"(95 % interval {top.ci_low * 100:.0f}–{top.ci_high * 100:.0f} %{'' if clear else ', overlapping ' + ranked[1].attribute}).")
    for a in r.attributes:
        levels = [p for p in r.part_worths if p.attribute == a.name]
        if levels:
            best = max(levels, key=lambda p: p.utility)
            if best.wtp is not None and best.wtp > 0:
                ci = f", 95 % interval {money(best.wtp_low, cur)}–{money(best.wtp_high, cur)}" if best.wtp_low is not None and best.wtp_high is not None else ""
                leads.append(f"{a.name}: “{best.level}” is preferred; worth about {money(best.wtp, cur)} more than “{a.levels[0]}”{ci}.")
            else:
                leads.append(f"{a.name}: “{best.level}” is preferred.")
    if r.prices and (r.price_slope is None or r.price_slope >= 0):
        leads.append("Respondents did not consistently avoid the higher prices, so no willingness to pay is given.")
    if r.none_option:
        leads.append(f"{r.none_share * 100:.0f} % of choices were “none of these”.")
    span = max((max(abs(p.ci_low), abs(p.ci_high), abs(p.utility)) for p in r.part_worths), default=1.0) or 1.0
    imp = "".join(
        f"<tr><td>{e(i.attribute)}</td><td><div style='background:#eef2f8;border-radius:4px;height:12px;width:100%'>"
        f"<div style='background:#2a78d6;height:12px;border-radius:4px;width:{i.importance * 100:.1f}%'></div></div></td>"
        f"<td class=n>{i.importance * 100:.0f} %</td><td class=n>{i.ci_low * 100:.0f}–{i.ci_high * 100:.0f} %</td></tr>"
        for i in ranked
    )
    pw_rows: list[str] = []
    for name in [a.name for a in r.attributes] + (["Price"] if r.prices else []):
        levels = [p for p in r.part_worths if p.attribute == name]
        for k, p in enumerate(levels):
            wtp = "–"
            if p.wtp is not None:
                wtp = money(p.wtp, cur, signed=True)
                if p.wtp_low is not None and p.wtp_high is not None:
                    wtp += f" <span class=note>({money(p.wtp_low, cur)} to {money(p.wtp_high, cur)})</span>"
            elif k == 0 and name != "Price" and r.price_slope is not None and r.price_slope < 0:
                wtp = "<span class=note>base</span>"
            pw_rows.append(f"<tr><td>{e(name) if k == 0 else ''}</td><td>{e(p.level)}</td><td>{_utility_bar(p.utility, p.ci_low, p.ci_high, span)}</td>"
                           f"<td class=n>{p.utility:+.2f}</td><td class=n>{p.ci_low:+.2f} to {p.ci_high:+.2f}</td><td class=n>{wtp}</td></tr>")
    names = [i.attribute for i in r.importances]
    seg = "".join(
        f"<tr><td>{e(s.segment)}</td><td class=n>{s.n}</td>" + "".join(f"<td class=n>{s.importances.get(n, 0) * 100:.0f} %</td>" for n in names)
        + (f"<td class=n>{s.none_share * 100:.0f} %</td>" if r.none_option else "") + "</tr>"
        for s in r.segments
    )
    fit = r.fit
    kpis = "".join(f"<div class=kpi><b>{v}</b><span>{k}</span></div>" for k, v in [
        ("respondents", str(r.respondents)), ("choices", str(fit.choices if fit else 0)),
        ("hit rate (chance)", f"{fit.hit_rate * 100:.0f} % ({fit.chance_rate * 100:.0f} %)" if fit else "–"),
        ("McFadden R²", f"{fit.mcfadden_r2:.2f}" if fit else "–"),
    ])
    said: dict[str, int] = {}
    for v in r.verbatims:
        said[v] = said.get(v, 0) + 1
    design = "".join(f"<tr><td>{e(a.name)}</td><td>{e(' · '.join(a.levels))}</td></tr>" for a in r.attributes)
    if r.prices:
        design += f"<tr><td>Price</td><td>{e(' · '.join(money(p, cur) for p in r.prices))}</td></tr>"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(r.name)} · conjoint report</title><style>{_CSS}</style></head><body><main>
<div class="meta"><span class="brand">twinstore</span> · Conjoint report · {now}</div>
<h1>{e(r.name)}</h1>
<div class="meta">{e(r.product)} · {r.options} options per task{' + none' if r.none_option else ''} · {e(r.model)}</div>
<div class="kpis">{kpis}</div>
<h2>Summary</h2><div class="flat"><ul>{''.join(f'<li>{e(x)}</li>' for x in leads)}</ul></div>
{reading_html(reading)}
<h2>What drives the choice <span class="note">· attribute importance, 95 % intervals over respondents</span></h2>
<table><tr><th>Attribute</th><th style="width:50%"></th><th>Importance</th><th>95 % CI</th></tr>{imp}</table>
<h2>Part-worths <span class="note">· utility centred within each attribute; willingness to pay over the first level</span></h2>
<table><tr><th>Attribute</th><th>Level</th><th></th><th>Utility</th><th>95 % CI</th><th>Willingness to pay</th></tr>{''.join(pw_rows)}</table>
{f'<h2>By segment <span class="note">· importance; groups of at least 15 respondents</span></h2><table><tr><th>Segment</th><th>n</th>{"".join(f"<th>{e(n)}</th>" for n in names)}{"<th>None</th>" if r.none_option else ""}</tr>{seg}</table>' if seg else ''}
{f'<h2>In their words</h2><ul>{"".join(f"<li>{e(v)}{f' <span class=note>×{k}</span>' if k > 1 else ''}</li>" for v, k in sorted(said.items(), key=lambda x: -x[1])[:16])}</ul>' if said else ''}
<h2>Design</h2><table><tr><th>Attribute</th><th>Levels</th></tr>{design}</table>
<h2>Method and caveats</h2><ul>{''.join(f'<li>{e(n)}</li>' for n in [
        "Each respondent is one of the project's personas, answering through a language model; every respondent gets their own random, level-balanced choice tasks.",
        "Part-worths come from a pooled multinomial logit (level dummies, one linear price slope, a constant for none) with a weak ridge prior; "
        "intervals resample respondents (200 bootstrap draws).",
        "Willingness to pay divides a utility difference by the price slope and is only shown when the slope is negative.",
        *r.notes,
    ])}</ul>
<footer>Generated by TwinStore from conjoint study {e(r.conjoint_id)}. Print this page to save it as PDF.</footer>
</main></body></html>"""
