"""A printed price bound must not overwrite a product with an exact amount."""
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
    ("FROM $1.00", "USD"), ("Prices from: USD 1.00", "USD"),
    ("Starting at £1.00", "GBP"), ("Starting from €1,00", "EUR"),
    ("Starting price: $1", "USD"), ("As low as $1.00", "USD"),
    ("At least $1", "USD"), ("More than $1", "USD"),
    ("UNDER $1.00", "USD"), ("Below $1.00", "USD"),
    ("Over $1", "USD"), ("Above $1", "USD"),
    ("Up to $1", "USD"), ("At most $1", "USD"), ("Less than $1", "USD"),
    ("$1 and up", "USD"), ("$1 or more", "USD"), ("$1 or less", "USD"),
    ("$1+", "USD"), ("≤ $1", "USD"), ("≥ USD 1", "USD"),
    ("$1 <", "USD"), ("$1 >", "USD"), ("$0.00+", "USD"),
    ("ＦＲＯＭ ＄１．００", "USD"), ("＜＄１．００", "USD"),
    ("1,000원부터", "KRW"), ("최저가 1,000원", "KRW"),
    ("1,000원 이상", "KRW"), ("1,000원 이하", "KRW"),
    ("1,000원 미만", "KRW"), ("1,000원 초과", "KRW"),
    ("100円から", "JPY"), ("100円以上", "JPY"),
    ("100円以下", "JPY"), ("100円未満", "JPY"), ("最低100円", "JPY"),
    ("CNY 10起", "CNY"), ("100¢ and up", "USD"),
    ("LIMIT 2 PER CUSTOMER", "USD"), ("Limit: 2", "EUR"),
    ("Limit of 2 per household", "GBP"), ("LIMIT $2", "USD"),
    ("MAX 2 PER PERSON", "USD"), ("Max. 2", "EUR"), ("Maximum 2", "GBP"),
    ("MIN 2 PER ORDER", "USD"), ("Min. 2", "EUR"), ("Minimum 2", "GBP"),
    ("Maximum: USD 2", "USD"), ("Minimum: 1,000원", "KRW"),
    ("$2 maximum", "USD"), ("$2 max.", "USD"), ("2 minimum", "JPY"), ("2 min.", "EUR"),
    ("ＬＩＭＩＴ ２ ＰＥＲ ＣＵＳＴＯＭＥＲ", "USD"), ("ＭＡＸ．２", "USD"),
])
@pytest.mark.parametrize("guess", [None, 1.0, 1000.0])
def test_price_limits_cannot_be_overridden_by_a_model_guess(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,currency,expected", [
    ("$1.00", "USD", 100), ("$0.00", "USD", 0), ("$1 EACH", "USD", 100),
    ("Fromage $1.00", "USD", 100), ("From the farm $1.00", "USD", 100),
    ("$1.00 + tax", "USD", 100), ("$1.00 + deposit", "USD", 100),
    ("Lowest price guaranteed: $1", "USD", 100),
    ("1,000원", "KRW", 1000), ("최저가 보장 1,000원", "KRW", 1000),
    ("100円", "JPY", 100), ("1,00 €", "EUR", 100), ("100¢", "USD", 100),
    ("LIMITED OFFER $1.00", "USD", 100), ("Limitless $1", "USD", 100),
    ("Mini $1", "USD", 100), ("Maxi $1", "USD", 100), ("Maxwell $1", "USD", 100),
    ("Maximum flavor $1", "USD", 100), ("Minimum fuss $1", "USD", 100),
])
def test_exact_cash_prices_and_product_names_are_preserved(tag, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag), currency, 249) == expected


@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("tag", ["FROM $1.00", "UNDER $1.00", "$1 and up", "LIMIT 2 PER CUSTOMER", "MAX 2", "MINIMUM 2"])
def test_a_price_limit_preserves_capture_identity_and_an_existing_selling_price(known, tag):
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
        assert items[0].labeled and items[0].name == "Cola 500ml" and items[0].price_text == tag
        assert items[0].price_estimated
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    expected = 799 if known else typical_price("soft_drinks", "Cola 500ml", "USD")[0]
    assert len(placed) == 1 and placed[0].price == expected
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == original and updated.racks[1] == store.racks[1]
