import math

import pytest
from pydantic import ValidationError

from store_emulator.domain.field_planning import PilotPlanningRequest
from store_emulator.engine.marketing.field_planning import plan_pilot


def request(counts=None, **assumptions):
    return PilotPlanningRequest.model_validate({
        "assumptions": {"minimum_effect": 0.1, "target_power": 0.8, "eligible_per_day": 50,
                        "available_days": 30, **assumptions}, "block_counts": counts or [100],
    })


def test_recommendation_meets_bound_and_previous_even_total_does_not():
    result = plan_pilot(request([500, 1000, 500]))
    assert result.required_encounters == 2036
    assert result.suggested_block_counts == [680, 678, 678]
    recommended = plan_pilot(request(result.suggested_block_counts))
    assert recommended.planned_power_lower_bound >= 0.8
    previous = plan_pilot(request([678, 678, 678]))
    assert previous.planned_power_lower_bound < 0.8
    assert result.required_days == 41 and result.planned_days == 40


def test_block_mix_does_not_change_balanced_bound_and_power_is_monotone():
    equal = plan_pilot(request([100, 100]))
    unequal = plan_pilot(request([40, 160]))
    assert equal.planned_ci_half_width == unequal.planned_ci_half_width
    assert equal.planned_power_lower_bound == unequal.planned_power_lower_bound
    assert plan_pilot(request([1000], minimum_effect=0.2)).planned_power_lower_bound > plan_pilot(request([100], minimum_effect=0.2)).planned_power_lower_bound
    assert plan_pilot(request(target_power=0.9)).required_encounters > plan_pilot(request()).required_encounters
    assert plan_pilot(request(minimum_effect=0.05)).required_encounters > plan_pilot(request()).required_encounters


@pytest.mark.parametrize("p_a,p_b", [(0.1, 0.7), (0.3, 0.9), (0.8, 0.2)])
def test_power_bound_is_below_exact_binomial_detection_probability(p_a, p_b):
    # An independent exact Bernoulli calculation, not a second copy of the planner formula.
    plan = plan_pilot(request([100], minimum_effect=abs(p_b - p_a)))
    n = 50
    a_probs = [math.comb(n, k) * p_a**k * (1 - p_a)**(n - k) for k in range(n + 1)]
    b_probs = [math.comb(n, k) * p_b**k * (1 - p_b)**(n - k) for k in range(n + 1)]
    direction = 1 if p_b > p_a else -1
    exact = sum(pa * pb for a, pa in enumerate(a_probs) for b, pb in enumerate(b_probs)
                if direction * (b - a) / n > plan.planned_ci_half_width)
    assert 0 < plan.planned_power_lower_bound <= exact <= 1 + 1e-12


def test_extreme_targets_remain_finite_and_are_never_capped_as_sufficient():
    tiny = plan_pilot(request(minimum_effect=0.001, target_power=0.99, eligible_per_day=0.1))
    assert tiny.required_encounters > 10_000 and tiny.suggested_block_counts is None
    assert tiny.planned_power_lower_bound == 0
    assert tiny.required_days == 10 * tiny.required_encounters
    assert plan_pilot(request()).suggested_block_counts is None  # one block cannot hold 2,036
    many = plan_pilot(request([4] * 30, minimum_effect=1, target_power=0.5))
    assert many.required_encounters == 120 and many.suggested_block_counts == [4] * 30
    assert 0.99 < plan_pilot(request([2000] * 5, minimum_effect=1)).planned_power_lower_bound < 1


@pytest.mark.parametrize("changes", [
    {"minimum_effect": 0}, {"minimum_effect": 1.01}, {"minimum_effect": True},
    {"minimum_effect": float("nan")}, {"target_power": 1}, {"target_power": "0.8"},
    {"eligible_per_day": float("inf")}, {"eligible_per_day": 0},
    {"available_days": 1.5}, {"available_days": True},
])
def test_invalid_assumptions(changes):
    with pytest.raises(ValidationError):
        request(**changes)


@pytest.mark.parametrize("counts", [[41], [20], [2002], [True, 40], [2000] * 6, [4] * 31])
def test_invalid_design_counts(counts):
    with pytest.raises(ValidationError):
        request(counts)
