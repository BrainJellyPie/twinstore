"""A price per measure is not an exact price for the observed package."""
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
    ("$1.00 / L", "USD"), ("USD/kg 1.00", "USD"), ("$1 per litre", "USD"),
    ("1,00 € / liter", "EUR"), ("$1/lb", "USD"), ("$1 per pound", "USD"),
    ("$1/oz", "USD"), ("$1 per fl. oz", "USD"), ("$1 per gram", "USD"),
    ("$1 / ml", "USD"), ("1000원/㎏", "KRW"), ("100円/ℓ", "JPY"),
    ("＄１．００／Ｌ", "USD"), ("$1∕kg", "USD"), ("$1⁄kg", "USD"),
    ("1000원 / 리터", "KRW"), ("$0.00/kg", "USD"),
    ("리터당 1,000원", "KRW"), ("1,000원 kg당", "KRW"),
    ("kg当たり100円", "JPY"), ("1,000원 그램당", "KRW"),
])
@pytest.mark.parametrize("guess", [None, 0, 1.0])
def test_measure_rates_cannot_override_a_package_price(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag", ["$1.00", "$1 each", "$1/ea", "$1 per item", "$1 / bottle",
                                 "$1 per pack", "Pepper L $1.00", "$1 / large"])
def test_product_unit_prices_remain_exact(tag):
    assert price_minor_units(ShelfItemLabel(price_text=tag), "USD", 249) == 100


def test_unit_rate_preserves_the_product_and_an_existing_package_price():
    store = target_store()
    store.racks[0].slots[0].items[0].price = 375
    before = store.model_dump_json()
    with Image.new("RGB", (100, 80), "white") as photo:
        detection = Detection(x1=0, y1=0, x2=40, y2=60, band=0)
        label = ShelfItemLabel(name="Cola 500ml", category="soft drink", price_text="$1.00 / L", price=1)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label)
        items, _ = build_items(make_frame(photo), [group], [3], currency="USD", rack_type="shelf")
        assert items[0].labeled and items[0].price_estimated and items[0].price_text == "$1.00 / L"
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    assert len(placed) == 1 and placed[0].price == 375
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == before and updated.racks[1] == store.racks[1]
