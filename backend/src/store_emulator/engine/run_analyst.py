"""Questions about a finished run, answered by a language model from the run's own numbers.

`run_facts` turns the run into a compact fact sheet (totals, hours, shelves, products, shopper groups); the model
answers only from it and lists the figures it used, so every claim can be checked against the sheet. A question the
sheet cannot answer gets "the run does not show that" and a pointer to the analysis that would.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.interview import AnalystMessage
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action
from store_emulator.engine.prompting import display_price

TOP = 12


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class RunAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer: str = Field(min_length=1, max_length=1500, description="the answer in two to five plain sentences")
    figures: list[str] = Field(default_factory=list[str], max_length=8,
                               description="the fact-sheet lines the answer rests on, copied as written")
    follow_ups: list[str] = Field(default_factory=list[str], max_length=3, description="up to three next questions")


ANALYST_PROMPT = """You are a retail analyst answering a store manager's questions about one simulated trading day.
The shoppers are synthetic; the fact sheet below is everything the run measured. Answer only from it: quote its
numbers, compare them, and say what they suggest, as a hypothesis when it is one. If the sheet cannot answer the
question, say "The run does not show that" and name what would (a group interview, an A/B test, a scenario run).
Copy the sheet lines you used into figures, exactly as written. Plain sentences, no markdown. Write in English."""


def _hour(clock: str) -> int:
    try:
        return int(clock.split(":", 1)[0])
    except ValueError:
        return -1


def run_facts(customers: Sequence[CustomerResult], personas: Mapping[str, Persona], store: Store, currency: str) -> str:
    """The run as a fact sheet a model can answer from (and a reader can check against)."""
    def money(v: float) -> str:
        return display_price(round(v), currency)

    racks = {r.id: r.rack_name or f"{r.type.value} {r.id[-4:]}" for r in store.racks}
    n = len(customers)
    buyers = [c for c in customers if c.purchases]
    revenue = sum(c.total_spent for c in customers)
    basket_units = sum(c.units_bought for c in buyers) / max(1, len(buyers))
    lines = [(
        f"Visitors: {n}. Buyers: {len(buyers)} ({len(buyers) / max(1, n):.0%}). Revenue: {money(revenue)}. "
        f"Revenue per visitor: {money(revenue / max(1, n))}. Average basket of buyers: "
        f"{money(revenue / max(1, len(buyers)))}, {basket_units:.1f} units."
    )]
    impulse_units = sum(e.quantity for c in customers for e in c.purchases if e.origin == "impulse")
    all_units = sum(c.units_bought for c in customers)
    empty = sum(1 for c in customers if not c.purchases and any(e.action == Action.BROWSE for e in c.timeline))
    walked = sum(1 for c in customers if not any(e.action in (Action.BROWSE, Action.BUY) for e in c.timeline))
    lines.append(f"Impulse units: {impulse_units} of {all_units} ({impulse_units / max(1, all_units):.0%}). "
                 f"Stopped at a shelf but bought nothing: {empty}. Never stopped at a shelf: {walked}.")

    by_hour: dict[int, list[CustomerResult]] = defaultdict(list)
    for c in customers:
        by_hour[_hour(c.arrival_time)].append(c)
    hours = [h for h in sorted(by_hour) if h >= 0]
    if hours:
        lines.append("By arrival hour (visitors / buyers / revenue): " + "; ".join(
            f"{h:02d}h {len(by_hour[h])} / {sum(1 for c in by_hour[h] if c.purchases)} / "
            f"{money(sum(c.total_spent for c in by_hour[h]))}" for h in hours))

    stops: dict[str, int] = defaultdict(int)
    bought: dict[str, int] = defaultdict(int)
    rack_rev: dict[str, int] = defaultdict(int)
    rack_units: dict[str, int] = defaultdict(int)
    prod_rev: dict[str, int] = defaultdict(int)
    prod_units: dict[str, int] = defaultdict(int)
    prod_impulse: dict[str, int] = defaultdict(int)
    for c in customers:
        bought_here = {e.target_rack for e in c.purchases if e.target_rack}
        # A stop is a browse or a buy at the shelf (planned picks can skip the browse step).
        for rack in {e.target_rack for e in c.timeline if e.action == Action.BROWSE and e.target_rack} | bought_here:
            stops[rack] += 1
        for rack in bought_here:
            bought[rack] += 1
        for e in c.purchases:
            line = e.price * e.quantity
            if e.target_rack:
                rack_rev[e.target_rack] += line
                rack_units[e.target_rack] += e.quantity
            name = e.product_name or e.product_sku
            prod_rev[name] += line
            prod_units[name] += e.quantity
            if e.origin == "impulse":
                prod_impulse[name] += e.quantity
    stocked = {r.id for r in store.product_racks}
    shelf_ids = sorted((set(stops) | set(rack_rev)) & stocked, key=lambda r: -rack_rev.get(r, 0))[:TOP]
    if shelf_ids:
        lines.append("Shelves (stopped / bought there / units / revenue / buy rate of those who stopped): " + "; ".join(
            f"{racks.get(r, r)} {stops.get(r, 0)} / {bought.get(r, 0)} / {rack_units.get(r, 0)} / {money(rack_rev.get(r, 0))} / "
            f"{bought.get(r, 0) / max(1, stops.get(r, 0)):.0%}" for r in shelf_ids))
    top_products = sorted(prod_rev, key=lambda k: -prod_rev[k])[:TOP]
    if top_products:
        lines.append("Products by revenue (units / revenue / impulse units): " + "; ".join(
            f"{k} {prod_units[k]} / {money(prod_rev[k])} / {prod_impulse.get(k, 0)}" for k in top_products))

    for label, key in (("age group", "age_group"), ("gender", "gender")):
        groups: dict[str, list[CustomerResult]] = defaultdict(list)
        for c in customers:
            p = personas.get(c.persona_id)
            if p is not None:
                groups[str(getattr(p, key))].append(c)
        if len(groups) > 1:
            lines.append(f"By {label} (visitors / buy rate / revenue per visitor): " + "; ".join(
                f"{g} {len(cs)} / {sum(1 for c in cs if c.purchases) / max(1, len(cs)):.0%} / "
                f"{money(sum(c.total_spent for c in cs) / max(1, len(cs)))}" for g, cs in sorted(groups.items())))
    return "\n".join(lines)


async def answer_run_question(
    llm: StructuredLLM, facts: str, question: str, history: Sequence[AnalystMessage], seed: int = 0,
) -> RunAnswer:
    convo = "\n".join(f"{'Manager' if m.role == 'user' else 'Analyst'}: {m.text}" for m in history[-8:])
    user = f"Fact sheet:\n{facts}\n\n{'Conversation so far:' + chr(10) + convo + chr(10) + chr(10) if convo else ''}Manager: {question.strip()}"
    answer = await llm.generate_structured_async(RunAnswer, ANALYST_PROMPT, user, max_retries=2, seed=seed)
    sheet = facts.casefold()
    figures = [f.strip() for f in answer.figures if f.strip() and f.strip().casefold() in sheet]
    return answer.model_copy(update={"figures": figures[:8], "follow_ups": [q.strip() for q in answer.follow_ups if q.strip()][:3]})


class _Starters(BaseModel):
    questions: list[str] = Field(default_factory=list[str], max_length=8,
                                 description="three short questions a manager would ask about this day")


STARTER_PROMPT = """You help a store manager start reading one simulated trading day. From the fact sheet, write three
short questions worth asking about what stands out: a shelf, product, hour or shopper group whose numbers are unusual
compared with the rest. Name the shelf, product, hour or group as written in the sheet, and ask questions the sheet can
answer or that point to what would explain them. One sentence each, no numbers in the question. Write in English."""


async def suggest_run_questions(llm: StructuredLLM, facts: str) -> list[str]:
    """Three questions read off the fact sheet (what stands out), for an empty analyst thread."""
    reply = await llm.generate_structured_async(_Starters, STARTER_PROMPT, f"Fact sheet:\n{facts}", max_retries=2, seed=0)
    seen: dict[str, str] = {}
    for q in reply.questions:
        text = " ".join(q.split())
        if 8 <= len(text) <= 200:
            seen.setdefault(text.casefold(), text)
    return list(seen.values())[:3]


class DifferenceReading(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=900, description="what B did differently from A, two or three sentences")
    where: str = Field(default="", max_length=1200, description="where the difference came from: shelves, hours, products, groups")
    caveats: str = Field(default="", max_length=600, description="what is within noise or cannot be told from the runs")
    figures: list[str] = Field(default_factory=list[str], max_length=10, description="sheet lines the reading rests on, as written")


DIFFERENCE_PROMPT = """You are a retail analyst explaining why one simulated store day (run B) differs from another
(run A) to a store manager. The paired comparison gives per-shopper differences (B minus A) with 95 % intervals; the
two fact sheets give each run's shelves, hours, products and shopper groups. Say what changed, then where it came
from by comparing the sheets (name at most four shelves, products, hours or groups, each with its one most telling
number), and what is within noise (an interval that includes zero) or cannot be told. Use only these numbers. Copy the lines you used into figures, exactly as written. Plain sentences, no markdown.
Write in English."""


_METRIC_NAMES = {"spend": "spend per shopper", "units": "units per shopper", "bought": "share who bought",
                 "impulse_spend": "impulse spend per shopper", "visit_sec": "visit length", "path_tiles": "walking path"}


def comparison_text(metrics: Sequence[tuple[str, float, float, float, float, float]], currency: str = "USD") -> str:
    """(metric, mean A, mean B, difference, 95 % low, 95 % high) as sheet lines, in the units a manager reads."""
    def fmt(metric: str, v: float, signed: bool = False) -> str:
        sign = "+" if signed and v >= 0 else ""
        if metric in ("spend", "impulse_spend"):
            text = display_price(round(abs(v)), currency)
            return f"{'-' if v < 0 else sign}{text}"
        if metric == "bought":
            return f"{v * 100:+.1f} pt" if signed else f"{v:.1%}"
        if metric == "visit_sec":
            return f"{sign}{v:.0f} s"
        if metric == "path_tiles":
            return f"{sign}{v:.1f} m"
        return f"{sign}{v:.2f}"

    return "\n".join(
        f"{_METRIC_NAMES.get(m, m)}: A {fmt(m, a)}, B {fmt(m, b)}, B minus A {fmt(m, d, True)} "
        f"(95 % interval {fmt(m, lo, True)} to {fmt(m, hi, True)})"
        for m, a, b, d, lo, hi in metrics)


async def explain_difference(
    llm: StructuredLLM, comparison: str, facts_a: str, facts_b: str, labels: tuple[str, str] = ("A", "B"),
) -> DifferenceReading:
    user = (f"Paired comparison (per shopper):\n{comparison}\n\nRun A ({labels[0]}) fact sheet:\n{facts_a}\n\n"
            f"Run B ({labels[1]}) fact sheet:\n{facts_b}")
    reading = await llm.generate_structured_async(DifferenceReading, DIFFERENCE_PROMPT, user, max_retries=2, seed=0)
    sheet = f"{comparison}\n{facts_a}\n{facts_b}".casefold()
    figures = [f.strip() for f in reading.figures if f.strip() and f.strip().casefold() in sheet]
    return reading.model_copy(update={"figures": figures[:10]})
