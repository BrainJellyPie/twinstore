"""Measure rates and bare quantities do not establish a package selling price."""
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


@pytest.mark.parametrize("tag,currency", [
    ("500 ml", "USD"), ("NET 500 mL", "EUR"), ("0.5 L", "GBP"),
    ("500 g", "JPY"), ("500㎖", "KRW"), ("500그램", "KRW"), ("1 kg", "USD"),
    ("500 mg", "USD"), ("12 fl oz", "USD"), ("6 PACK", "USD"), ("1 pack", "USD"),
    ("pack of 6", "USD"), ("6 pk", "USD"), ("6 bottles", "USD"), ("6병", "KRW"),
    ("6本入り", "JPY"), ("6 count", "USD"), ("0 ml", "USD"),
])
@pytest.mark.parametrize("guess", [None, 1.0, 500.0])
def test_bare_sizes_and_pack_counts_are_not_selling_prices(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,currency,expected", [
    ("$6 PACK", "USD", 600), ("USD 6 pack", "USD", 600), ("6 USD pack", "USD", 600),
    ("$1 BOTTLE", "USD", 100), ("1,000원 병", "KRW", 1000),
    ("500", "USD", 500), ("$500", "USD", 50000), ("249¢", "USD", 249),
])
def test_cash_units_and_unqualified_numeric_tags_keep_existing_interpretations(tag, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag), currency, 249) == expected


@pytest.mark.parametrize("tag", ["$1.00 / L", "500 ml", "6 PACK", "pack of 6"])
def test_non_selling_measure_preserves_the_product_and_an_existing_package_price(tag):
    store = target_store()
    store.racks[0].slots[0].items[0].price = 375
    before = store.model_dump_json()
    with Image.new("RGB", (100, 80), "white") as photo:
        detection = Detection(x1=0, y1=0, x2=40, y2=60, band=0)
        label = ShelfItemLabel(name="Cola 500ml", category="soft drink", price_text=tag, price=1)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label)
        items, _ = build_items(make_frame(photo), [group], [3], currency="USD", rack_type="shelf")
        assert items[0].labeled and items[0].price_estimated and items[0].price_text == tag
        updated, report = replace_rack_face(store, CaptureResult(image_size=photo.size, currency="USD", items=items), "r1")
    placed = [item for slot in updated.racks[0].slots for item in slot.items]
    assert len(placed) == 1 and placed[0].price == 375
    assert report.placed_items == 1 and not report.dropped
    assert store.model_dump_json() == before and updated.racks[1] == store.racks[1]
