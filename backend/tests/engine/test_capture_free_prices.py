"""Explicit zero-price tags must survive capture and existing-SKU placement."""
import pytest
from PIL import Image

from store_emulator.domain.capture import CaptureResult, ShelfItemLabel
from store_emulator.engine.capture.catalog_match import price_minor_units
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.planogram import replace_rack_face
from store_emulator.engine.capture.recognize import FacingGroup, describe
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("tag,currency", [
    ("FREE $0.00", "USD"), ("$0", "USD"), ("0 USD", "USD"), ("0 cents", "USD"),
    ("0,00 €", "EUR"), ("0원", "KRW"), ("0円", "JPY"), ("ＦＲＥＥ ＄０．００", "USD"),
])
@pytest.mark.parametrize("guess", [None, 0, 2.49])
def test_explicit_zero_price_outranks_a_catalog_estimate_or_numeric_guess(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) == 0


@pytest.mark.parametrize("tag", ["", "0", "0.00", "FREE", "unreadable"])
@pytest.mark.parametrize("guess", [None, 0])
def test_missing_price_or_unqualified_zero_remains_unknown(tag, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), "USD", 249) is None


@pytest.mark.parametrize("tag,currency", [
    ("$-0.00", "USD"), ("$0.00 OFF", "USD"), ("SAVE $0.00", "USD"), ("WAS $0.00", "USD"),
    ("$0.004", "USD"), ("0.001원", "KRW"), ("0%", "USD"),
    ("$0.00", "KRW"), ("0원", "USD"), ("$0.00 or $1.00", "USD"),
])
@pytest.mark.parametrize("guess", [0, 2.49])
def test_ambiguous_wrong_currency_or_rounded_down_amount_does_not_become_free(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("known", [False, True])
def test_zero_survives_capture_and_replaces_an_existing_paid_offer(known):
    store = target_store()
    if not known:
        store.racks[0].slots = []
    before = store.model_dump_json()
    with Image.new("RGB", (100, 80), "white") as photo:
        detection = Detection(x1=0, y1=0, x2=40, y2=60, band=0)
        label = ShelfItemLabel(name="Cola 500ml", category="soft drink", price_text="FREE $0.00", price=0)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label)
        items, _ = build_items(make_frame(photo), [group], [3], currency="USD", rack_type="shelf")
        assert items[0].price == 0 and not items[0].price_estimated
        assert items[0].price_text == "FREE $0.00"
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    assert len(placed) == 1 and placed[0].price == 0
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == before and updated.racks[1] == store.racks[1]
