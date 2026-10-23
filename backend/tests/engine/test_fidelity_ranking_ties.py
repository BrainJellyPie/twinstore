"""Tied sales predictions must not be ranked by arbitrary SKU identifiers."""

from itertools import permutations
import math

import numpy as np
import pytest

from store_emulator.engine.analysis.fidelity import PosLine, fidelity_report, ndcg
from tests.engine.test_analysis import _customer


def expected_ndcg(predicted, relevance, k):
    if k <= 0 or not any(relevance):
        return 0
    orders = [order for order in permutations(range(len(predicted)))
              if all(predicted[a] >= predicted[b] for a, b in zip(order, order[1:]))]
    dcgs = [sum(relevance[index] / math.log2(rank + 2) for rank, index in enumerate(order[:k]))
            for order in orders]
    ideal = sum(value / math.log2(rank + 2) for rank, value in enumerate(sorted(relevance, reverse=True)[:k]))
    return sum(dcgs) / len(dcgs) / ideal


@pytest.mark.parametrize("predicted,relevance", [
    ([0, 0], [100, 0]),
    ([5, 5, 0], [10, 0, 5]),
    ([7, 5, 5, 2], [0, 2, 10, 9]),
    ([2, 2, 2, 0], [.25, 9, 0, 2.5]),
    ([0, 0, 0, 0], [1, 2, 3, 4]),
    ([4, 3, 2, 1], [4, 3, 2, 1]),
    ([3, 1, 2], [9, 2, 5]),
    ([2, 2, 1, 1], [0, 0, 0, 0]),
])
@pytest.mark.parametrize("k", [0, 1, 2, 3, 10])
def test_ranking_score_matches_every_possible_order_within_ties(predicted, relevance, k):
    assert ndcg(np.array(predicted), np.array(relevance), k) == pytest.approx(expected_ndcg(predicted, relevance, k))


def test_generated_tied_rankings_are_invariant_to_input_order():
    rng = np.random.default_rng(261023947)
    for _ in range(80):
        size = int(rng.integers(2, 30))
        predicted = rng.integers(0, 4, size=size)
        relevance = rng.integers(0, 30, size=size) / 4
        order = rng.permutation(size)
        for k in (1, size // 2, size, size + 10):
            assert ndcg(predicted, relevance, k) == pytest.approx(ndcg(predicted[order], relevance[order], k))


@pytest.mark.parametrize("units", [0, 1])
def test_fidelity_report_does_not_prefer_the_alphabetically_first_sku_when_sales_tie(collision_store, units):
    results = [_customer("p", [("sku-a", 100, units, "planned"), ("sku-b", 200, units, "planned")])] if units else []
    reports = [fidelity_report(collision_store, results,
        [PosLine(transaction_id="sale", sku=sku, quantity=10, unit_price=100)], top_k=1)
        for sku in ("sku-a", "sku-b")]
    scores = [{metric.name: metric.value for metric in report.metrics} for report in reports]
    assert scores[0]["sku_ndcg@1"] == scores[1]["sku_ndcg@1"] == .5
    assert scores[0]["sku_ndcg@all"] == scores[1]["sku_ndcg@all"]
