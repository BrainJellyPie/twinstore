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

from pydantic import BaseModel, Field

from store_emulator.domain.analysis import MetricComparison
from store_emulator.domain.marketing import ExperimentReport, FocusOutcome, PriceRange, SurveyReport, VariantResult

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
        headline = (f"{v.name} earns {money(m.diff, cur, signed=True)} per visitor ({pct(m.rel_diff)}) over the control, "
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
        rec.append(f"{v.name} sells more of the tracked product ({u.diff * 100:+.1f} units per 100 visitors, {pct(u.rel_diff, 0)}) "
                   "without moving the basket: worth it for that product's margin or brand goals, not for store revenue.")
    if losses:
        rec.append(f"Avoid {', '.join(v.name for v in losses)}: revenue per visitor falls beyond noise.")
    if not wins and needed > r.panel_size:
        rec.append(f"To detect a 5 % change in revenue per visitor, run about {needed:,} shoppers per arm "
                   f"(this test had {r.panel_size}).")
    if not rec:
        rec.append("Keep the control: none of the changes moved sales of the store or the tracked products.")
    return Finding(headline=headline, recommendation=rec)


# ── model commentary (optional) ─────────────────────────────────────────────────

REPORT_NARRATIVE_PROMPT = """You are a retail analyst writing the commentary of an A/B test report for a brand or category
manager. The test ran on a digital twin of the store with synthetic shoppers; every arm used the same shoppers. Use only
the numbers in the report below; do not invent figures, products or causes you cannot support from them. Say plainly
when a difference is within noise (its 95 % interval crosses zero). Write in English, short paragraphs, no headings."""


class ReportNarrative(BaseModel):
    summary: str = Field(max_length=1200, description="what happened, two to four sentences")
    interpretation: str = Field(max_length=1200, description="why it may have happened, as hypotheses tied to the numbers")
    next_steps: str = Field(max_length=900, description="what to test or do next")
    model: str = ""


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


async def write_narrative(llm: StructuredLLM, r: ExperimentReport, layout: str = "") -> ReportNarrative:
    return await llm.generate_structured_async(ReportNarrative, REPORT_NARRATIVE_PROMPT, report_markdown(r, layout), max_retries=1, seed=0)


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
            f"{a.units_per_visitor:.2f}" + (f" ({pct(units.rel_diff)})" if units else ""),
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
        f"{r.panel_size} shoppers per arm · {r.visitors_per_day:,.0f} visitors a day",
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
    spend_rows = [(v.name, f"{pct(m.rel_diff)} vs control", m.diff, m.ci_low, m.ci_high)
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
        f"<div class='kpi'><span>Visitors a day</span><b>{r.visitors_per_day:,.0f}</b></div>",
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
{('<h2>Tracked products</h2>' + ''.join(focus_blocks)) if focus_blocks else ''}
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


def survey_report_html(r: SurveyReport, board_jpeg: bytes | None = None) -> str:
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
            clear = best.ci_low > max(s.ci_high for s in rows if s is not best)
            leads.append(f"{name(best.stimulus)} leads on {_SCALE_LABEL[q].lower()} ({best.mean:.2f} vs {second:.2f} out of 5"
                         f"{'' if clear else ', intervals overlap'}).")
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
