"""Questions about a finished online run, answered by a language model from the run's own numbers.

`online_facts` turns the run's report into a fact sheet (each store's visits, orders, money and funnel, how visits
ended and where people left, friction, the exit survey, ads, the rival shop, paired differences with intervals,
segments, products and searches); the analyst of the physical store (engine/run_analyst) answers from it with the
prompt below and keeps only the figures that appear in the sheet.
"""

from collections.abc import Callable, Sequence

from store_emulator.domain.interview import AnalystMessage
from store_emulator.domain.online import OnlineRunResult, VariantSummary
from store_emulator.engine.prompting import display_price
from store_emulator.engine.run_analyst import RunAnswer, StructuredLLM, answer_run_question, suggest_run_questions

ONLINE_ANALYST_PROMPT = """You are an e-commerce analyst answering a shop owner's questions about one simulated
online run: virtual shoppers visited one or more versions of a web shop (the first is the control), the same
shoppers in every version. The fact sheet below is everything the run measured. Answer only from it: quote its
numbers, compare the versions, and say what they suggest, as a hypothesis when it is one. A difference whose 95 %
interval includes zero is not clear. If the sheet cannot answer the question, say "The run does not show that" and
name what would (watching visits, asking a shopper, another variant or more shoppers).
Answer the owner's latest question; do not repeat a question as your answer.
Copy the sheet lines you used into figures, exactly as written. Use [] for absent figures or follow_ups, not null.
Plain sentences, no markdown. Write in English."""

ONLINE_STARTER_PROMPT = """You help a shop owner start reading one simulated online run. From the fact sheet, write three
short questions worth asking about what stands out: a store version, funnel step, exit page, friction point, search or
shopper group whose numbers are unusual compared with the rest. Name it as written in the sheet, and ask questions the
sheet can answer or that point to what would explain them. One sentence each, no numbers in the question. Write in
English."""

_DELTA_NAMES = {"conversion": "conversion", "revenue_per_session": "revenue per visit", "add_to_cart_rate": "add-to-cart rate",
                "steps": "clicks per visit", "seconds": "seconds per visit", "satisfaction": "satisfaction (1-7)",
                "recommend": "likelihood to recommend (0-10)", "rival_revenue_per_session": "rival's revenue per visit"}
_MONEY = {"revenue_per_session", "rival_revenue_per_session"}
_SHARES = {"conversion", "add_to_cart_rate"}


def _store_lines(s: VariantSummary, money: Callable[[float], str]) -> list[str]:
    lines = [
        f"{s.site_name}: visits {s.sessions}, orders {s.purchases} ({s.conversion:.1%}), revenue {money(s.revenue)}, "
        f"revenue per visit {money(s.revenue_per_session)}, average order {money(s.aov)}, added to cart "
        f"{s.add_to_cart_rate:.1%}, cart abandonment {s.cart_abandonment:.1%}, bounce {s.bounce_rate:.1%}, "
        f"clicks per visit {s.avg_steps:.1f}, seconds per visit {s.avg_seconds:.0f}, used search {s.search_share:.1%}, "
        f"searches that found nothing {s.zero_result_searches}.",
        f"{s.site_name} funnel: " + "; ".join(f"{f.stage} {f.sessions} ({f.share:.0%})" for f in s.funnel) + ".",
        f"{s.site_name} visits ended: " + "; ".join(f"{k} {v}" for k, v in sorted(s.outcomes.items(), key=lambda kv: -kv[1])) + ".",
    ]
    if s.exits:
        lines.append(f"{s.site_name} pages where shoppers left without buying: "
                     + "; ".join(f"{e.page} {e.sessions}" for e in s.exits[:6]) + ".")
    if s.frictions:
        lines.append(f"{s.site_name} friction: " + "; ".join(
            f"{f.code} in {f.sessions} visits ({f.share:.0%}){f' worth {money(f.amount)}' if f.amount else ''}"
            for f in s.frictions[:8]) + ".")
    if s.survey:
        v = s.survey
        lines.append(f"{s.site_name} exit survey ({v.responses} answers): satisfaction {v.satisfaction:.1f}/7, ease "
                     f"{v.ease:.1f}/7, NPS {v.nps:+.0f}, would return {v.would_return:.0%}"
                     + (f", top annoyance: {v.frustrations[0]}" if v.frustrations else "") + ".")
    for ad in s.ads[:4]:
        lines.append(f"{s.site_name} ad {ad.name} ({ad.placement}): impressions {ad.impressions}, clicks {ad.clicks} "
                     f"({ad.ctr:.1%}), orders after a click {ad.click_conversions}, cost {money(ad.cost)}"
                     + (f", ROAS {ad.roas:.2f}" if ad.roas is not None else "") + ".")
    if s.recovery:
        r = s.recovery
        lines.append(f"{s.site_name} cart reminder: emails {r.emails}, came back {r.returned}, recovered orders "
                     f"{r.recovered}, recovered revenue {money(r.revenue)}, discount given {money(r.discount)}.")
    if s.rival:
        r = s.rival
        lines.append(f"{s.site_name} lost to the rival shop: left without buying {r.left}, tried the rival {r.went}, "
                     f"bought there {r.bought}, rival revenue {money(r.revenue)}.")
    segments: dict[str, list[str]] = {}
    for g in s.segments:
        segments.setdefault(g.dimension, []).append(f"{g.value} {g.sessions} visits {g.conversion:.0%}")
    for dimension, rows in segments.items():
        if len(rows) > 1:
            lines.append(f"{s.site_name} conversion by {dimension}: " + "; ".join(rows) + ".")
    if s.products:
        lines.append(f"{s.site_name} top products (views / adds / units / revenue): " + "; ".join(
            f"{p.name} {p.views}/{p.adds}/{p.units}/{money(p.revenue)}" for p in s.products[:8]) + ".")
    if s.searches:
        lines.append(f"{s.site_name} searches (count / found nothing / ordered): " + "; ".join(
            f"'{q.query}' {q.count}/{q.zero_results}/{q.purchases}" for q in s.searches[:8]) + ".")
    return lines


