"""Reference SKU and price conflicts cannot be resolved by shelf order."""

import pytest

from store_emulator.domain.capture import CaptureItem
from store_emulator.domain.rack import SlotItem
from store_emulator.engine.shelf_lab.rival import compare_rival, unmatched_names
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("other_sku,other_price,identity_known", [
    ("different", 100, False), ("different", 400, False), ("tea", 400, True),
])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("other_name", ["Tea", "ＴＥＡ"])
def test_conflicts_do_not_change_a_healthy_neighbor_price_index(other_sku, other_price, identity_known, reverse, alias, other_name):
    printed = "Captured label" if alias else "Tea"
    store, capture = pair(our_price=100, rival_price=200, rival_name=printed)
    store.racks[0].slots[0].items.extend([
        SlotItem(sku=other_sku, name=other_name, price=other_price),
        SlotItem(sku="coffee", name="Coffee", price=200),
    ])
    capture.items.append(CaptureItem(id="coffee", band=0, level=1, order=1, name="Coffee", price=180, labeled=True))
    if reverse:
        store.racks[0].slots[0].items.reverse()
        capture.items.reverse()
    before = store.model_dump(), capture.model_dump()
    missing, names = unmatched_names(store, capture)
    if not identity_known:
        assert missing == [printed] and names == ["Coffee"]
    elif not alias:
        assert not missing
    report = compare_rival(store, capture, aliases={printed: "Tea"} if alias else None)
    assert report.matched == 1 + int(identity_known)
    assert report.price_index == pytest.approx(0.9) and report.suggested_pull_factor == 1.111
    assert [(p.name, p.our_price, p.rival_price) for p in report.prices] == [("Coffee", 200, 180)]
    assert (store.model_dump(), capture.model_dump()) == before


@pytest.mark.parametrize("copies", [1, 2, 4])
@pytest.mark.parametrize("alias", [False, True])
def test_repeated_identical_reference_offers_still_match(copies, alias):
    printed = "Captured label" if alias else "Tea"
    store, capture = pair(our_price=100, rival_price=200, rival_name=printed)
    store.racks[0].slots[0].items *= copies
    report = compare_rival(store, capture, aliases={printed: "Tea"} if alias else None)
    assert report.matched == 1 and report.price_index == 2 and len(report.prices) == 1
