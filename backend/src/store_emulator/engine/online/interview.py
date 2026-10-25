"""Talking to an online shopper after the visit.

A language model answers a researcher's question as that shopper, in the first person, from who they are and their
visit only: every page with what they clicked and thought, how it ended and what they said in the exit survey. So "why
did you leave at the delivery fee?" is answered from what the shopper actually saw and did, and "I never got that far"
is a valid answer. Written in English like the browsing prompt; the "Language" block keeps the answer in English.
"""

from collections.abc import Sequence
from typing import Protocol

from instructor.core.exceptions import IncompleteOutputException, InstructorRetryException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError

from store_emulator.domain.interview import InterviewMessage
from store_emulator.domain.online import ActionKind, OnlineShopper, OnlineSite, SessionResult
from store_emulator.domain.types import stable_seed
from store_emulator.engine.prompting import display_price

from .policies import OUTCOME_WORDS
from .prompt import EYESIGHT, age_words


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, max_tokens: int | None = None,
    ) -> T: ...


INTERVIEW_PROMPT = """You are an online shopper who has just left a shop's website, talking to a market researcher. You
are the person described below and you answer as that person: first person, casual and specific, one to four sentences.
Your visit is listed step by step: the page you were on, what you clicked and what went through your mind.

Rules:
- Answer only from your visit and who you are. Do not invent pages, products, prices or events.
- Answer the researcher's latest question; do not repeat a question as your answer.
- If you did not see or notice something, say so plainly ("I never opened the cart", "I didn't see a coupon").
- You may explain your reasons with your goal, budget, patience, eyesight and comfort with websites, as a real person
  would.
- Do not mention that you are simulated, a model or an AI.
- Put the numbers of the visit steps your answer is about in `steps` ([] if none, not null).

## Language
Write answer in English."""


_FROM = {"direct": "its address or a bookmark", "search_engine": "a search engine result", "social": "a social media post",
         "email": "the shop's email newsletter"}


class InterviewReply(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer: str = Field(min_length=1, max_length=900)
    steps: list[int] = Field(default_factory=list[int], max_length=12)

    @field_validator("steps", mode="before")
    @classmethod
    def _absent_steps(cls, value: object) -> object:
        return [] if value is None else value


def _words(text: str) -> str:
    return "".join(c for c in text.casefold() if c.isalnum())


def visit_text(site: OnlineSite, shopper: OnlineShopper, session: SessionResult) -> str:
    """The visit as the shopper remembers it, steps numbered from 1."""
    money = site.currency
    lines = [
        f"Who you are: {shopper.identity}, {age_words(shopper.age_group)}, {shopper.gender.lower()}, on a {shopper.device}.",
        shopper.description if shopper.description and shopper.persona_id else "",
        EYESIGHT[shopper.vision],
        f"Why you went to {site.name}: {shopper.goal}.",
        f"Budget: {display_price(shopper.budget, money)}." if shopper.budget else "Budget: no fixed limit.",
        f"You came to the site from {_FROM[shopper.arrival]}.",
        f"Your visit to {site.name}:",
    ]
    for step in session.steps:
        if step.index == session.returned_at:
            lines.append("Next day: a reminder email about your cart brought you back.")
        where = step.page.value.replace("_", " ")
        if step.choice is None:
            lines.append(f"[{step.index + 1}] {where} page")
            continue
        what = (f'searched for "{step.search_text}"' if step.choice.kind == ActionKind.SEARCH
                else f"clicked: {step.choice.label}")
        thought = f' — thinking: "{step.thought}"' if step.thought else ""
        lines.append(f"[{step.index + 1}] {where} page: {what}{thought}")
    lines.append(f"How it ended: {OUTCOME_WORDS[session.outcome].replace('they ', 'you ')}"
                 + (f"; you paid {display_price(session.order_total, money)}." if session.order_total else "."))
    survey = session.survey
    if survey is not None:
        lines.append(f"In the exit survey you gave satisfaction {survey.satisfaction}/7, ease {survey.ease}/7 and "
                     f"{survey.recommend}/10 for recommending the shop"
                     + (f'; biggest annoyance: "{survey.frustration}"' if survey.frustration else "") + ".")
    return "\n".join(line for line in lines if line)


async def ask_shopper(
    llm: StructuredLLM, site: OnlineSite, shopper: OnlineShopper, session: SessionResult,
    history: Sequence[InterviewMessage], question: str, *, run_id: str,
) -> InterviewReply:
    convo = "\n".join(f"{'Researcher' if m.role == 'interviewer' else 'You'}: {m.text}" for m in history[-12:])
    user = (f"{visit_text(site, shopper, session)}\n\n{('Conversation so far:\n' + convo + '\n\n') if convo else ''}"
            f"Researcher: {question}")
    seed = stable_seed("online-interview", run_id, site.id, shopper.id, len(history))
    asked = {_words(m.text) for m in history if m.role == "interviewer"} | {_words(question)}

    class ShopperReply(InterviewReply):
        @field_validator("answer")
        @classmethod
        def _answer_the_question(cls, value: str) -> str:
            if _words(value) in asked:
                raise PydanticCustomError("interview_echo", "the model repeated the question instead of answering. "
                                          "Answer the researcher's latest question in the shopper's first-person voice.")
            return value

    async def answer(seed: int) -> InterviewReply:
        try:
            return await llm.generate_structured_async(
                ShopperReply, INTERVIEW_PROMPT, user, max_retries=2, seed=seed, max_tokens=700,
            )
        except Exception as error:
            cause = (error.failed_attempts[-1].exception
                     if isinstance(error, InstructorRetryException) and error.failed_attempts else error)
            if not isinstance(cause, IncompleteOutputException):
                raise
            return await llm.generate_structured_async(
                ShopperReply, INTERVIEW_PROMPT, user, max_retries=2, seed=seed, max_tokens=1400,
            )

    # Schema validation gives the retry corrective feedback and keeps echoes out of the cache.
    try:
        reply = await answer(seed)
    except Exception as error:
        cause = (error.failed_attempts[-1].exception
                 if isinstance(error, InstructorRetryException) and error.failed_attempts else error)
        if isinstance(cause, ValidationError) and any(e["type"] == "interview_echo" for e in cause.errors()):
            raise ValueError("the model repeated the question instead of answering") from error
        raise
    valid = range(1, len(session.steps) + 1)
    return reply.model_copy(update={"answer": reply.answer.strip(), "steps": [s for s in reply.steps if s in valid]})
