"""Accepted signed study seeds must survive estimation after respondents have answered."""

import json
import random

import pytest

from store_emulator.domain.marketing import ConjointRequest, ConjointRespondent, ConjointTask
from store_emulator.engine.marketing.conjoint import design, estimate


@pytest.mark.parametrize("seed", [-1, -(2**63), -(10**80), 0], ids=["negative", "signed-limit", "large", "zero"])
@pytest.mark.parametrize("prices", [[], [0, 199, 999]], ids=["no-prices", "prices"])
@pytest.mark.parametrize("none_option", [False, True])
def test_signed_seeds_produce_finite_repeatable_estimates(seed, prices, none_option):
    request = ConjointRequest(
        product="Tea", seed=seed, prices=prices, none_option=none_option,
        attributes=[{"name": "Sugar", "levels": ["Regular", "Zero"]},
                    {"name": "Pack", "levels": ["Can", "Bottle"]}],
    )
    levels = [2, 2] + ([len(prices)] if prices else [])
    people = [ConjointRespondent(
        respondent=str(i), age_group="20s", gender="Female", tasks=[
            ConjointTask(profiles=profiles, choice=None if none_option and (i + t) % 3 == 0 else (i + t) % 4)
            for t, profiles in enumerate(design(levels, 3, 4, random.Random(i)))
        ],
    ) for i in range(10)]
    result = estimate(people, request.attributes, prices, none_option=none_option, seed=request.seed, draws=8)
    assert result is not None and result.fit.choices == 30
    json.dumps(result.model_dump(), allow_nan=False)
    assert result == estimate(people, request.attributes, prices, none_option=none_option, seed=abs(seed), draws=8)
