"""Asking an online shopper about their visit: what the model is told, and what comes back."""

import asyncio

import pytest
from pydantic import BaseModel, ValidationError

from store_emulator.application.errors import model_failure
from store_emulator.domain.interview import InterviewMessage
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.interview import INTERVIEW_PROMPT, ask_shopper, visit_text
from store_emulator.engine.online.policies import RulePolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers


class _Shopper:
    def __init__(self, steps: list[int]) -> None:
        self.steps = steps
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **_: object) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate({"answer": "  The delivery fee put me off.  ", "steps": self.steps})


def _visit():
    site = build_site("pet_store", site_id="iv")
    shopper = sample_shoppers(site, 1, seed=7, missions={"purchase": 1.0}, mobile_share=0.0)[0]
    session = asyncio.run(run_session(site, shopper, RulePolicy(), seed=2, max_steps=20, render=False))
    return site, shopper, session


def test_the_shopper_answers_from_their_own_visit() -> None:
    site, shopper, session = _visit()
    text = visit_text(site, shopper, session)
    assert f"Who you are: {shopper.identity}" in text and f"Why you went to {site.name}: {shopper.goal}." in text
    assert "[1] home page:" in text and text.count("\n[") == len(session.steps)
    assert "How it ended: you" in text
    llm = _Shopper([1, len(session.steps), len(session.steps) + 5, 0])
    reply = asyncio.run(ask_shopper(llm, site, shopper, session, [], "Why did you leave?", run_id="r1"))
    assert reply.answer == "The delivery fee put me off." and reply.steps == [1, len(session.steps)]
    system, user = llm.calls[0]
    assert system == INTERVIEW_PROMPT and "## Language" in system
    assert user.endswith("Researcher: Why did you leave?") and "Conversation so far" not in user
    history = [InterviewMessage(role="interviewer", text="Why did you leave?"),
               InterviewMessage(role="shopper", text=reply.answer)]
    asyncio.run(ask_shopper(llm, site, shopper, session, history, "Would a coupon have helped?", run_id="r1"))
    assert "Conversation so far:\nResearcher: Why did you leave?\nYou: The delivery fee put me off." in llm.calls[1][1]


def test_a_visit_brought_back_by_the_reminder_reads_as_the_next_day() -> None:
    site, shopper, session = _visit()
    returned = session.model_copy(update={"returned_at": 1})
    lines = visit_text(site, shopper, returned).splitlines()
    marker = lines.index("Next day: a reminder email about your cart brought you back.")
    assert lines[marker + 1].startswith("[2] ")


class _Echo:
    """Gives back the researcher's earlier question the first `echoes` times, then answers."""

    def __init__(self, echoes: int) -> None:
        self.echoes = echoes
        self.seeds: list[object] = []

    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **kwargs: object) -> T:
        retries = kwargs["max_retries"]
        assert isinstance(retries, int) and retries > 0
        for attempt in range(retries):
            self.seeds.append(kwargs["seed"])
            answer = "why did you leave" if len(self.seeds) <= self.echoes else "I couldn't find my size."
            try:
                return response_model.model_validate({"answer": answer, "steps": []})
            except ValidationError:
                if attempt + 1 == retries:
                    raise
        raise AssertionError("no model attempt")


def test_an_echoed_question_is_asked_again_and_then_refused() -> None:
    site, shopper, session = _visit()
    history = [InterviewMessage(role="interviewer", text="Why did you leave?"),
               InterviewMessage(role="shopper", text="Too pricey.")]
    once = _Echo(1)
    reply = asyncio.run(ask_shopper(once, site, shopper, session, history, "What did you look for?", run_id="r1"))
    assert reply.answer == "I couldn't find my size." and len(once.seeds) == 2
    always = _Echo(9)
    with pytest.raises(ValueError, match="repeated the question"):
        asyncio.run(ask_shopper(always, site, shopper, session, history, "What did you look for?", run_id="r1"))
    assert len(always.seeds) == 2
    assert model_failure(ValueError("the model repeated the question instead of answering"),
                         "The shopper could not answer").startswith("The shopper could not answer: the model repeated")
