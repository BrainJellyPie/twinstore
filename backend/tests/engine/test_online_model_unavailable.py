"""A model that never answers ends the run instead of quietly turning it into a rule run."""

import asyncio

import pytest
from pydantic import BaseModel

from store_emulator.domain.online import SessionResult
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import ModelPolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers


class _Model:
    """Answers the first `works` decisions (with the leave option), then fails every call."""

    def __init__(self, works: int) -> None:
        self.works = works
        self.calls = 0

    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **_: object) -> T:
        self.calls += 1
        if self.calls > self.works:
            raise ConnectionError("Connection refused")
        leave = next(line for line in user_prompt.splitlines() if "Close the tab" in line)
        return response_model.model_validate({"option": int(leave[1:leave.index("]")]), "thought": "Not today."})


def _visits(policy: ModelPolicy, count: int) -> list[SessionResult]:
    site = build_site("toy_store", site_id="dead")
    site = site.model_copy(update={"options": site.options.model_copy(update={"welcome_popup": "none", "cookie_banner": False})})
    shoppers = sample_shoppers(site, count, seed=1, missions={"purchase": 1.0}, mobile_share=0.0)

    async def go() -> list[SessionResult]:
        return [await run_session(site, s, policy, seed=2, max_steps=4, render=False) for s in shoppers]
    return asyncio.run(go())


def test_a_model_that_never_answers_ends_the_run_with_its_error() -> None:
    model = _Model(works=0)
    with pytest.raises(ConnectionError, match="Connection refused"):
        _visits(ModelPolicy(model, vision=False), 5)
    assert model.calls == 6  # the sixth unanswered decision in a row stops it


def test_a_model_that_has_answered_falls_back_to_rules_when_a_call_fails() -> None:
    model = _Model(works=1)
    sessions = _visits(ModelPolicy(model, vision=False), 6)
    assert sessions[0].steps[0].source == "model"
    later = [step for s in sessions[1:] for step in s.steps if step.choice is not None]
    assert later and all(step.source == "fallback" and "Connection refused" in step.error for step in later)
