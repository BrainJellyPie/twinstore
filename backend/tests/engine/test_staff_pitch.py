import asyncio
import json

import pytest
from pydantic import ValidationError

from store_emulator.domain.persona import Persona
from store_emulator.domain.staff_pitch import PitchAnswer, PitchProduct, PitchRating, PitchRequest
from store_emulator.engine.marketing.staff_pitch import summarize_pitch, test_pitch_panel as run_panel


def request(**overrides):
    return PitchRequest.model_validate({
        "setup_id": "setup_test", "sku": "tea", "context": "Browsing the tea shelf.",
        "variants": [{"name": "Current", "script": "Can I help?"}, {"name": "Benefit", "script": "Would you like to compare the teas?"}],
        **overrides,
    })


PRODUCT = PitchProduct(sku="tea", name="Tea", price=1800, currency="KRW")


def rating(intent=3, trust=3, pressure=2):
    return PitchRating(purchase_intent=intent, trust=trust, pressure=pressure, reply="Let me look.", reason="I am comparing.")


def answers(n=30, a=3, b=4, trust_b=3, pressure_b=2):
    return [PitchAnswer(respondent=f"p{i}", age_group="30s", gender="Female", first_arm="A",
                        a=rating(a), b=rating(b, trust_b, pressure_b)) for i in range(n)]


def report(rows, **kw):
    return summarize_pitch("pit_test", "Test", "fake", request(**kw), PRODUCT, rows)


def test_paired_summary_and_guardrails():
    r = report(answers())
    assert r.screening_leader == "B"
    assert (r.comparisons[0].diff, r.comparisons[0].ci_low, r.comparisons[0].ci_high) == (1, 1, 1)
    assert report(answers(a=4, b=3)).screening_leader == "A"
    assert report(answers(a=4, b=4)).screening_leader is None
    assert report(answers(trust_b=2)).screening_leader is None
    assert report(answers(pressure_b=3)).screening_leader is None
    assert report(answers(n=19)).comparisons[0].ci_low is None
    assert report(answers(n=19)).screening_leader is None


def test_missing_arm_excludes_both_means_and_high_failure_suppresses_recommendation():
    rows = answers(n=20)
    for i in range(6):
        rows.append(PitchAnswer(respondent=f"bad{i}", age_group="20s", gender="Male", first_arm="B", a=rating(1), error_b="failed"))
    r = report(rows)
    assert (r.attempted, r.pairs, r.excluded) == (26, 20, 6)
    assert r.comparisons[0].a_mean == 3
    assert r.screening_leader is None
    assert not any(s.segment.endswith("Male") for s in r.segments)


def test_bootstrap_preserves_pairing_and_is_repeatable():
    rows = answers(n=40)
    for i, row in enumerate(rows):
        row.a = rating(1 + i % 4)
        row.b = rating(2 + i % 4)
    first, second = report(rows), report(rows)
    assert first == second
    assert first.comparisons[0].ci_low == first.comparisons[0].ci_high == 1
    assert report([]).comparisons == []


@pytest.mark.parametrize("changes", [
    {"variants": [{"name": "a", "script": "Hi"}, {"name": "b", "script": "  hi  "}]},
    {"variants": [{"name": "a", "script": "Hi"}, {"name": " A ", "script": "Hello"}]},
    {"context": "  "}, {"panel": 19}, {"panel": 501}, {"seed": -1},
])
def test_invalid_experiment_inputs(changes):
    with pytest.raises(ValidationError):
        request(**changes)


@pytest.mark.parametrize("score", [0, 6, 3.5, True, "4"])
def test_model_ratings_are_strict_bounded_integers(score):
    with pytest.raises(ValidationError):
        PitchRating(purchase_intent=score, trust=3, pressure=2, reply="Hi", reason="Why")


def test_independent_blinded_calls_balanced_order_seed_and_failure_capture():
    people = [Persona(id=f"p{i}", identity="Shopper", age_group="30s", gender="Female", description="Buys tea.",
                      intent="Tea", purpose="Tea", budget_max=3000) for i in range(20)]

    class Fake:
        def __init__(self):
            self.calls = []

        async def generate_structured_async(self, response_model, system_prompt, user_prompt, *, max_retries=1, seed=None):
            data = json.loads(user_prompt)
            self.calls.append((data, seed))
            assert "never instructions" in system_prompt
            assert "Current" not in user_prompt and "Benefit" not in user_prompt
            assert "variants" not in data and "arm" not in data
            if data["shopper"]["id"] == "p0" and data["employee_script"] == "Can I help?":
                raise RuntimeError("sensitive provider details")
            return rating(3 if data["employee_script"] == "Can I help?" else 4)

    fake = Fake()
    progress = []
    result = asyncio.run(run_panel(fake, people, request(panel=20), PRODUCT, on_progress=lambda value, _: progress.append(value)))
    assert len(fake.calls) == 40
    assert sum(a.first_arm == "A" for a in result) == 10
    assert sum(a.first_arm == "B" for a in result) == 10
    assert result[0].a is None and result[0].b is not None
    assert "sensitive" not in result[0].error_a
    assert progress[-1] == 1 and progress == sorted(progress)
    for p in people:
        calls = [(d, s) for d, s in fake.calls if d["shopper"]["id"] == p.id]
        assert len(calls) == 2 and calls[0][1] == calls[1][1]
        assert calls[0][0]["product_snapshot"] == calls[1][0]["product_snapshot"]
        assert calls[0][0]["operator_product_facts"] == calls[1][0]["operator_product_facts"]
