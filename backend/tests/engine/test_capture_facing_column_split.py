"""A product run crossing rack boundaries must keep its facings on both sides."""

from collections import Counter

import pytest

from store_emulator.domain.capture import Box, CaptureItem, CaptureResult
from store_emulator.engine.capture.planogram import _split_columns, add_capture_racks
from store_emulator.engine.layout_gen import generate_store


def photographed(groups):
    items = []
    cursor = 0
    for index, (name, count) in enumerate(groups):
        boxes = [Box(x1=(cursor + i) * 30, y1=0, x2=(cursor + i) * 30 + 28, y2=80) for i in range(count)]
        items.append(CaptureItem(id=f"i{index}", band=0, level=3, order=index, sku=name, name=name,
                                 price=100 + index, facings=count, boxes=boxes, labeled=True))
        cursor += count
    return CaptureResult(image_size=(cursor * 30, 100), dominant_category="chips", currency="USD", items=items)


@pytest.mark.parametrize("facings", [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])
def test_one_wide_product_uses_all_available_rack_capacity(facings):
    capture = photographed([("Tea", facings)])
    before = capture.model_dump_json()
    original = generate_store("mini_mart", seed=0)
    store, report = add_capture_racks(original, [capture], exact_sku_match=True)
    placed = [item for rack in store.racks if rack.id in report.rack_ids for slot in rack.slots for item in slot.items]
    assert report.placed_facings == facings
    assert report.placed_items == 1 and report.dropped == []
    assert len(placed) == facings and all(item.name == "Tea" and item.price == 100 for item in placed)
    assert all(any(slot.items for slot in rack.slots) for rack in store.racks if rack.id in report.rack_ids)
    assert capture.model_dump_json() == before


@pytest.mark.parametrize("groups", [[("A", 5), ("B", 7)], [("A", 3), ("B", 6), ("C", 3)],
    [("A", 1), ("B", 14), ("C", 1)], [("A", 8), ("B", 8)]])
def test_runs_crossing_columns_keep_every_product_facing(groups):
    capture = photographed(groups)
    columns = (sum(count for _, count in groups) + 3) // 4
    parts = _split_columns(capture, columns)
    actual = Counter()
    for part in parts:
        assert part.facings <= 4
        for item in part.items:
            actual[item.name] += item.facings
            assert len(item.boxes) == item.facings
    assert actual == Counter(dict(groups))
    assert [box for part in parts for item in part.items for box in item.boxes] == [box for item in capture.items for box in item.boxes]


@pytest.mark.parametrize("box_count", [1, 2, 3, 5, 9])
@pytest.mark.parametrize("declared", [1, 2, 4, 12, 24])
def test_adjusted_facing_counts_are_apportioned_without_inventing_units(box_count, declared):
    capture = photographed([("A", box_count)])
    capture.items[0].facings = declared
    before = capture.model_dump_json()
    parts = _split_columns(capture, 4)
    assert sum(part.facings for part in parts) == declared
    for index, part in enumerate(parts):
        for item in part.items:
            assert item.facings > 0 and item.boxes
            lo = capture.items[0].boxes[0].x1
            span = capture.items[0].boxes[-1].x2 - lo
            assert all(min(3, int((box.cx - lo) / span * 4)) == index for box in item.boxes)
    assert capture.model_dump_json() == before


def test_over_capacity_photo_keeps_the_full_supported_sixteen_facings():
    capture = photographed([("Tea", 24)])
    store, report = add_capture_racks(generate_store("mini_mart"), [capture], exact_sku_match=True)
    assert report.placed_facings == 16
    assert len(report.rack_ids) == 4
    assert all(sum(len(slot.items) for slot in rack.slots) == 4 for rack in store.racks if rack.id in report.rack_ids)


def test_partially_retained_product_is_not_reported_as_completely_dropped():
    capture = photographed([("A", 4), ("B", 1), ("C", 1), ("D", 1), ("E", 1)])
    capture.items[0].boxes = [Box(x1=x, y1=0, x2=x + 8, y2=80) for x in [20, 150, 170, 190]]
    for item, x in zip(capture.items[1:], [2, 6, 10, 14], strict=True):
        item.boxes = [Box(x1=x, y1=0, x2=x + 2, y2=80)]
    store, report = add_capture_racks(generate_store("mini_mart"), [capture], exact_sku_match=True)
    placed = Counter(item.name for rack in store.racks if rack.id in report.rack_ids for slot in rack.slots for item in slot.items)
    assert placed == Counter(A=3, B=1, C=1, D=1, E=1)
    assert report.placed_items == 5 and report.placed_facings == 7 and report.dropped == []
