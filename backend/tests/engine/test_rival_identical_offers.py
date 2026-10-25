"""Repeated detections of one offer must not weight a rival's price index."""

import pytest

from store_emulator.domain.capture import CaptureItem
from store_emulator.domain.rack import SlotItem
from store_emulator.engine.shelf_lab.rival import compare_rival
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("copies", [1, 2, 9])
@pytest.mark.parametrize("names", ["identical", "case", "alias"])
@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_offers_cannot_change_price_index_or_unique_product_count(copies, names, reverse):
    store, capture = pair(our_name="Tea", our_price=100, rival_price=200)
    store.racks[0].slots[0].items.append(SlotItem(sku="coffee", name="Coffee", price=200))
    labels = [f"Printed tea label {i}" if names == "alias" else ("TEA" if names == "case" and i % 2 else "Tea")
              for i in range(copies)]
    capture.items = [capture.items[0].model_copy(update={"id": f"tea-{i}", "name": name, "level": i % 4 + 1,
        "order": i, "facings": i + 1}) for i, name in enumerate(labels)] + [
        CaptureItem(id="coffee", band=0, level=1, order=copies, name="Coffee", price=100, labeled=True)]
    if reverse:
        capture.items.reverse()
    before = capture.model_dump()
    report = compare_rival(store, capture, aliases={name: "Tea" for name in labels} if names == "alias" else None)
    assert report.matched == report.rival_products == 2
    assert report.price_index == pytest.approx(1) and report.suggested_pull_factor == 1
    assert len(report.prices) == 2 and {row.ratio for row in report.prices} == {0.5, 2}
    assert report.overlap == 1 and not report.only_rival and not report.only_ours
    assert capture.model_dump() == before


@pytest.mark.parametrize("copies", [1, 5])
def test_different_prices_for_the_same_rival_product_remain_distinct_offers(copies):
    store, capture = pair(our_price=100, rival_price=200)
    capture.items = [capture.items[0].model_copy(update={"id": f"copy-{i}"}) for i in range(copies)] + [
        capture.items[0].model_copy(update={"id": "other-offer", "price": 300})]
    report = compare_rival(store, capture)
    assert report.matched == report.rival_products == 1 and len(report.prices) == 2
    assert {row.rival_price for row in report.prices} == {200, 300}
    assert report.price_index == pytest.approx(6 ** 0.5)


def test_unmatched_normalized_copies_count_as_one_product():
    store, capture = pair(our_name="Tea", rival_name="Unknown Coffee")
    capture.items.append(capture.items[0].model_copy(update={"id": "duplicate", "name": "UNKNOWN COFFEE"}))
    report = compare_rival(store, capture)
    assert report.matched == 0 and report.rival_products == 1 and len(report.only_rival) == 1
    assert report.price_index is None and report.suggested_pull_factor is None
