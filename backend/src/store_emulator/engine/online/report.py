"""An online run as one self-contained, print-ready HTML page to share: the verdict, every store's numbers with its
conversion as a ring, the paired differences with their 95 % intervals, the funnel, how visits ended and where people
left, friction, the exit survey, segments, products and searches, the questions asked about the run (with the report
lines each answer used), and the method notes. Every number comes from the run's result; nothing is drawn by a model.
"""

from datetime import datetime, timezone
from html import escape
from math import cos, pi, sin

from store_emulator.domain.interview import AnalystThread
from store_emulator.domain.online import OnlineRunResult, PairedDelta, VariantSummary
from store_emulator.engine.prompting import display_price

_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
_OTHER = "#8b8f98"
_OUTCOMES = {"purchased": ("Ordered", "#1baf7a"), "abandoned_cart": ("Abandoned cart", "#eda100"), "left": ("Left", "#9aa0a6"),
             "bounced": ("Bounced", "#e34948"), "timed_out": ("Ran out of patience", "#8b5cf6"), "step_limit": ("Step limit", "#5f6368")}
_STAGES = {"visit": "Visited", "product_view": "Viewed a product", "add_to_cart": "Added to cart", "checkout": "Started checkout",
           "payment": "Added payment", "purchase": "Ordered"}
_DELTAS = {"conversion": "Conversion", "revenue_per_session": "Revenue per visit", "add_to_cart_rate": "Added to cart",
           "steps": "Clicks per visit", "seconds": "Time per visit", "satisfaction": "Satisfaction (1–7)",
           "recommend": "Would recommend (0–10)", "rival_revenue_per_session": "Rival's revenue per visit"}
_POLICIES = {"rule": "Rule shoppers", "vlm": "Vision-model shoppers", "text": "Text-model shoppers"}


def _color(i: int) -> str:
    return _COLORS[i] if i < len(_COLORS) else _OTHER


def verdict(result: OnlineRunResult) -> tuple[str, str]:
    """(tone, headline): a variant that clearly converts better wins (the largest gain); the control holds when every
    variant clearly converts worse; otherwise it is too close to call. Same rule as the in-app report."""
    v = result.variants
    if not result.comparisons:
        s = v[0]
        return "single", f"{s.site_name}: {s.purchases} of {s.sessions} visits ordered ({s.conversion:.1%})"
    calls: list[tuple[int, float, bool]] = []
    for i, c in enumerate(result.comparisons, 1):
        d = next((x for x in c.deltas if x.metric == "conversion"), None)
        sure = d is not None and d.ci_low is not None and d.ci_high is not None and (d.ci_low > 0 or d.ci_high < 0)
        calls.append((i, d.diff if d else 0.0, sure))
    wins = sorted((c for c in calls if c[2] and c[1] > 0), key=lambda c: -c[1])
    if wins:
        i, diff, _ = wins[0]
        return "win", f"{v[i].site_name} wins: conversion {diff * 100:+.1f} points against {v[0].site_name}"
    if all(sure and diff < 0 for _, diff, sure in calls):
        return "holds", f"{v[0].site_name} holds: every variant converts worse"
    return "close", "Too close to call: no clear difference in conversion yet"


def _ring(share: float, color: str, size: int = 96) -> str:
    r, w = size / 2 - 7, 9
    c = size / 2
    angle = 2 * pi * min(max(share, 0.0), 0.9999)
    x, y = c + r * sin(angle), c - r * cos(angle)
    arc = (f'<path d="M {c:.1f} {c - r:.1f} A {r:.1f} {r:.1f} 0 {1 if angle > pi else 0} 1 {x:.1f} {y:.1f}" fill="none" '
           f'stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>') if share > 0 else ""
    return (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="conversion {share:.1%}">'
            f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="#ffffff22" stroke-width="{w}"/>{arc}'
            f'<text x="{c}" y="{c + 6}" text-anchor="middle" font-size="18" font-weight="700" fill="#fff">{share * 100:.1f}%</text></svg>')


