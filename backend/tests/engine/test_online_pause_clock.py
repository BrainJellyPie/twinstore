"""Background pauses change the recorded clock without changing the shopper's decisions."""
import asyncio

import pytest

from store_emulator.engine.online import session
from store_emulator.engine.online.policies import RulePolicy
from tests.engine.test_online_store import _shoppers, _site


@pytest.mark.parametrize("max_steps", [1, 40])
@pytest.mark.parametrize("reminder", [False, True])
def test_pauses_preserve_choices_patience_and_survey_evidence(monkeypatch, max_steps, reminder):
    site = _site(cart_reminder=reminder)
    shoppers = _shoppers(site, 8, seed=4)

    async def run(pause):
        monkeypatch.setattr(session, "pause_seconds", lambda rng: pause)
        surveys = []

        async def survey(site, shopper, **evidence):
            surveys.append(evidence)
            return None

        visits = [await session.run_session(site, shopper, RulePolicy(), seed=5,
                    max_steps=max_steps, render=False, surveyor=survey) for shopper in shoppers]
        return visits, surveys

    ordinary, evidence = asyncio.run(run(0))
    paused, paused_evidence = asyncio.run(run(10_000))
    assert evidence == paused_evidence
    for before, after in zip(ordinary, paused, strict=True):
        assert before.model_dump(exclude={"seconds", "steps"}) == after.model_dump(exclude={"seconds", "steps"})
        decisions = 0
        for first, second in zip(before.steps, after.steps, strict=True):
            assert first.model_dump(exclude={"seconds"}) == second.model_dump(exclude={"seconds"})
            extra = 10_000 if first.choice is not None else 0
            decisions += bool(extra)
            assert second.seconds == pytest.approx(first.seconds + extra)
        assert after.seconds == pytest.approx(before.seconds + decisions * 10_000)
