"""Savings amounts must not become exact selling prices after correct OCR."""
import pytest
from PIL import Image

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.engine.capture.catalog_match import price_minor_units, typical_price
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.recognize import FacingGroup, describe


SAVINGS = [
    ("SAVE $1.00", "USD"), ("You save USD 1.00", "USD"), ("Savings $1", "USD"),
    ("$1.00 OFF", "USD"), ("1.00 USD off", "USD"), ("SAVE 100¢", "USD"),
    ("ＣＯＵＰＯＮ ＄１．００", "USD"), ("Coupon value $1", "USD"),
    ("Rebate $1.00", "USD"), ("$1.00 cashback", "USD"),
    ("Discount $1.00", "USD"), ("1,000원 할인", "KRW"), ("할인액 1,000원", "KRW"),
    ("1,000원 절약", "KRW"), ("100円引き", "JPY"), ("100円割引", "JPY"),
    ("値引き100円", "JPY"), ("SAVE €1,00", "EUR"), ("SAVE £1.00", "GBP"),
    ("WAS $1.00", "USD"), ("was: USD 1.00", "USD"), ("MSRP $1.00", "USD"),
    ("RRP £1.00", "GBP"), ("ＷＡＳ： ＄１．００", "USD"), ("SAVE: $1.00", "USD"),
    ("SAVE UP TO $1.00", "USD"), ("Save up to: USD 1", "USD"),
    ("SAVE AT LEAST £1.00", "GBP"), ("Save as much as €1,00", "EUR"),
    ("Rebate up to $1.00", "USD"), ("Coupon value up to $1", "USD"),
    ("Cash back $1.00", "USD"), ("Cash-back: USD 1.00", "USD"),
    ("$1.00 CASH BACK", "USD"), ("$1.00 cash-back", "USD"),
    ("SAVE UP TO $0.00", "USD"), ("$0.00 CASH BACK", "USD"),
    ("ＳＡＶＥ ＵＰ ＴＯ ＄１．００", "USD"),
]


@pytest.mark.parametrize("tag,currency", SAVINGS)
@pytest.mark.parametrize("guess", [None, 1.0, 1000.0])
def test_savings_text_cannot_be_overridden_by_a_numeric_model_guess(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,currency,amount", [
    ("$1.00", "USD", 100), ("SALE $1.00", "USD", 100), ("Special offer $1.00", "USD", 100),
    ("Discount price $1.00", "USD", 100), ("Coupon price $1.00", "USD", 100),
    ("$1.00 with coupon", "USD", 100), ("$1.00 EACH", "USD", 100),
    ("할인가 1,000원", "KRW", 1000), ("할인 가격 1,000원", "KRW", 1000),
    ("割引価格100円", "JPY", 100), ("$2.49", "USD", 249), ("249¢", "USD", 249),
    ("NOW $1.00", "USD", 100), ("Our price: $1.00", "USD", 100), ("Wasabi $1.00", "USD", 100),
    ("Cash price $1.00", "USD", 100), ("Cashback price $1.00", "USD", 100),
    ("Save Mart $1.00", "USD", 100), ("$1.00 after cashback", "USD", 100),
])
def test_explicit_sale_prices_and_ordinary_prices_keep_their_amount(tag, currency, amount):
    assert price_minor_units(ShelfItemLabel(price_text=tag), currency, 999) == amount


@pytest.mark.parametrize("guess", [None, 1.0])
@pytest.mark.parametrize("tag", ["SAVE $1.00", "SAVE UP TO $1.00", "$1.00 CASH BACK"])
def test_capture_preserves_product_and_tag_but_marks_savings_fallback_estimated(guess, tag):
    with Image.new("RGB", (100, 80), "white") as photo:
        frame = make_frame(photo)
        groups = []
        for index, label in enumerate([
            ShelfItemLabel(name="Cola", category="soft drink", price_text=tag, price=guess),
            ShelfItemLabel(name="Mineral Water 500ml", category="water", price_text="$1.25"),
        ]):
            detection = Detection(x1=index * 50, y1=0, x2=index * 50 + 40, y2=60, band=0)
            groups.append(FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label))
        items, _ = build_items(frame, groups, [3], currency="USD", rack_type="shelf")
    assert len(items) == 2 and all(item.labeled for item in items)
    assert items[0].name == "Cola" and items[0].price_text == tag
    assert items[0].price_estimated and items[0].price == typical_price("soft_drinks", "Cola", "USD")[0]
    assert items[1].price == 125 and not items[1].price_estimated
