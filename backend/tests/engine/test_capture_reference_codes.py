"""Nonmonetary identifiers and date labels must not become exact selling prices."""
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


@pytest.mark.parametrize("tag,currency", [
    ("ID 1234", "USD"), ("ID: 1234", "EUR"), ("ID no. 1234", "JPY"), ("ID1234", "USD"),
    ("ID number 1234", "KRW"), ("Product ID 1234", "USD"), ("ｉｄ １２３４", "USD"),
    ("ID 0", "USD"), ("ID 1.00", "USD"), ("ID #1234", "VND"),
    ("SKU 1234", "USD"), ("SKU: 1234", "USD"), ("UPC 1234", "USD"),
    ("EAN 1234", "EUR"), ("GTIN #1234", "USD"), ("LOT 1234", "USD"),
    ("Lot number: 1234", "USD"), ("Batch no. 1234", "USD"), ("Serial number 1234", "USD"),
    ("Item code: 1234", "USD"), ("Product number 1234", "USD"), ("Model 1234", "USD"),
    ("ITEM #1234", "USD"), ("Item: 1234", "USD"), ("Item 1234", "USD"),
    ("PRODUCT #1234", "USD"), ("Product 1234", "USD"), ("Article #1234", "EUR"),
    ("Article 1234", "EUR"), ("Ref 1234", "USD"), ("REF #1234", "USD"),
    ("Ref. 1234", "USD"), ("Ref. no. 1234", "USD"), ("Reference: 1234", "USD"),
    ("Reference number 1234", "USD"), ("Reference code #1234", "USD"),
    ("#1234", "USD"), ("# 1234", "JPY"), ("ＩＴＥＭ ＃１２３４", "KRW"),
    ("ＲＥＦ．１２３４", "USD"), ("＃１２３４", "USD"),
    ("EXP 2026", "USD"), ("Expiry date: 2026", "USD"), ("Expires 2026", "USD"),
    ("Best before 2026", "USD"), ("Best by 2026", "USD"), ("Use by 2026", "USD"),
    ("Sell by 2026", "USD"), ("MFG 2026", "USD"), ("Manufactured on 2026", "USD"),
    ("ＳＫＵ：１２３４", "USD"), ("상품코드 1234", "KRW"), ("제품번호: 1234", "KRW"),
    ("제조번호 1234", "KRW"), ("소비기한 2026", "KRW"), ("유통기한 2026", "KRW"),
    ("賞味期限2026", "JPY"), ("消費期限2026", "JPY"), ("商品番号1234", "JPY"),
])
@pytest.mark.parametrize("guess", [None, 12.34, 2026.0])
def test_reference_numbers_cannot_be_overridden_by_a_model_price_guess(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,currency,expected", [
    ("ID $1.00", "USD", 100), ("ID USD 1.00", "USD", 100), ("ID 1,000원", "KRW", 1000),
    ("ID 1000₫", "VND", 1000), ("ID price 1.00", "USD", 100),
    ("VALID 1.00", "USD", 100), ("SOLID 1.00", "USD", 100), ("IDEAL 1.00", "USD", 100),
    ("IDR1000", "IDR", 1000), ("AID 1.00", "USD", 100),
    ("$1.00", "USD", 100), ("$0.00", "USD", 0), ("1234", "USD", 1234),
    ("PRICE 1234", "USD", 1234), ("Item price $1.00", "USD", 100),
    ("Lot $1.00", "USD", 100), ("LOT USD 1.00", "USD", 100),
    ("EXPRESS $1.00", "USD", 100), ("Lotus $1.00", "USD", 100),
    ("ITEM $1.00", "USD", 100), ("Product USD 1.00", "USD", 100),
    ("Article $1.00", "USD", 100), ("Ref $1.00", "USD", 100), ("# $1.00", "USD", 100),
    ("Item price 1.00", "USD", 100), ("Product price 1.00", "USD", 100),
    ("Refill 1.00", "USD", 100), ("Referencebook 1.00", "USD", 100),
    ("Itemized 1.00", "USD", 100), ("Productivity 1.00", "USD", 100),
    ("1,000원", "KRW", 1000), ("100円", "JPY", 100), ("1,00 €", "EUR", 100),
])
def test_cash_prices_and_ordinary_numeric_tags_remain_usable(tag, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag), currency, 249) == expected


@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("tag", ["ID 1234", "SKU 1234", "LOT 1234", "EXP 2026", "ITEM #1234", "REF 1234", "#1234"])
def test_a_reference_label_preserves_identity_and_the_existing_selling_price(known, tag):
    store = target_store()
    store.racks[0].slots[0].items[0].price = 799
    if not known:
        store.racks[0].slots = []
    original = store.model_dump_json()
    with Image.new("RGB", (100, 80), "white") as photo:
        detection = Detection(x1=0, y1=0, x2=40, y2=60, band=0)
        label = ShelfItemLabel(name="Cola 500ml", category="soft drink", price_text=tag, price=12.34)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label)
        items, _ = build_items(make_frame(photo), [group], [3], currency="USD", rack_type="shelf")
        assert items[0].labeled and items[0].name == "Cola 500ml" and items[0].price_text == tag
        assert items[0].price_estimated
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    expected = 799 if known else typical_price("soft_drinks", "Cola 500ml", "USD")[0]
    assert len(placed) == 1 and placed[0].price == expected
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == original and updated.racks[1] == store.racks[1]
