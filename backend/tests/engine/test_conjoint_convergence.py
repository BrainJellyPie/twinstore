"""Conjoint fits must maximize penalized likelihood even for separated or resampled choices."""

import json
import random

import numpy as np
import pytest

from store_emulator.domain.marketing import ConjointAttribute, ConjointRespondent, ConjointTask
from store_emulator.engine.marketing.conjoint import Coding, design, estimate, fit_logit


def _choices(seed, mode):
    levels = [2 + seed % 5, 2 + (seed // 5) % 5]
    prices = [0, 1, 10000] if seed % 2 else []
    coding = Coding(levels, prices, bool(seed % 3))
    people = [ConjointRespondent(respondent=str(r), age_group="20s", gender="F", tasks=[
        ConjointTask(profiles=p, choice=0)
        for p in design(levels + ([3] if prices else []), 3 + seed % 13, 2 + seed % 3, random.Random(seed * 10 + r))
    ]) for r in range(10)]
    x, _, owner = coding.matrix(people)
    rng = np.random.default_rng(seed)
    true = rng.normal(size=coding.width) * [1, 4, 20][seed % 3]
    y = np.argmax(x @ true + (rng.gumbel(size=x.shape[:2]) if mode == "observed" else 0), axis=1)
    if mode in ("first", "last"):
        y[:] = 0 if mode == "first" else x.shape[1] - 1
    for person_index, person in enumerate(people):
        for task, choice in zip(person.tasks, y[owner == person_index], strict=True):
            task.choice = None if choice == len(task.profiles) else int(choice)
    return coding, people, x, y, owner


@pytest.mark.parametrize("seed", [0, 17, 74], ids=["minimum", "wide-price-range", "separated-preferences"])
@pytest.mark.parametrize("mode", ["observed", "deterministic", "first", "last"])
@pytest.mark.parametrize("concentrated", [False, True], ids=["whole-panel", "one-respondent-resampled"])
@pytest.mark.parametrize("initial", [0, 50, -50], ids=["cold", "positive-start", "negative-start"])
def test_fit_converges_to_the_penalized_optimum(seed, mode, concentrated, initial):
    coding, _, x, y, owner = _choices(seed, mode)
    weights = np.where(owner == 0, 10., 0.) if concentrated else np.ones(len(y))
    start = np.full(coding.width, float(initial))
    before = start.copy()
    beta = fit_logit(x, y, weights=weights, start=start)
    np.testing.assert_array_equal(start, before)
    assert np.isfinite(beta).all()
    utilities = x @ beta
    log_probs = utilities - np.logaddexp.reduce(utilities, axis=1, keepdims=True)
    probabilities = np.exp(log_probs)
    chosen_features = x[np.arange(len(y)), y]
    expected_features = np.einsum("ta,tak->tk", probabilities, x)
    gradient = np.sum(weights[:, None] * (chosen_features - expected_features), axis=0) - .1 * beta
    assert np.max(np.abs(gradient)) < 1e-4
    objective = weights @ log_probs[np.arange(len(y)), y] - .05 * (beta @ beta)
    assert objective >= -weights.sum() * np.log(x.shape[1]) - 1e-6


def test_bootstrap_weights_match_repeating_whole_respondents():
    _, _, x, y, owner = _choices(74, "observed")
    counts = np.array([0, 3, 0, 0, 1, 0, 2, 1, 0, 3])
    weights = counts[owner]
    pooled = fit_logit(x, y)
    weighted = fit_logit(x, y, weights=weights.astype(float), start=pooled)
    repeated = fit_logit(np.repeat(x, weights, axis=0), np.repeat(y, weights))
    np.testing.assert_allclose(weighted, repeated, atol=1e-5, rtol=1e-5)


def test_report_fit_is_better_than_chance_for_strongly_separated_choices():
    coding, people, _, _, _ = _choices(74, "observed")
    attrs = [ConjointAttribute(name=f"Attribute {a}", levels=[f"Level {i}" for i in range(n)]) for a, n in enumerate(coding.levels)]
    result = estimate(people, attrs, [], none_option=True, draws=30, seed=74)
    assert result is not None
    assert result.fit.log_likelihood > result.fit.null_log_likelihood
    assert 0 < result.fit.mcfadden_r2 < 1
    assert result.fit.hit_rate > result.fit.chance_rate
    assert all(abs(p.utility) < 20 for p in result.part_worths)
    json.dumps(result.model_dump(), allow_nan=False)
