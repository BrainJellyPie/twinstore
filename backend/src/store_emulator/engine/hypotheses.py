"""What the synthetic shoppers said, turned into something to test.

A group interview's themes ("prices felt high", "could not find the tea") or the run analyst's last answer become up to
three questions a test can answer, each with the tool that answers it: an A/B test on the simulated day, a shelf test,
or a concept test. Products and shelves are named only as the layout lists them. Answers are hypotheses; the test is
where they are checked.
"""

from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from store_emulator.domain.interview import AnalystMessage, GroupInterview
from store_emulator.domain.store import Store
from store_emulator.engine.prompting import relevant_first

type TestKind = Literal["ab_test", "shelf_test", "concept_test"]


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class Hypothesis(BaseModel):
    question: str = Field(max_length=300, description="the test question, naming listed products or shelves")
    kind: TestKind = "ab_test"
    why: str = Field(default="", max_length=200, description="what the shoppers or the analyst said that it checks")

    @field_validator("why", mode="before")
    @classmethod
    def _optional_reason(cls, value: object) -> object:
        return "" if value is None else value


class _Hypotheses(BaseModel):
    tests: list[Hypothesis] = Field(default_factory=list[Hypothesis], max_length=6)


PROMPT = """Synthetic shoppers of a simulated store day said the things below. Turn them into up to three questions a
test can answer, each with the tool that answers it:
- ab_test: a change on the shelves (price, discount, promotion sign, placement, new package) compared over a whole
  simulated day, e.g. "Would a 1+1 sign on Coca-Cola 500ml sell more than a 20 % discount?";
- shelf_test: whether one product's new pack, price or sign stands out on its shelf;
- concept_test: how shoppers rate product packs or ideas shown as pictures.
Name products and shelves exactly as listed, ask one change per question, and say in a few words what each one checks.
What shoppers said is a hypothesis, not a finding. Use an empty string, not null, when no why explanation is given.
Write in English."""


def _layout(store: Store, hint: str) -> str:
    items: dict[str, tuple[str, str, str]] = {}
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                items.setdefault(item.name, (rack.rack_name, item.name, item.name))
    products = relevant_first(list(items.values()), hint, 80)
    shelves = list(dict.fromkeys(r.rack_name for r in store.product_racks if r.rack_name))
    return f"Shelves: {', '.join(shelves)}\nProducts: {'; '.join(products)}"


def group_text(group: GroupInterview) -> str:
    themes = "; ".join(f"{t.label} ({t.count})" for t in group.themes) or "not coded"
    answers = [a.answer for a in group.answers if a.answer][:12]
    return (f"Group interview question: {group.question}\nThemes (shoppers): {themes}\n"
            "Answers:\n" + "\n".join(f"- {a}" for a in answers))


def analyst_text(messages: Sequence[AnalystMessage]) -> str:
    last = [m for m in messages if m.role == "analyst"][-1:]
    asked = [m for m in messages if m.role == "user"][-1:]
    if not last:
        return ""
    figures = "; ".join(last[0].figures)
    return f"Manager asked: {asked[0].text if asked else ''}\nAnalyst answered: {last[0].text}\nFigures: {figures}"


async def suggest_tests(llm: StructuredLLM, said: str, store: Store) -> list[Hypothesis]:
    reply = await llm.generate_structured_async(
        _Hypotheses, PROMPT, f"{_layout(store, said)}\n\nWhat was said:\n{said}", max_retries=2, seed=0)
    seen: dict[str, Hypothesis] = {}
    for h in reply.tests:
        q = " ".join(h.question.split())
        if len(q) >= 10:
            seen.setdefault(q.casefold(), h.model_copy(update={"question": q, "why": h.why.strip()}))
    return list(seen.values())[:3]
