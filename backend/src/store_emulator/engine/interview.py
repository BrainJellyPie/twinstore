"""Shopper journeys and post-trip interviews.

`build_journey` turns a simulated trip into numbered steps (walking collapsed, thoughts kept) plus the
products on every shelf face the shopper stopped at. `ask_shopper` lets a language model answer an
interviewer's question as that shopper: in the first person, from the persona and the trip only,
citing the steps it refers to — so "why didn't you buy the green tea?" is answered from what the
shopper actually saw and did, and "I didn't notice it" is a valid answer.
"""

import json
import unicodedata
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Literal, Protocol

from instructor.core.exceptions import InstructorRetryException
from litellm.exceptions import BadRequestError
from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.interview import (
    InterviewMessage,
    Journey,
    JourneyStep,
    ShelfItem,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, stable_seed
from store_emulator.engine.llm_client import is_context_overflow
from store_emulator.engine.prompting import display_price

MAX_SHELF_ITEMS = 16


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


def _clock(arrival: str, elapsed: int) -> str:
    try:
        t = datetime.strptime(arrival, "%H:%M:%S") + timedelta(seconds=elapsed)
    except ValueError:
        return arrival
    return t.strftime("%H:%M:%S")


def build_journey(run_id: str, customer: CustomerResult, persona: Persona, store: Store, currency: str) -> Journey:
    racks = {r.id: r for r in store.racks}
    steps: list[JourneyStep] = []
    stops: dict[str, set[str]] = {}
    for e in customer.timeline:
        # Plain walking is the path; a move with a thought or a target is a decision worth showing.
        if e.action == Action.MOVE and not e.description and not e.target_rack:
            continue
        rack = racks.get(e.target_rack)
        face = e.face.value if e.face is not None else ""
        if rack is not None and e.action in (Action.BROWSE, Action.BUY):
            stops.setdefault(rack.id, set()).add(face)
        stocked = rack is not None and any(sl.items and (not face or sl.face.value == face) for sl in rack.slots)
        steps.append(JourneyStep(
            index=len(steps) + 1, time=_clock(customer.arrival_time, e.elapsed_sec), elapsed_sec=e.elapsed_sec,
            action=e.action, rack_id=e.target_rack, rack=(rack.rack_name or rack.id) if rack else "", face=face,
            product_sku=e.product_sku, product_name=e.product_name, price=e.price, quantity=e.quantity, origin=e.origin,
            thought=e.description.strip(), duration=e.duration, x=e.x, y=e.y, sees_products=stocked,
        ))
    shelves: dict[str, list[ShelfItem]] = {}
    for rid, faces in stops.items():
        seen: dict[str, ShelfItem] = {}
        for slot in racks[rid].slots:
            if faces and "" not in faces and slot.face.value not in faces:
                continue
            for item in slot.items:
                seen.setdefault(item.sku, ShelfItem(sku=item.sku, name=item.name, price=item.price,
                                                    regular_price=item.regular_price, promo=item.promo))
        shelves[rid] = list(seen.values())[:MAX_SHELF_ITEMS]
    buys = [e for e in customer.timeline if e.action == Action.BUY]
    return Journey(
        run_id=run_id, persona=persona, day=int(customer.day), arrival_time=customer.arrival_time,
        leave_time=customer.leave_time, engine_type=customer.engine_type, currency=currency,
        total_spent=customer.total_spent, units=sum(e.quantity for e in buys), steps=steps,
        path=[(e.elapsed_sec, e.x, e.y) for e in customer.timeline], shelves=shelves,
    )


INTERVIEW_PROMPT = """You are a shopper who has just left a store, talking to a market researcher. You are the person
described below and you answer as that person: first person, casual and specific, one to four sentences. Your trip is
listed step by step with what went through your mind at each step, followed by what was on the shelves you stopped at.

Rules:
- Answer only from your trip, the shelves you saw and who you are. Do not invent stops, products, prices or events.
- If you did not see or notice something, say so plainly ("I didn't go to that aisle", "I didn't notice it").
- You may explain your reasons with your tastes, budget, habits and mood as described, as a real person would.
- Prices are those on the shelf tags. Do not mention that you are simulated, a model or an AI.
- Put the numbers of the trip steps your answer is about in `steps` ([] if none, not null).
- Write in English."""


class ShopperReply(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer: str = Field(min_length=1, max_length=900)
    steps: list[int] = Field(default_factory=list[int], max_length=12)

    @field_validator("steps", mode="before")
    @classmethod
    def _absent_steps(cls, value: object) -> object:
        return [] if value is None else value


def trip_text(journey: Journey, store: Store, *, observer: bool = False) -> str:
    """The trip as the shopper remembers it ("you"), or as a researcher reads it (`observer`, "they")."""
    p = journey.persona
    cur = journey.currency
    racks = {r.id: r for r in store.racks}
    you, your = ("they", "their") if observer else ("you", "your")
    budget = f"{display_price(p.budget_min, cur)}–{display_price(p.budget_max, cur)}" if p.budget_max else "not fixed"
    lines = [
        f"{'The shopper' if observer else 'Who you are'}: {p.identity}, {p.age_group}, {p.gender}. {p.description}",
        f"Why {you} came: {p.purpose or p.intent}. Budget for this trip: {budget}.",
        f"Purchase intent: {p.intent}" if p.intent and p.purpose and p.intent != p.purpose else "",
        f"Habits: {p.behavior_tendency}" if p.behavior_tendency else "",
        f"Preferred categories: {', '.join(p.preferred_categories)}" if p.preferred_categories else "",
        f"Products {you} usually buy: {', '.join(p.usual_products[:8])}." if p.usual_products else "",
        f"{your.capitalize()} trip ({journey.arrival_time} to {journey.leave_time}):",
    ]
    for s in journey.steps:
        where = f" at {s.rack}{f' ({s.face} side)' if s.face else ''}" if s.rack else ""
        what = f" {s.product_name} ×{s.quantity} for {display_price(s.price, cur)} ({s.origin})" if s.product_name else ""
        thought = f' — thinking: "{s.thought}"' if s.thought else ""
        lines.append(f"[{s.index}] {s.time} {s.action.value}{where}{what}{thought}")
    lines.append(f"{you.capitalize()} spent {display_price(journey.total_spent, cur)} on {journey.units} item(s).")
    if journey.shelves:
        lines.append(f"Shelves {you} stopped at:")
        for rid, items in journey.shelves.items():
            name = racks[rid].rack_name if rid in racks else rid
            listed = "; ".join(
                f"{i.name} {display_price(i.price, cur)}"
                + (f" (was {display_price(i.regular_price, cur)})" if i.regular_price else "")
                + (f" [{i.promo}]" if i.promo else "")
                for i in items
            )
            lines.append(f"- {name}: {listed}")
    return "\n".join(line for line in lines if line)


async def ask_shopper(
    llm: StructuredLLM, journey: Journey, store: Store, history: Sequence[InterviewMessage], question: str,
) -> ShopperReply:
    convo = "\n".join(f"{'Researcher' if m.role == 'interviewer' else 'You'}: {m.text}" for m in history[-12:])
    user = f"{trip_text(journey, store)}\n\n{('Conversation so far:\n' + convo + '\n\n') if convo else ''}Researcher: {question}"
    reply = await llm.generate_structured_async(  # a second retry: models now and then put the answer outside the JSON
        ShopperReply, INTERVIEW_PROMPT, user, max_retries=2,
        seed=stable_seed("interview", journey.run_id, journey.persona.id, len(history)),
    )
    valid = {s.index for s in journey.steps}
    return reply.model_copy(update={"answer": reply.answer.strip(), "steps": [s for s in reply.steps if s in valid]})


FOLLOW_UP_PROMPT = """You are an experienced qualitative market researcher interviewing a shopper right after their
store trip. You see the shopper's profile, every step of the trip with what went through their mind, the shelves they
stopped at and the conversation so far. Suggest the three questions you would ask next.

Good questions:
- dig into something specific: a product they bought or put back, a shelf they stopped at without buying, a price or
  promotion they saw, a reason or feeling in their last answer, a gap between their plan and what they did;
- name the product, shelf or price they are about, in plain words;
- are short (at most 14 words), open, neutral and not leading: one question each, never two joined by "and";
- do not repeat or rephrase anything already asked.
With no conversation yet, open with the most revealing moments of the trip. Write in English."""


class FollowUps(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    questions: list[str] = Field(min_length=1, max_length=6)


async def suggest_follow_ups(
    llm: StructuredLLM, journey: Journey, store: Store, history: Sequence[InterviewMessage],
) -> list[str]:
    """Questions a researcher would ask next, written for this trip and this conversation (deduplicated, at most
    three, none already asked)."""
    convo = "\n".join(f"{'Researcher' if m.role == 'interviewer' else 'Shopper'}: {m.text}" for m in history[-12:])
    user = f"{trip_text(journey, store, observer=True)}\n\n{'Conversation so far:' + chr(10) + convo if convo else 'No questions asked yet.'}"
    ideas = await llm.generate_structured_async(
        FollowUps, FOLLOW_UP_PROMPT, user, max_retries=1,
        seed=stable_seed("follow-ups", journey.run_id, journey.persona.id, len(history)),
    )
    asked = {_norm(m.text) for m in history if m.role == "interviewer"}
    out: list[str] = []
    for q in ideas.questions:
        q = " ".join(q.split()).strip(" -•\"'")
        if not q or len(q) > 200 or _norm(q) in asked or _norm(q) in {_norm(o) for o in out}:
            continue
        out.append(_as_prompt(q))
    return out[:3]


def _as_prompt(text: str) -> str:
    """A question keeps its mark, an instruction ("Walk me through…") its full stop; bare text becomes a question."""
    return text if text.endswith(("?", ".", "!", "？", "。", "！", "؟")) else f"{text}?"


def _norm(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    letters = "".join(c for c in normalized
                      if c.isalnum() or c.isspace() or unicodedata.category(c).startswith("M"))
    return " ".join(letters.split())


RUN_QUESTIONS_PROMPT = """You are a qualitative market researcher planning group interviews with the shoppers of one
simulated store day. From the run's numbers below, suggest the three group questions that would explain the most
important things in it (a shelf many people stopped at without buying, a product bought on impulse, people who left
empty-handed, a price that may have put people off). For each: the question (at most 18 words, open, neutral, one
question), the group to ask (one of: empty_handed, impulse, top_spenders, buyers, all) and in a few words why the run
suggests it. Name shelves and products as listed. Write in English."""

GroupSegmentName = Literal["empty_handed", "impulse", "top_spenders", "buyers", "all"]


class GroupQuestion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=5, max_length=200)
    segment: GroupSegmentName = "all"
    why: str = Field(default="", max_length=160)


class _GroupQuestions(BaseModel):
    questions: list[GroupQuestion] = Field(min_length=1, max_length=6)


def run_text(customers: Sequence[CustomerResult], store: Store, currency: str) -> str:
    """The run in numbers a researcher would look at: who bought, where people stopped without buying, impulse picks."""
    racks = {r.id: r.rack_name for r in store.racks}
    n = len(customers)
    buyers = [c for c in customers if c.purchases]
    stopped: dict[str, int] = {}
    bought_at: dict[str, int] = {}
    impulse: dict[str, int] = {}
    for c in customers:
        browsed = {e.target_rack for e in c.timeline if e.action == Action.BROWSE and e.target_rack}
        bought = {e.target_rack for e in c.purchases if e.target_rack}
        # A planned pick can skip BROWSE but still stops at its shelf. Count
        # each shopper once, regardless of repeated visits or purchase quantity.
        for rack in browsed | bought:
            stopped[rack] = stopped.get(rack, 0) + 1
            if rack in bought:
                bought_at[rack] = bought_at.get(rack, 0) + 1
        for e in c.purchases:
            if e.origin == "impulse" and e.product_name:
                impulse[e.product_name] = impulse.get(e.product_name, 0) + e.quantity
    empty = sum(1 for c in customers if not c.purchases and any(e.action == Action.BROWSE for e in c.timeline))
    average = display_price(round(sum(c.total_spent for c in buyers) / max(1, len(buyers))), currency)
    lines = [(f"Shoppers: {n}; bought something: {len(buyers)} ({len(buyers) / max(1, n):.0%}); "
              f"stopped at a shelf but left empty-handed: {empty}; average spend of buyers: {average}.")]
    shelves = sorted(stopped, key=lambda r: -stopped[r])[:8]
    if shelves:
        lines.append("Shelves where shoppers stopped (stopped / bought there): " + "; ".join(
            f"{racks.get(r, r)} {stopped[r]} / {bought_at.get(r, 0)}" for r in shelves))
    if impulse:
        top = sorted(impulse, key=lambda k: -impulse[k])[:6]
        lines.append("Bought on impulse (units): " + "; ".join(f"{k} {impulse[k]}" for k in top))
    return "\n".join(lines)


async def suggest_group_questions(llm: StructuredLLM, summary: str) -> list[GroupQuestion]:
    ideas = await llm.generate_structured_async(_GroupQuestions, RUN_QUESTIONS_PROMPT, summary, max_retries=2, seed=0)
    out: list[GroupQuestion] = []
    for q in ideas.questions:
        text = " ".join(q.question.split())
        if text and _norm(text) not in {_norm(o.question) for o in out}:
            out.append(q.model_copy(update={"question": _as_prompt(text)}))
    return out[:3]


THEMES_PROMPT = """You code open-ended answers from shopper interviews into themes, as a qualitative researcher would.
Group answers that give the same reason; keep themes distinct and concrete (e.g. "Too expensive for a snack", not
"Price"). Return two to six short theme labels and, for every answer in the order given, the number of its theme
(starting at 0). The assignments list must have exactly one entry per supplied answer, including repeated answers;
do not omit answers or return only one representative per theme. Write in English."""


MAX_THEMES = 6

MERGE_THEMES_PROMPT = """You reconcile themes from smaller batches of shopper interview answers to the same question.
Each entry is a theme label and the number of answers it represents. Merge labels that express the same reason;
keep genuinely different reasons distinct. Return two to six short English theme labels and an assignments list
with exactly one theme index per supplied entry, in its original order, starting at 0. Do not omit entries.
Counts describe respondents, not additional entries. Do not invent reasons absent from the supplied labels."""


class ThemeCoding(BaseModel):
    # Models sometimes return a seventh theme; accept it and fold the smallest ones into "Other" below.
    themes: list[str] = Field(min_length=1, max_length=12)
    assignments: list[int]


def _theme_schema(count: int) -> type[ThemeCoding]:
    return create_model("ThemeCoding", __base__=ThemeCoding, assignments=(list[int], Field(
        description=f"Exactly {count} theme indices, one per answer in its original order",
        json_schema_extra={"minItems": count, "maxItems": count},
    )))


def _theme_assignments(coding: ThemeCoding, count: int) -> tuple[list[str], list[int]]:
    themes: list[str] = []
    indices: dict[int, int] = {}
    for original, label in enumerate(coding.themes):
        label = label.strip()
        if label:
            if label not in themes:
                themes.append(label)
            indices[original] = themes.index(label)
    if not themes:
        themes = ["Other"]
    out: list[int] = []
    other = themes.index("Other") if "Other" in themes else -1
    for i in range(count):
        original = coding.assignments[i] if i < len(coding.assignments) else -1
        k = indices.get(original, -1)
        if k < 0:
            if other < 0:
                themes.append("Other")
                other = len(themes) - 1
            k = other
        out.append(k)
    return themes, out


async def _code_theme_batches(llm: StructuredLLM, question: str, answers: Sequence[str]) -> tuple[list[str], list[int]]:
    listed = "\n".join(f"{i}. {a}" for i, a in enumerate(answers))
    try:
        coding = await llm.generate_structured_async(
            _theme_schema(len(answers)), THEMES_PROMPT, f"Question: {question}\n\nAnswers:\n{listed}", max_retries=2, seed=0,
        )
    except (BadRequestError, InstructorRetryException) as exc:
        error = exc.failed_attempts[-1].exception if isinstance(exc, InstructorRetryException) and exc.failed_attempts else exc
        if len(answers) < 2 or not is_context_overflow(error):
            raise
        middle = len(answers) // 2
        batches = [await _code_theme_batches(llm, question, answers[:middle]),
                   await _code_theme_batches(llm, question, answers[middle:])]
        # Retain every respondent in order, including duplicates. Fold small
        # themes only after recovery, using global respondent counts.
        labels = [themes[k] for themes, codes in batches for k in codes]
        counts = Counter(labels)
        named = list(dict.fromkeys(label for label in labels if label != "Other"))
        if len(named) > 1:
            entries = [{"label": label, "count": counts[label]} for label in named]
            merged = await llm.generate_structured_async(
                _theme_schema(len(named)), MERGE_THEMES_PROMPT,
                f"Question: {question}\n\nBatch themes:\n{json.dumps(entries, ensure_ascii=False)}", max_retries=2, seed=0,
            )
            themes, mapped = _theme_assignments(merged, len(named))
        else:
            themes, mapped = named.copy(), list(range(len(named)))
        lookup = dict(zip(named, mapped, strict=True))
        if "Other" in counts:
            if "Other" not in themes:
                themes.append("Other")
            lookup["Other"] = themes.index("Other")
        return themes, [lookup[label] for label in labels]
    return _theme_assignments(coding, len(answers))


async def code_themes(llm: StructuredLLM, question: str, answers: Sequence[str]) -> tuple[list[str], list[int]]:
    """Code every answer, splitting only on context rejection; missing or invalid indices become Other."""
    themes, out = await _code_theme_batches(llm, question, answers)
    if len(themes) > MAX_THEMES:  # keep the largest themes, in their original order; the rest become "Other"
        counts = Counter(out)
        named = [k for k in range(len(themes)) if themes[k] != "Other"]
        keep = sorted(sorted(named, key=lambda k: (-counts[k], k))[: MAX_THEMES - 1])
        remap = {k: i for i, k in enumerate(keep)}
        themes = [themes[k] for k in keep] + ["Other"]
        out = [remap.get(k, len(themes) - 1) for k in out]
    return themes, out
