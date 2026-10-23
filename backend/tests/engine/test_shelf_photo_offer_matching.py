"""Photo badges must describe the captured offer, including repeated-SKU shelves."""

import random

import pytest
from PIL import Image, ImageDraw

from store_emulator.domain.capture import Box, CaptureItem, CaptureResult
from store_emulator.domain.rack import RACK_LEVELS
from store_emulator.engine.capture.planogram import display_name
from store_emulator.engine.perception import render_face
from store_emulator.engine.prompting import display_price
from store_emulator.engine.shelf_lab.sim2real import build_views, photo_view, twin_rack
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance, resolve


def capture(offers):
    return CaptureResult(image_size=(400, 400), currency="USD", items=[CaptureItem(
        id=f"i{i}", band=4 - level, level=level, order=i, sku=sku, name=name, price=price,
        labeled=True, facings=facings, boxes=[Box(x1=10 + (i % 4) * 90, y1=10 + (4 - level) * 90,
                                                x2=80 + (i % 4) * 90, y2=80 + (4 - level) * 90)],
    ) for i, (sku, name, price, level, facings) in enumerate(offers)])


@pytest.mark.parametrize("seed", [0, 1, 7, 19])
@pytest.mark.parametrize("prices", [(100, 700), (100, 100), (0, 700)])
@pytest.mark.parametrize("levels", [(1, 2), (4, 1), (2, 2)])
def test_each_view_retains_prices_and_levels_of_repeated_skus(seed, prices, levels):
    result = capture([("tea", "Tea", price, level, i + 1) for i, (price, level) in enumerate(zip(prices, levels))])
    with Image.new("RGB", result.image_size, "white") as photo:
        views = build_views(photo, result, width=256, seed=seed)
    expected = {("tea", price, level) for price, level in zip(prices, levels)}
    for condition, view in views.views.items():
        assert {(m.item.sku, m.item.price, m.slot.level) for m in view.items} == expected, condition
        if condition != "photo_raw":
            for marked in view.items:
                chosen, _ = resolve(view, ShelfGlance(product="Tea", number=marked.mark))
                assert chosen == marked


def test_photo_badges_show_the_price_of_each_captured_offer(monkeypatch):
    result = capture([("tea", "Tea", 100, 1, 2), ("tea", "Tea", 700, 2, 1)])
    rack, face = twin_rack(result)
    render = render_face(rack, face, width=256)
    text = []
    original = ImageDraw.ImageDraw.text

    def record(draw, xy, label, *args, **kwargs):
        text.append(label)
        return original(draw, xy, label, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    with Image.new("RGB", result.image_size, "white") as photo:
        view = photo_view(photo, result, render, tags=True, width=256)
    assert len(text) == 2
    for item, label in zip(result.items, text, strict=True):
        mark = int(label.split()[0][1:])
        selected = view.by_mark(mark)
        assert selected is not None
        assert (selected.item.price, selected.slot.level) == (item.price, item.level)
        assert label == f"#{mark} {display_price(item.price, 'USD')}"


@pytest.mark.parametrize("seed", range(16))
def test_mixed_catalogs_preserve_every_distinct_rendered_offer(seed):
    rng = random.Random(seed + 261023)
    offers = [(f"sku-{rng.randrange(3)}", f"Product {rng.randrange(3)}", rng.choice([0, 100, 150, 999]),
               level, rng.randrange(1, 4)) for level in range(1, 5) for _ in range(4)]
    result = capture(offers)
    with Image.new("RGB", result.image_size, "white") as photo:
        views = build_views(photo, result, width=256, seed=seed)
    expected = {(i.sku, display_name(i), max(0, i.price or 0), min(RACK_LEVELS, max(1, i.level))) for i in result.items}
    for view in views.views.values():
        actual = {(m.item.sku, m.item.name, m.item.price, m.slot.level) for m in view.items}
        assert actual == expected
    assert views.dropped_products == 0


def test_capacity_overflow_does_not_relabel_dropped_offers_as_other_prices():
    result = capture([("tea", "Tea", price, 1, 1) for price in range(100, 140)])
    for i, item in enumerate(result.items):
        item.boxes = [Box(x1=1 + i * 9, x2=9 + i * 9, y1=300, y2=370)]
    with Image.new("RGB", result.image_size, "white") as photo:
        views = build_views(photo, result, width=256)
    for view in views.views.values():
        assert {m.item.price for m in view.items} == set(range(100, 132))
    assert views.dropped_products == 8
