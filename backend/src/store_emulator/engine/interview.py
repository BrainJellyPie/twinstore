"""Shopper journeys and post-trip interviews.

`build_journey` turns a simulated trip into numbered steps (walking collapsed, thoughts kept) plus the
products on every shelf face the shopper stopped at. `ask_shopper` lets a language model answer an
interviewer's question as that shopper: in the first person, from the persona and the trip only,
citing the steps it refers to — so "why didn't you buy the green tea?" is answered from what the
shopper actually saw and did, and "I didn't notice it" is a valid answer.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Protocol

from pydantic import BaseModel, Field

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.interview import InterviewMessage, Journey, JourneyStep, ShelfItem
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, stable_seed
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
        steps.append(JourneyStep(
            index=len(steps) + 1, time=_clock(customer.arrival_time, e.elapsed_sec), elapsed_sec=e.elapsed_sec,
            action=e.action, rack_id=e.target_rack, rack=(rack.rack_name or rack.id) if rack else "", face=face,
            product_sku=e.product_sku, product_name=e.product_name, price=e.price, quantity=e.quantity, origin=e.origin,
            thought=e.description.strip(), duration=e.duration, x=e.x, y=e.y,
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
- Put the numbers of the trip steps your answer is about in `steps` (empty if none).
- Write in English."""


class ShopperReply(BaseModel):
    answer: str = Field(max_length=900)
    steps: list[int] = Field(default_factory=list[int], max_length=12)


def trip_text(journey: Journey, store: Store) -> str:
    p = journey.persona
    cur = journey.currency
    racks = {r.id: r for r in store.racks}
    budget = f"{display_price(p.budget_min, cur)}–{display_price(p.budget_max, cur)}" if p.budget_max else "not fixed"
    lines = [
        f"Who you are: {p.identity}, {p.age_group}, {p.gender}. {p.description}",
        f"Why you came: {p.purpose or p.intent}. Budget for this trip: {budget}.",
        f"Habits: {p.behavior_tendency}" if p.behavior_tendency else "",
        f"Products you usually buy: {', '.join(p.usual_products[:8])}." if p.usual_products else "",
        f"Your trip ({journey.arrival_time} to {journey.leave_time}):",
    ]
    for s in journey.steps:
        where = f" at {s.rack}{f' ({s.face} side)' if s.face else ''}" if s.rack else ""
        what = f" {s.product_name} ×{s.quantity} for {display_price(s.price, cur)} ({s.origin})" if s.product_name else ""
        thought = f' — thinking: "{s.thought}"' if s.thought else ""
        lines.append(f"[{s.index}] {s.time} {s.action.value}{where}{what}{thought}")
    lines.append(f"You spent {display_price(journey.total_spent, cur)} on {journey.units} item(s).")
    if journey.shelves:
        lines.append("Shelves you stopped at:")
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
    reply = await llm.generate_structured_async(
        ShopperReply, INTERVIEW_PROMPT, user, max_retries=1,
        seed=stable_seed("interview", journey.run_id, journey.persona.id, len(history)),
    )
    valid = {s.index for s in journey.steps}
    return reply.model_copy(update={"answer": reply.answer.strip(), "steps": [s for s in reply.steps if s in valid]})
