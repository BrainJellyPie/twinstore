"""Capture matching must not merge distinct SKUs because of name or price order."""

from itertools import permutations

import pytest

from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.capture.planogram import PlacementReport, match_store_skus


def match(entries, *, name="Tea", sku="captured", price=500, estimated=False, exact=True):
    store = Store(id="s", name="S", type="convenience", grid_size=(5, 5), racks=[Rack(
        id="r", type="shelf", position=(1, 1), shape=[[1]], slots=[Slot(block=0, face=Face.S, level=1,
        items=[SlotItem(sku=key, name=label, price=value) for key, label, value in entries])],
    )])
    capture = CaptureResult(image_size=(100, 100), items=[CaptureItem(
        id="i1", band=0, level=1, order=0, sku=sku, name=name, price=price, price_estimated=estimated, labeled=True,
    )])
    before = capture.model_dump_json(), store.model_dump_json()
    report = PlacementReport()
    result = match_store_skus(store, capture, report, exact=exact)
    assert before == (capture.model_dump_json(), store.model_dump_json())
    return result.items[0], report


@pytest.mark.parametrize("names,query", [(('Tea', 'Tea'), 'Tea'), (('green-tea', 'GREEN TEA'), 'Green tea'),
    (('ｔｅａ', 'tea'), 'Tea')])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("exact", [False, True])
def test_ambiguous_normalized_names_keep_the_captured_sku(names, query, reverse, exact):
    entries = [("small", names[0], 100), ("large", names[1], 700)]
    item, report = match(entries[::-1] if reverse else entries, name=query, exact=exact)
    assert item.sku == "captured" and item.price == 500 and item.name == query
    assert any("ambiguous" in note.lower() for note in report.notes)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("exact", [False, True])
def test_an_existing_sku_is_retained_despite_other_products_with_the_same_name(reverse, exact):
    entries = [("small", "Tea", 100), ("large", "Tea", 700)]
    item, _ = match(entries[::-1] if reverse else entries, sku="large", price=None, estimated=True, exact=exact)
    assert item.sku == "large" and item.price == 700


@pytest.mark.parametrize("order", list(permutations([0, 1, 2])))
def test_equally_close_names_cannot_break_a_sku_tie_by_sort_order(order):
    entries = [("one", "Sparkling lemon drink 100", 100), ("one", "Sparkling lemon drink 102", 100),
               ("two", "Sparkling lemon drink 103", 200)]
    item, report = match([entries[i] for i in order], name="Sparkling lemon drink 101", exact=False)
    assert item.sku == "captured"
    assert any("ambiguous" in note.lower() for note in report.notes)


@pytest.mark.parametrize("price,estimated,expected", [(500, True, 500), (None, True, None), (20, False, 20)])
@pytest.mark.parametrize("reverse", [False, True])
def test_repeated_sku_with_different_prices_does_not_choose_an_arbitrary_estimate(price, estimated, expected, reverse):
    entries = [("tea", "Tea", 100), ("tea", "Tea", 700)]
    item, _ = match(entries[::-1] if reverse else entries, price=price, estimated=estimated)
    assert item.sku == "tea" and item.price == expected and item.price_estimated is estimated


@pytest.mark.parametrize("exact", [False, True])
def test_repeated_copies_of_one_unambiguous_product_reuse_its_price(exact):
    item, _ = match([("tea", "Tea", 100)] * 4, price=None, estimated=True, exact=exact)
    assert item.sku == "tea" and item.price == 100


def test_unique_fuzzy_match_is_still_supported():
    item, _ = match([("tea", "Sparkling lemon drink 100", 100)], name="Sparkling lemon drink 101", exact=False)
    assert item.sku == "tea"
