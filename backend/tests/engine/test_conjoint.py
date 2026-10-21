"""Conjoint design and estimation: balanced tasks without repeated profiles, and a logit that recovers the utilities
behind simulated choices."""

import math
import random

import pytest

from store_emulator.domain.marketing import ConjointAttribute, ConjointRequest, ConjointRespondent, ConjointTask
from store_emulator.engine.marketing.conjoint import choice_model, design, estimate, none_share, tasks_text


def test_design_balances_levels_and_avoids_repeated_profiles() -> None:
    plan = design([3, 2, 4], tasks=12, options=3, rng=random.Random(5))
    assert len(plan) == 12 and all(len(task) == 3 for task in plan)
    for task in plan:
        assert len({tuple(p) for p in task}) == 3
        assert len({p[0] for p in task}) == 3 and len({p[2] for p in task}) == 3   # enough levels: no overlap
    for a, levels in enumerate([3, 2, 4]):
        counts = [sum(1 for task in plan for p in task if p[a] == lv) for lv in range(levels)]
        assert max(counts) - min(counts) <= 2


@pytest.mark.parametrize("levels", [[2, 2], [2, 2, 2], [2, 3], [3, 3], [2, 6], [6] * 7])
@pytest.mark.parametrize("options", [2, 3, 4])
@pytest.mark.parametrize("seed", range(12))
def test_design_keeps_options_distinct_at_small_and_large_attribute_limits(levels, options, seed) -> None:
    plan = design(levels, tasks=15, options=options, rng=random.Random(seed))
    assert len(plan) == 15
    for task in plan:
        assert len(task) == options
        assert len({tuple(profile) for profile in task}) == options
        assert all(len(profile) == len(levels) for profile in task)
        assert all(0 <= value < limit for profile in task for value, limit in zip(profile, levels, strict=True))
        if levels == [2, 2] and options == 4:
            assert {tuple(profile) for profile in task} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert plan == design(levels, tasks=15, options=options, rng=random.Random(seed))


def test_tasks_text_and_choice_model() -> None:
    attrs = [ConjointAttribute(name="Sugar", levels=["Regular", "Zero"]), ConjointAttribute(name="Pack", levels=["PET", "Can"])]
    text = tasks_text(attrs, [149, 199], "USD", [[[0, 1, 0], [1, 0, 1]]], none_option=True)
    assert "Task 1:" in text and "A: Sugar: Regular · Pack: Can · Price: $1.49" in text and "none: buy none of these" in text
    model = choice_model(2, 2, none_option=False)
    assert model.model_validate({"task_1": "A", "task_2": "B"}).model_dump()["task_2"] == "B"
    with pytest.raises(ValueError):
        model.model_validate({"task_1": "none", "task_2": "B"})


def test_request_validation() -> None:
    attrs = [{"name": "Sugar", "levels": ["Regular", "Zero"]}]
    with pytest.raises(ValueError, match="two price levels"):
        ConjointRequest.model_validate({"product": "tea", "attributes": attrs, "prices": [100]})
    with pytest.raises(ValueError, match="at least two attributes"):
        ConjointRequest.model_validate({"product": "tea", "attributes": attrs})
    with pytest.raises(ValueError, match="different names"):
        ConjointRequest.model_validate({"product": "tea", "attributes": [{"name": "Sugar", "levels": ["Zero", "zero"]}], "prices": [1, 2]})
    assert ConjointRequest.model_validate({"product": "tea", "attributes": attrs, "prices": [100, 150]}).tasks == 8


def test_logit_recovers_simulated_part_worths_and_willingness_to_pay() -> None:
    attrs = [ConjointAttribute(name="Size", levels=["330 ml", "500 ml", "1 L"]), ConjointAttribute(name="Brand", levels=["Store", "Known"])]
    prices = [1200, 1600, 2000]
    true = [[0.0, 0.6, 0.9], [0.0, 0.5]]
    slope = -0.002
    rng = random.Random(1)
    people: list[ConjointRespondent] = []
    for r in range(200):
        tasks: list[ConjointTask] = []
        for profiles in design([3, 2, 3], 10, 3, rng):
            utilities = [sum(true[a][p[a]] for a in range(2)) + slope * prices[p[2]] + 3.0 for p in profiles] + [-0.5]
            gumbel = [u - math.log(-math.log(rng.random())) for u in utilities]
            choice = max(range(4), key=lambda i: gumbel[i])
            tasks.append(ConjointTask(profiles=profiles, choice=None if choice == 3 else choice))
        people.append(ConjointRespondent(respondent=f"p{r}", age_group="20s" if r % 2 else "30s", gender="F", tasks=tasks))
    est = estimate(people, attrs, prices, none_option=True, draws=60, seed=3)
    assert est is not None
    size = [p for p in est.part_worths if p.attribute == "Size"]
    assert [round(p.utility, 1) for p in size] == pytest.approx([-0.5, 0.1, 0.4], abs=0.11)
    assert all(p.ci_low <= p.utility <= p.ci_high for p in est.part_worths)
    assert est.price_slope == pytest.approx(slope, rel=0.15)
    one_litre = size[2]
    assert one_litre.wtp == pytest.approx(450, rel=0.2) and one_litre.wtp_low is not None and one_litre.wtp_low < one_litre.wtp < (one_litre.wtp_high or 0)
    assert sum(i.importance for i in est.importances) == pytest.approx(1, abs=1e-3)
    assert est.fit.hit_rate > est.fit.chance_rate and 0 < est.fit.mcfadden_r2 < 1
    assert {s.segment for s in est.segments} == {"age 20s", "age 30s", "gender F"}
    assert 0 < none_share(people) < 0.3


def test_estimate_without_answers_and_without_price() -> None:
    attrs = [ConjointAttribute(name="Sugar", levels=["Regular", "Zero"]), ConjointAttribute(name="Pack", levels=["PET", "Can"])]
    failed = [ConjointRespondent(respondent="x", age_group="20s", gender="F", error="timeout")]
    assert estimate(failed, attrs, [], none_option=False) is None
    people = [ConjointRespondent(respondent=f"p{i}", age_group="20s", gender="F",
                                 tasks=[ConjointTask(profiles=[[1, 0], [0, 1]], choice=0), ConjointTask(profiles=[[0, 0], [1, 1]], choice=1)])
              for i in range(10)]
    est = estimate(people, attrs, [], none_option=False, draws=20)
    assert est is not None and est.price_slope is None and est.none_utility is None
    sugar = [p for p in est.part_worths if p.attribute == "Sugar"]
    assert sugar[1].utility > 0 > sugar[0].utility and sugar[1].wtp is None