def _fmt_delta(d: PairedDelta, value: float, currency: str) -> str:
    if d.metric in ("revenue_per_session", "rival_revenue_per_session"):
        return ("+" if value >= 0 else "−") + display_price(round(abs(value)), currency)
    if d.metric in ("conversion", "add_to_cart_rate"):
        return f"{value * 100:+.1f} pt"
    if d.metric == "seconds":
        return f"{value:+.0f} s"
    return f"{value:+.1f}"


def _forest(deltas: list[PairedDelta], currency: str) -> str:
    """Each measure's paired difference (dot) and 95 % interval (bar) around zero, on its own scale."""
    w, left, right, row_h = 760, 200, 150, 44
    plot = w - left - right
    h = row_h * len(deltas) + 10
    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="paired differences" xmlns="http://www.w3.org/2000/svg">']
    for i, d in enumerate(deltas):
        lo, hi = d.ci_low, d.ci_high
        span = max(1e-9, abs(d.diff), abs(lo or 0), abs(hi or 0)) * 1.2
        y = 6 + i * row_h + row_h / 2

        def x(v: float) -> float:
            return left + (v / span + 1) / 2 * plot

        sure = lo is not None and hi is not None and (lo > 0 or hi < 0)
        good = d.diff > 0 if d.metric != "rival_revenue_per_session" else d.diff < 0
        neutral = d.metric in ("steps", "seconds")
        tone = "#5f6368" if not sure else "#5f6368" if neutral else "#0d9768" if good else "#d03b3b"
        call = "within noise" if not sure else "clearly up" if d.diff > 0 else "clearly down"
        parts.append(f'<line x1="{x(0):.1f}" y1="{y - 14:.1f}" x2="{x(0):.1f}" y2="{y + 14:.1f}" stroke="#c4c7cc"/>')
        parts.append(f'<text x="0" y="{y + 4:.1f}" font-size="13" font-weight="600" fill="#111">{escape(_DELTAS.get(d.metric, d.metric))}</text>')
        if lo is not None and hi is not None:
            parts.append(f'<rect x="{x(min(lo, hi)):.1f}" y="{y - 5:.1f}" width="{max(2.0, abs(hi - lo) / span / 2 * plot):.1f}" '
                         f'height="10" rx="5" fill="{tone}" opacity="0.28"/>')
        parts += [
            f'<circle cx="{x(d.diff):.1f}" cy="{y:.1f}" r="6.5" fill="{tone}" stroke="#fff" stroke-width="2"/>',
            f'<text x="{w}" y="{y - 1:.1f}" font-size="13" font-weight="700" text-anchor="end" fill="#111">{escape(_fmt_delta(d, d.diff, currency))}</text>',
            f'<text x="{w}" y="{y + 14:.1f}" font-size="11" text-anchor="end" fill="{tone}">{call}</text>',
        ]
    parts.append("</svg>")
    return "".join(parts)


def _funnel(variants: list[VariantSummary]) -> str:
    rows: list[str] = []
    for stage, label in _STAGES.items():
        bars = "".join(
            f'<div class="bar"><b><i style="width:{max(0.5, f.share * 100):.1f}%;background:{_color(i)}"></i></b>'
            f'<span>{f.sessions} · {f.share:.0%}</span></div>'
            for i, s in enumerate(variants) for f in s.funnel if f.stage == stage)
        rows.append(f'<div class="frow"><div class="flabel">{label}</div><div>{bars}</div></div>')
    return "".join(rows)


def _outcomes(s: VariantSummary) -> str:
    total = max(1, sum(s.outcomes.values()))
    parts = "".join(f'<i title="{escape(_OUTCOMES.get(k, (k, ""))[0])}: {n}" style="width:{n / total * 100:.2f}%;'
                    f'background:{_OUTCOMES.get(k, (k, _OTHER))[1]}"></i>'
                    for k, n in sorted(s.outcomes.items(), key=lambda kv: list(_OUTCOMES).index(kv[0]) if kv[0] in _OUTCOMES else 99) if n)
    return f'<div class="stack">{parts}</div>'


