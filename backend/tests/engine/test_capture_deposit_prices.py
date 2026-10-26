"""A correctly read bottle deposit must not replace a product's selling price."""
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
    ("DEPOSIT $0.10", "USD"), ("$0.10 DEPOSIT", "USD"),
    ("Bottle deposit: USD 0.10", "USD"), ("Refundable deposit 10¢", "USD"),
    ("0,25 € deposit", "EUR"), ("ＤＥＰＯＳＩＴ ＄０．１０", "USD"),
    ("DEPOSIT $0.00", "USD"), ("$0 DEPOSIT", "USD"),
])
@pytest.mark.parametrize("guess", [None, 0.1, 2.49])
def test_deposit_amount_is_not_a_selling_price_even_with_numeric_model_guess(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag", [
    "DEPOSIT INCLUDED $1.00", "$1.00 DEPOSIT INCLUDED", "$1.00 incl. deposit",
    "Including deposit: $1.00", "Includes bottle deposit $1.00", "With deposit $1.00",
    "Incl. container deposit $1.00", "$1.00 + deposit", "Deposit-free $1.00",
    "$1.00 deposit-free", "$1.00", "SALE $1.00", "$1.00 WITH COUPON",
])
def test_sale_prices_and_explicit_deposit_inclusion_keep_their_amount(tag):
    assert price_minor_units(ShelfItemLabel(price_text=tag), "USD", 999) == 100


@pytest.mark.parametrize("known", [False, True])
def test_deposit_capture_is_estimated_and_preserves_an_existing_product_price(known):
    store = target_store()
    existing_price = store.racks[0].slots[0].items[0].price
    if not known:
        store.racks[0].slots = []
    original = store.model_dump_json()
    with Image.new("RGB", (100, 80), "white") as photo:
        detection = Detection(x1=0, y1=0, x2=40, y2=60, band=0)
        label = ShelfItemLabel(name="Cola 500ml", category="soft drink", price_text="DEPOSIT $0.10", price=.1)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label)
        items, _ = build_items(make_frame(photo), [group], [3], currency="USD", rack_type="shelf")
        expected = typical_price("soft_drinks", "Cola 500ml", "USD")[0]
        assert items[0].labeled and items[0].price_text == "DEPOSIT $0.10"
        assert items[0].price_estimated and items[0].price == expected
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    assert len(placed) == 1 and placed[0].price == (existing_price if known else expected)
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == original and updated.racks[1] == store.racks[1]
