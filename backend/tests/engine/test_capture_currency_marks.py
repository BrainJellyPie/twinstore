"""Recognized currency signs must retain their currency and major-unit meaning."""

import pytest
from PIL import Image

from store_emulator.domain.capture import CaptureResult, ShelfItemLabel
from store_emulator.engine.capture.catalog_match import price_minor_units, typical_price
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.planogram import replace_rack_face
from store_emulator.engine.capture.recognize import FacingGroup, describe
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY", "EUR", "CAD", "TWD"])
@pytest.mark.parametrize("guess", [None, 1, 100])
@pytest.mark.parametrize("tag", ["₹100", "100 ₹", "₹１００"])
def test_a_rupee_sign_cannot_become_another_currency(currency, guess, tag):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,expected", [
    ("₹100", 10000), ("100₹", 10000), ("₹１００", 10000),
    ("₹0.00", 0), ("₹0.01", 1), ("₹1,000", 100000), ("₹1,00,000", 10000000),
    ("₹1.00 WITH COUPON", 100), ("ITEM ₹100", 10000), ("₹100 INR", 10000),
    ("₹100 USD", None), ("-₹100", None), ("− ₹100", None), ("₹-100", None),
    ("SAVE ₹100", None), ("₹100 OFF", None), ("FROM ₹100", None), ("₹100+", None),
    ("DEPOSIT ₹100", None), ("₹100 / L", None), ("₹100.00 / kg", None),
    ("DEPOSIT INCLUDED ₹100", 10000), ("₹100 LIMITED OFFER", 10000),
])
def test_matching_rupee_prices_remain_literal_major_units_with_existing_guards(tag, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=1), "INR", 249) == expected


@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("tag", ["₹100", "R$1.00", "₫1000", "d1000", "1000 đ"])
def test_foreign_signs_preserve_captured_identity_and_existing_store_prices(known, tag):
    store = target_store()
    store.racks[0].slots[0].items[0].price = 799
    if not known:
        store.racks[0].slots = []
    original = store.model_dump_json()
    with Image.new("RGB", (100, 80), "white") as photo:
        detection = Detection(x1=0, y1=0, x2=40, y2=60, band=0)
        label = ShelfItemLabel(name="Cola 500ml", category="soft drink", price_text=tag, price=1)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label)
        items, _ = build_items(make_frame(photo), [group], [3], currency="USD", rack_type="shelf")
        assert items[0].price_estimated and items[0].price_text == tag
        assert items[0].labeled and items[0].name == "Cola 500ml"
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    expected = 799 if known else typical_price("soft_drinks", "Cola 500ml", "USD")[0]
    assert len(placed) == 1 and placed[0].price == expected
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == original and updated.racks[1] == store.racks[1]


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY", "EUR", "INR", "BRL", "CAD"])
@pytest.mark.parametrize("guess", [None, 1, 1000])
@pytest.mark.parametrize("tag", ["₫1000", "1000₫", "d1000", "D 1000", "1000 d", "đ1000", "1000 Đ", "ｄ１０００", "₫0", "0d"])
def test_dong_units_cannot_become_the_store_currency(currency, guess, tag):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,expected", [
    ("₫1000", 1000), ("1000₫", 1000), ("d1000", 1000), ("D 1,000", 1000),
    ("1000 d", 1000), ("đ1000", 1000), ("1000 Đ", 1000), ("ｄ１０００", 1000),
    ("₫0", 0), ("d0", 0), ("0 đ", 0), ("VND1000", 1000), ("₫1000 VND", 1000),
    ("₫1000 USD", None), ("USD1000", None), ("$1000", None), ("$d1000", None),
    ("-d1000", None), ("−1000 d", None), ("đ1000-", None),
    ("SAVE d1000", None), ("1000 đ OFF", None), ("FROM ₫1000", None),
    ("d1000+", None), ("DEPOSIT d1000", None), ("DEPOSIT INCLUDED d1000", 1000),
    ("d1000 / L", None), ("1000 đ per kg", None), ("d1000 WITH COUPON", 1000),
])
def test_dong_units_remain_literal_and_keep_existing_price_guards(tag, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=1), "VND", 45000) == expected


@pytest.mark.parametrize("tag,expected", [
    ("USD1000", 100000), ("1000USD", 100000), ("USD 1.00", 100),
    ("RED $1.00", 100), ("LIMITED OFFER $1.00", 100), ("PRICE 1.00", 100),
    ("DISCOUNT 1000", None), ("CAD1.00", None), ("1.00USD", 100),
])
def test_dong_abbreviations_do_not_match_inside_other_words(tag, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag), "USD", 249) == expected