def online_facts(result: OnlineRunResult) -> str:
    """The run's report as a fact sheet a model can answer from (and a reader can check against)."""
    def money(amount: float) -> str:
        return display_price(round(amount), result.currency)

    stores = [s.site_name for s in result.variants]
    lines = [f"Run: {result.name or ' vs '.join(stores)}. Shoppers: {len(result.shoppers)} ({result.policy} shoppers). "
             f"Stores: {'; '.join(stores)} (the first is the control)."]
    if result.rival_name:
        lines.append(f"Rival shop: {result.rival_name}.")
    for s in result.variants:
        lines.extend(_store_lines(s, money))
    for c in result.comparisons:
        def fmt(metric: str, value: float) -> str:
            if metric in _MONEY:
                return ("+" if value >= 0 else "-") + money(abs(value))
            if metric in _SHARES:
                return f"{value * 100:+.1f} pt"
            return f"{value:+.1f}"
        rows: list[str] = []
        for d in c.deltas:
            interval = f" [{fmt(d.metric, d.ci_low)}, {fmt(d.metric, d.ci_high)}]" if d.ci_low is not None and d.ci_high is not None else ""
            rows.append(f"{_DELTA_NAMES.get(d.metric, d.metric)} {fmt(d.metric, d.diff)}{interval}")
        lines.append(f"{c.site_name} minus control (same shoppers, 95 % interval): " + "; ".join(rows) + ".")
        lines.append(f"{c.site_name} vs control: orders won {c.won}, lost {c.lost}, visits that ended differently {c.changed}.")
        biggest = [g for g in sorted(c.segments, key=lambda g: -abs(g.conversion_diff)) if g.conversion_diff][:4]
        if biggest:
            lines.append(f"{c.site_name} conversion difference by segment: " + "; ".join(
                f"{g.dimension} {g.value} {g.conversion_diff * 100:+.1f} pt (n {g.n})" for g in biggest) + ".")
    lines.extend(result.notes[:4])
    return "\n".join(lines)


async def answer_online_question(llm: StructuredLLM, result: OnlineRunResult, question: str,
                                 history: Sequence[AnalystMessage], seed: int = 0) -> RunAnswer:
    return await answer_run_question(llm, online_facts(result), question, history, seed=seed, prompt=ONLINE_ANALYST_PROMPT)


async def suggest_online_questions(llm: StructuredLLM, result: OnlineRunResult) -> list[str]:
    return await suggest_run_questions(llm, online_facts(result), prompt=ONLINE_STARTER_PROMPT)
