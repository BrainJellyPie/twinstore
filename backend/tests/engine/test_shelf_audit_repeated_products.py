"""Repeated products must not create false compliance findings or hide bad price tags."""

from itertools import product

import pytest

from store_emulator.domain.capture import Box, CaptureItem, CaptureResult
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.engine.shelf_lab.audit import diff_face


def reference(offers):
    return Rack(id="shelf", type="shelf", shape=[[1]], position=(0, 0), slots=[Slot(
        block=0, face=Face.S, level=1, items=[SlotItem(sku=sku, name=sku, price=price) for sku, price in offers],
    )])


def photographed(offers):
    return CaptureResult(image_size=(400, 100), items=[CaptureItem(
        id=str(i), band=0, level=1, order=i, sku=sku, name=sku, price=price,
        boxes=[Box(x1=i * 90, y1=0, x2=i * 90 + 80, y2=80)],
    ) for i, (sku, price) in enumerate(offers)])


@pytest.mark.parametrize("skus", product("ABC", repeat=4))
@pytest.mark.parametrize("mixed_prices", [False, True])
def test_identical_shelves_never_report_a_deviation(skus, mixed_prices):
    offers = [(sku, 100 + i * 50 if mixed_prices else 100) for i, sku in enumerate(skus)]
    levels, findings = diff_face(reference(offers), Face.S, photographed(offers), "USD")
    assert findings == []
    assert len(levels) == 1 and levels[0].score == 1


def test_repeated_product_occurrences_are_checked_in_order():
    rack = reference([("A", 100), ("B", 100), ("A", 100), ("C", 100)])
    field = photographed([("A", 100), ("B", 100), ("C", 100), ("A", 100)])
    findings = diff_face(rack, Face.S, field, "USD")[1]
    moved = [finding.sku for finding in findings if finding.kind == "misplaced"]
    assert sorted(moved) == ["A", "C"]


@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_reduced_repeated_product_is_reported_once(missing):
    rack = reference([("A", 100), ("B", 100), ("A", 100), ("C", 100)])
    field = photographed(([] if missing else [("A", 100)]) + [("B", 100), ("C", 100)])
    findings = diff_face(rack, Face.S, field, "USD")[1]
    counts = [finding for finding in findings if finding.sku == "A" and finding.kind == ("missing" if missing else "facings")]
    assert len(counts) == 1
    assert counts[0].expected == ("2 facings" if missing else "2")


@pytest.mark.parametrize("bad_at", [0, 1, 2])
def test_every_read_price_tag_is_checked_and_points_to_the_bad_offer(bad_at):
    rack = reference([("A", 100), ("A", 700), ("A", 100)])
    prices = [100, 700, 100]
    prices[bad_at] = 450
    field = photographed([("A", price) for price in prices])
    findings = diff_face(rack, Face.S, field, "USD")[1]
    prices = [finding for finding in findings if finding.kind == "price"]
    assert len(prices) == 1
    assert prices[0].found == "$4.50"
    assert "$1.00" in prices[0].expected and "$7.00" in prices[0].expected
    assert prices[0].box == field.items[bad_at].boxes[0]


@pytest.mark.parametrize("price,estimated,wrong", [(None, False, False), (700, True, False),
    (0, False, False), (1, False, False), (2, False, True)])
def test_free_reference_products_and_unread_or_estimated_prices(price, estimated, wrong):
    field = photographed([("A", price)])
    field.items[0].price_estimated = estimated
    findings = diff_face(reference([("A", 0)]), Face.S, field, "USD")[1]
    assert bool([f for f in findings if f.kind == "price"]) is wrong


def test_split_capture_groups_of_one_product_are_not_extra_positions():
    field = photographed([("A", 100), ("A", 100), ("B", 100), ("A", 100)])
    rack = reference([("A", 100), ("A", 100), ("B", 100), ("A", 100)])
    assert diff_face(rack, Face.S, field, "USD")[1] == []
