"""Returns may make net sales negative, which cannot define a unit-share distribution."""

import json

import pytest

from store_emulator.application.pos import parse_pos_csv
from store_emulator.engine.analysis.fidelity import fidelity_report
from tests.engine.test_analysis import _customer


@pytest.mark.parametrize("units", [(-1, -2), (2, -1), (1, -1), (0, -1), (-0.5, -2.25), (0.000001, -0.000001)])
def test_negative_net_pos_units_do_not_produce_valid_share_or_ranking_scores(collision_store, units):
    pos = parse_pos_csv(("receipt_id,sku,quantity,unit_price\n"
                         f"r1,sku-a,{units[0]},100\nr2,sku-b,{units[1]},200\n").encode())
    buyers = [_customer("p", [("sku-a", 100, 1, "planned"), ("sku-b", 200, 2, "planned")])]
    report = fidelity_report(collision_store, buyers, pos)
    scores = {metric.name: metric.value for metric in report.metrics}
    for key in ("sku_js_similarity", "sku_ndcg@10", "sku_ndcg@all", "rack_js_similarity"):
        assert scores[key] is None, (key, scores[key])
    assert any("negative net POS units" in note for note in report.notes)
    assert report.real_transactions == 2
    json.dumps(report.model_dump(), allow_nan=False)


def test_returns_that_leave_nonnegative_net_sales_preserve_distribution_scores(collision_store):
    pos = parse_pos_csv(b"receipt_id,sku,quantity,unit_price\nsale,sku-a,3,100\nreturn,sku-a,-2,100\nsale,sku-b,2,200\n")
    buyers = [_customer("p", [("sku-a", 100, 1, "planned"), ("sku-b", 200, 2, "planned")])]
    report = fidelity_report(collision_store, buyers, pos)
    scores = {metric.name: metric.value for metric in report.metrics}
    for key in ("sku_js_similarity", "sku_ndcg@10", "sku_ndcg@all", "rack_js_similarity"):
        assert scores[key] == 1
    assert not any("negative net POS units" in note for note in report.notes)


def test_nonnegative_rack_totals_remain_scorable_when_one_product_has_net_returns(collision_store):
    for rack in collision_store.racks:
        if rack.slots:
            rack.rack_name = "Shared category"
    pos = parse_pos_csv(b"receipt_id,sku,quantity,unit_price\nsale,sku-a,4,100\nreturn,sku-b,-1,200\n")
    buyers = [_customer("p", [("sku-a", 100, 1, "planned"), ("sku-b", 200, 2, "planned")])]
    scores = {metric.name: metric.value for metric in fidelity_report(collision_store, buyers, pos).metrics}
    assert scores["sku_js_similarity"] is None
    assert scores["sku_ndcg@all"] is None
    assert scores["rack_js_similarity"] == 1


@pytest.mark.parametrize("a", [-3, -1, 0, 1, 3])
@pytest.mark.parametrize("b", [-3, -1, 0, 1, 3])
@pytest.mark.parametrize("shared_rack", [False, True])
@pytest.mark.parametrize("has_buyers", [False, True])
@pytest.mark.parametrize("top_k", [1, 2, 10])
def test_return_combinations_keep_scores_defined_only_for_valid_net_distributions(collision_store, a, b, shared_rack, has_buyers, top_k):
    if shared_rack:
        for rack in collision_store.racks:
            if rack.slots:
                rack.rack_name = "Shared category"
    # Split sales and returns, include fractional weighed goods and an unknown returned SKU.
    rows = ["receipt_id,sku,quantity,unit_price,hour", "sale-a,sku-a,8,100,12", "sale-b,sku-b,8,200,12",
            f"return-a,sku-a,{a / 4 - 8},100,12", f"return-b,sku-b,{b / 4 - 8},200,12", "unknown,missing,-999,100,12"]
    pos = parse_pos_csv("\n".join(rows).encode())
    buyers = [_customer("p", [("sku-a", 100, 1, "planned"), ("sku-b", 200, 2, "planned")])] if has_buyers else []
    report = fidelity_report(collision_store, buyers, pos, top_k=top_k)
    scores = {metric.name: metric.value for metric in report.metrics}
    for name in ("sku_js_similarity", f"sku_ndcg@{top_k}", "sku_ndcg@all"):
        if min(a, b) < 0:
            assert scores[name] is None
        else:
            assert scores[name] is not None and 0 <= scores[name] <= 1
    rack_negative = a + b < 0 if shared_rack else min(a, b) < 0
    if rack_negative:
        assert scores["rack_js_similarity"] is None
    else:
        assert scores["rack_js_similarity"] is not None and 0 <= scores["rack_js_similarity"] <= 1
    assert any("negative net POS units" in note for note in report.notes) is (min(a, b) < 0)
    assert report.real_transactions == 4
    json.dumps(report.model_dump(), allow_nan=False)
