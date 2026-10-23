"""Constant or single-category sales cannot establish a rank correlation."""

import json
import math

import numpy as np
import pytest

from store_emulator.engine.analysis.fidelity import PosLine, fidelity_report, spearman
from tests.engine.test_shared_store import _shopper, _store


@pytest.mark.parametrize("size", [0, 1, 2, 3, 1000])
@pytest.mark.parametrize("constant", [0, 1, -1])
@pytest.mark.parametrize("side", ["left", "right", "both"])
def test_constant_rank_vectors_are_unavailable(size, constant, side):
    flat = np.full(size, constant, dtype=float)
    varying = np.arange(size, dtype=float)
    a = flat if side in ("left", "both") else varying
    b = flat if side in ("right", "both") else varying
    assert math.isnan(spearman(a, b))


@pytest.mark.parametrize("a,b,expected", [
    ([1, 2, 3], [10, 20, 30], 1), ([1, 2, 3], [30, 20, 10], -1),
    ([1, 2, 3], [1, 0, 1], 0), ([0, 0, 1, 2], [0, 0, 10, 20], 1),
])
def test_measured_zero_and_defined_tied_rank_correlations_remain_numeric(a, b, expected):
    assert spearman(np.array(a, dtype=float), np.array(b, dtype=float)) == pytest.approx(expected)


@pytest.mark.parametrize("quantity", [0, 1, 2])
def test_uniform_sku_sales_are_not_labeled_a_zero_rank_match(quantity):
    store = _store()
    products = [(item.sku, item.price) for item in store.racks[0].slots[0].items]
    shoppers = [_shopper("p", "10:00:00", [(sku, quantity) for sku, _ in products] if quantity else [])]
    pos = [PosLine(transaction_id="r", sku=sku, quantity=quantity, unit_price=price) for sku, price in products]
    report = fidelity_report(store, shoppers, pos)
    scores = {metric.name: metric.value for metric in report.metrics}
    assert scores["sku_spearman"] is None
    assert scores["rack_spearman"] is None
    if quantity:
        assert scores["sku_js_similarity"] == scores["rack_js_similarity"] == 1
        assert scores["sku_ndcg@all"] == 1
    assert any("SKU rank correlation is unavailable" in note for note in report.notes)
    assert any("Rack rank correlation is unavailable" in note for note in report.notes)
    json.dumps(report.model_dump(), allow_nan=False)


def test_a_single_category_keeps_valid_sku_correlation_and_category_share_similarity():
    store = _store()
    shoppers = [_shopper("p", "10:00:00", [("chips", 1), ("nuts", 2)])]
    pos = [PosLine(transaction_id="r", sku="chips", quantity=1, unit_price=300),
           PosLine(transaction_id="r", sku="nuts", quantity=2, unit_price=350)]
    report = fidelity_report(store, shoppers, pos)
    scores = {metric.name: metric.value for metric in report.metrics}
    assert scores["sku_spearman"] == 1
    assert scores["rack_spearman"] is None
    assert scores["rack_js_similarity"] == 1
    assert not any("SKU rank correlation is unavailable" in note for note in report.notes)


def test_a_single_product_does_not_create_a_rank_from_its_shared_category():
    store = _store()
    store.racks[0].slots[0].items = store.racks[0].slots[0].items[:1]
    report = fidelity_report(store, [_shopper("p", "10:00:00", [("chips", 1)])],
        [PosLine(transaction_id="r", sku="chips", quantity=2, unit_price=300)])
    scores = {metric.name: metric.value for metric in report.metrics}
    assert scores["sku_spearman"] is None and scores["rack_spearman"] is None
    assert scores["sku_js_similarity"] == 1
    assert scores["basket_units_mean_ratio"] == .5