def _table(header: list[str], rows: list[list[str]], numeric_from: int = 1) -> str:
    head = "".join(f"<th{' class=n' if j >= numeric_from else ''}>{escape(h)}</th>" for j, h in enumerate(header))
    body = "".join("<tr>" + "".join(f"<td{' class=n' if j >= numeric_from else ''}>{escape(c)}</td>" for j, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


_CSS = """
:root{--ink:#111;--muted:#5f6368;--line:#e6e7ea}
*{box-sizing:border-box}body{margin:0;background:#eceef3;color:var(--ink);font:14px/1.55 "Inter","Segoe UI",system-ui,sans-serif}
main{max-width:920px;margin:28px auto;background:#fff;border-radius:22px;overflow:hidden;box-shadow:0 30px 80px -40px rgba(20,20,60,.45)}
.hero{position:relative;overflow:hidden;padding:40px 48px 34px;color:#fff;background:radial-gradient(120% 140% at 0% 0%,#3b2a8f 0%,#141529 55%,#0b0c14 100%)}
.hero:after{content:"";position:absolute;inset:auto -10% -60% 40%;height:140%;background:radial-gradient(closest-side,#eb683455,transparent);pointer-events:none}
.brand{font-weight:800;letter-spacing:-.03em;background:linear-gradient(90deg,#8ab4ff,#f7a072);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero .meta{color:#c9cbe0;font-size:13px}.hero h1{font-size:32px;letter-spacing:-.025em;margin:6px 0 4px}
.verdict{display:inline-block;margin-top:14px;padding:9px 16px;border-radius:999px;font-weight:600;border:1px solid #ffffff33;background:#ffffff14}
.verdict.win{background:#1baf7a33;border-color:#1baf7a88}.verdict.holds{background:#2a78d633;border-color:#2a78d688}
.stores{position:relative;z-index:1;display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-top:22px}
.store{border-radius:16px;padding:14px;background:#ffffff0f;border:1px solid #ffffff1f;display:flex;gap:12px;align-items:center}
.store b{display:block;font-size:14px}.store small{display:block;color:#c9cbe0;font-size:12px}.store .tag{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em}
.body{padding:8px 48px 40px}h2{font-size:18px;letter-spacing:-.01em;margin:30px 0 10px;padding-top:18px;border-top:1px solid var(--line)}
h3{font-size:14px;margin:16px 0 6px}.note{color:var(--muted);font-size:12px}.key{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--muted)}
.key i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}.n{text-align:right;font-variant-numeric:tabular-nums}
.frow{display:grid;grid-template-columns:150px 1fr;gap:10px;align-items:center;margin:4px 0}.flabel{font-size:12.5px;font-weight:600}
.bar{display:grid;grid-template-columns:1fr 78px;gap:8px;align-items:center;margin:2px 0}
.bar b{display:block;height:14px;background:#f2f3f5;border-radius:0 6px 6px 0}.bar i{display:block;height:100%;border-radius:0 6px 6px 0}
.bar span{font-size:10.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.stack{display:flex;height:18px;border-radius:6px;overflow:hidden;gap:2px;margin:4px 0 10px}.stack i{display:block;height:100%}
.qa{border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:10px 0}.qa .q{font-weight:600}
.qa ul{margin:6px 0 0;padding-left:18px;color:var(--muted);font-size:12px}
footer{margin-top:30px;color:var(--muted);font-size:11.5px}.body>h2:first-child{border-top:0}
@media (max-width:640px){main{margin:0;border-radius:0}.hero{padding:28px 18px 24px}.hero h1{font-size:26px}.body{padding:4px 18px 28px}
.frow{grid-template-columns:1fr}table{font-size:11.5px}th,td{padding:6px 4px}}
@media print{body{background:#fff}main{box-shadow:none;margin:0;max-width:none;border-radius:0}.hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}
.brand{background:none;color:#8ab4ff}h2,h3{break-after:avoid}table,svg,.qa{break-inside:avoid}}
@page{size:A4;margin:12mm}
"""


def online_report_html(result: OnlineRunResult, created_at: str = "", thread: AnalystThread | None = None) -> str:
    e = escape
    cur = result.currency
    v = result.variants
    tone, headline = verdict(result)
    stores = "".join(
        f'<div class="store">{_ring(s.conversion, _color(i))}<div><span class="tag" style="color:{_color(i)}">'
        f'{"Control" if i == 0 and len(v) > 1 else f"Variant {chr(65 + i)}" if len(v) > 1 else "Store"}</span>'
        f'<b>{e(s.site_name)}</b><small>{s.purchases} orders of {s.sessions} visits</small>'
        f'<small>{e(display_price(round(s.revenue_per_session), cur))} per visit · {e(display_price(round(s.revenue), cur))} in all</small></div></div>'
        for i, s in enumerate(v))
    key = "".join(f'<span><i style="background:{_color(i)}"></i>{e(s.site_name)}</span>' for i, s in enumerate(v))
    numbers = _table([""] + [s.site_name for s in v], [
        ["Visits"] + [str(s.sessions) for s in v],
        ["Orders"] + [f"{s.purchases} ({s.conversion:.1%})" for s in v],
        ["Revenue per visit"] + [display_price(round(s.revenue_per_session), cur) for s in v],
        ["Average order"] + [display_price(round(s.aov), cur) if s.purchases else "–" for s in v],
        ["Added to cart"] + [f"{s.add_to_cart_rate:.1%}" for s in v],
        ["Cart abandonment"] + [f"{s.cart_abandonment:.1%}" for s in v],
        ["Bounce"] + [f"{s.bounce_rate:.1%}" for s in v],
        ["Clicks per visit"] + [f"{s.avg_steps:.1f}" for s in v],
        ["Time per visit"] + [f"{s.avg_seconds:.0f} s" for s in v],
        ["Used search"] + [f"{s.search_share:.1%}" for s in v],
    ])
    compare = "".join(
        f"<h3>{e(c.site_name)} against {e(v[0].site_name)}</h3>"
        f'<p class="note">Orders won {c.won} · lost {c.lost} · visits that ended differently {c.changed} (same shoppers)</p>'
        + _forest(c.deltas, cur)
        for c in result.comparisons)
    outcomes = "".join(f"<h3>{e(s.site_name)}</h3>{_outcomes(s)}"
                       + (f'<p class="note">Left without buying from: {e(", ".join(f"{x.page} ({x.sessions})" for x in s.exits[:6]))}</p>' if s.exits else "")
                       for s in v)
    outcome_key = "".join(f'<span><i style="background:{color}"></i>{label}</span>' for label, color in _OUTCOMES.values())
    friction = "".join(
        f"<h3>{e(s.site_name)}</h3>" + _table(["Friction point", "Visits", "Share", "Money involved"], [
            [f.code.replace("_", " ").capitalize(), str(f.sessions), f"{f.share:.0%}", display_price(f.amount, cur) if f.amount else "–"]
            for f in s.frictions[:8]])
        for s in v if s.frictions)
    survey = _table(["Store", "Answers", "Satisfaction", "Ease", "NPS", "Would return", "Top annoyance"], [
        [s.site_name, str(s.survey.responses), f"{s.survey.satisfaction:.1f}/7", f"{s.survey.ease:.1f}/7", f"{s.survey.nps:+.0f}",
         f"{s.survey.would_return:.0%}", s.survey.frustrations[0] if s.survey.frustrations else "–"]
        for s in v if s.survey]) if any(s.survey for s in v) else ""
    segments = ""
    for dimension in ("device", "mission", "age_group", "arrival"):
        values = list(dict.fromkeys(g.value for s in v for g in s.segments if g.dimension == dimension))
        if len(values) > 1:
            rows = [[value.replace("_", " ")] + [next((f"{g.conversion:.0%} of {g.sessions}" for g in s.segments if g.dimension == dimension and g.value == value), "–")
                               for s in v] for value in values]
            segments += f"<h3>Conversion by {dimension.replace('_', ' ')}</h3>" + _table([dimension.replace("_", " ").capitalize()] + [s.site_name for s in v], rows)
    products = "".join(
        f"<h3>{e(s.site_name)}</h3>" + _table(["Product", "Views", "Added", "Units", "Revenue"], [
            [p.name, str(p.views), str(p.adds), str(p.units), display_price(p.revenue, cur)] for p in s.products[:8]])
        for s in v if s.products)
    searches = "".join(
        f"<h3>{e(s.site_name)}</h3>" + _table(["Search", "Times", "Found nothing", "Ordered"], [
            [q.query, str(q.count), str(q.zero_results), str(q.purchases)] for q in s.searches[:8]])
        for s in v if s.searches)
    questions = ""
    if thread and thread.messages:
        pairs = zip(thread.messages[::2], thread.messages[1::2], strict=False)
        questions = "<h2>Questions about this run</h2>" + (
            f'<p class="note">Answered by {e(thread.model or "a language model")} from this report; each answer lists the report lines it used.</p>'
        ) + "".join(
            f'<div class="qa"><div class="q">{e(q.text)}</div><p>{e(a.text)}</p>'
            + (f"<ul>{''.join(f'<li>{e(f)}</li>' for f in a.figures)}</ul>" if a.figures else "") + "</div>"
            for q, a in pairs if q.role == "user" and a.role == "analyst")
    shoppers = f"{len(result.shoppers)} {_POLICIES.get(result.policy, result.policy).lower()}"
    when = created_at[:16].replace("T", " ") if created_at else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(result.name or " vs ".join(s.site_name for s in v))} · online run report</title><style>{_CSS}</style></head><body><main>
<section class="hero"><div class="meta"><span class="brand">twinstore</span> · online run report · {e(when)}</div>
<h1>{e(result.name or " vs ".join(s.site_name for s in v))}</h1>
<div class="meta">{e(shoppers)}{f" ({e(result.model)})" if result.model else ""} · the same shoppers visited every store{f" · rival shop: {e(result.rival_name)}" if result.rival_name else ""}</div>
<div class="verdict {tone}">{e(headline)}</div>
<div class="stores">{stores}</div></section>
<div class="body">
<h2>Key numbers</h2>{numbers}
{f'<h2>Variants against the control</h2><p class="note">Dot = paired difference on the same shoppers; bar = 95 % bootstrap interval. A bar that crosses the line is within noise.</p>{compare}' if compare else ''}
<h2>Funnel</h2><div class="key">{key}</div>{_funnel(v)}
<h2>How visits ended</h2><div class="key">{outcome_key}</div>{outcomes}
{f'<h2>Friction and dark patterns</h2>{friction}' if friction else ''}
{f'<h2>Exit survey</h2>{survey}' if survey else ''}
{f'<h2>Who converted</h2>{segments}' if segments else ''}
{f'<h2>Top products</h2>{products}' if products else ''}
{f'<h2>What people searched for</h2>{searches}' if searches else ''}
{questions}
<h2>Method and caveats</h2><ul>{''.join(f'<li>{e(n)}</li>' for n in result.notes)}<li>Every store was visited by the same virtual shoppers, so differences are paired; read them rather than the absolute rates.</li></ul>
<footer>Generated by TwinStore from online run {e(result.run_id)}. Print this page to save it as PDF.</footer>
</div></main></body></html>"""
