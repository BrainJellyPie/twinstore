"""Price conclusions must follow observed thresholds, not an outlier-stretched plotting grid."""

import random

import pytest

from store_emulator.domain.marketing import SurveyAnswer
from store_emulator.engine.marketing.survey import van_westendorp

POINTS = ("point_of_marginal_cheapness", "optimal_price_point", "indifference_price_point",
          "point_of_marginal_expensiveness")


def answers(outlier, scale=1):
    return [SurveyAnswer(
        respondent=str(i), age_group="20s", gender="Female", too_cheap=100 * scale,
        cheap=200 * scale, expensive=300 * scale, too_expensive=(outlier if i == 9 else 400) * scale,
    ) for i in range(10)]


@pytest.mark.parametrize("outlier", [400, 100_000, 100_000_000])
@pytest.mark.parametrize("scale", [1, 100, 1000])
def test_a_high_price_outlier_cannot_move_every_intersection_outside_majority_thresholds(outlier, scale):
    price = van_westendorp(answers(outlier, scale))
    assert price is not None
    for key in POINTS:
        value = getattr(price, key)
        assert value is not None and 100 * scale <= value <= 400 * scale, (key, value)


@pytest.mark.parametrize("steps", [1, 2, 7, 60, 200])
def test_chart_resolution_cannot_change_price_conclusions(steps):
    rows = answers(100_000_000)
    expected = van_westendorp(rows, steps=1000)
    actual = van_westendorp(rows, steps=steps)
    assert actual is not None and expected is not None
    assert [getattr(actual, p) for p in POINTS] == [getattr(expected, p) for p in POINTS]


def test_equal_curves_at_the_last_price_still_have_an_intersection():
    rows = [SurveyAnswer(respondent=str(i), age_group="20s", gender="Male",
                         too_cheap=1, cheap=2, expensive=2, too_expensive=2) for i in range(5)]
    price = van_westendorp(rows)
    assert price is not None and price.indifference_price_point == 2


def test_chart_keeps_the_empirical_jumps_around_price_conclusions():
    price = van_westendorp(answers(100_000_000))
    assert price is not None
    curve = {row[0]: row[1:] for row in price.curve}
    assert 100 in curve and 101 in curve
    assert curve[100][0] == 1 and curve[101][0] == 0
    assert len(curve) <= 100


def test_generated_small_price_ranges_match_exhaustive_minor_unit_crossings():
    rng = random.Random(24102501)

    def crossing(prices, differences):
        for index, difference in enumerate(differences):
            if difference == 0:
                return prices[index]
            if index and differences[index - 1] * difference < 0:
                before = differences[index - 1]
                return round(prices[index - 1] + before / (before - difference))
        return None

    for case in range(60):
        rows = [sorted(rng.choices(range(81), k=4)) for _ in range(rng.randint(5, 25))]
        replies = [SurveyAnswer(respondent=str(i), age_group="30s", gender="Female",
                                too_cheap=tc, cheap=c, expensive=e, too_expensive=te)
                   for i, (tc, c, e, te) in enumerate(rows)]
        report = van_westendorp(replies, steps=rng.choice([1, 7, 60]))
        assert report is not None
        prices = list(range(min(r[0] for r in rows), max(r[3] for r in rows) + 1))
        n = len(rows)
        tc = [sum(r[0] >= p for r in rows) for p in prices]
        c = [sum(r[1] >= p for r in rows) for p in prices]
        e = [sum(r[2] <= p for r in rows) for p in prices]
        te = [sum(r[3] <= p for r in rows) for p in prices]
        differences = [[a - (n - b) for a, b in zip(tc, c)], [a - b for a, b in zip(tc, te)],
                       [a - b for a, b in zip(c, e)], [(n - a) - b for a, b in zip(e, te)]]
        assert [getattr(report, key) for key in POINTS] == [crossing(prices, d) for d in differences], case


def test_large_panel_does_not_expand_chart_payload_with_every_threshold():
    rows = [SurveyAnswer(respondent=str(i), age_group="30s", gender="Male", too_cheap=i * 10,
                         cheap=20_000 + i * 10, expensive=40_000 + i * 10, too_expensive=60_000 + i * 10)
            for i in range(1000)]
    report = van_westendorp(rows)
    assert report is not None and report.n == 1000
    assert len(report.curve) <= 73
