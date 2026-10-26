"""Nutrition quantities must not become exact selling prices."""
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
    ("100 kcal", "USD"), ("100kcal", "USD"), ("100 KCALS", "USD"),
    ("100 calories", "USD"), ("CALORIES 100", "USD"), ("Calories: 100", "USD"),
    ("Calories per serving: 100", "USD"), ("Energy 100 kJ", "USD"),
    ("100 kilojoules", "USD"), ("Energy (kJ) 100", "USD"), ("100 (kcal)", "USD"),
    ("100 IU", "USD"), ("100 international units", "USD"),
    ("１００ｋｃａｌ", "USD"), ("100칼로리", "KRW"), ("열량 100", "KRW"),
    ("100カロリー", "JPY"), ("100キロカロリー", "JPY"),
    ("100千卡", "CNY"), ("热量100", "CNY"), ("熱量100", "TWD"),
    ("100千焦", "CNY"), ("100大卡", "CNY"),
    ("100 calorías", "EUR"), ("Calorías 100", "EUR"),
])
@pytest.mark.parametrize("guess", [None, 12.34, 2026.0])
def test_nutrition_quantities_cannot_be_overridden_by_a_model_price_guess(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,currency,expected", [
    ("$1.00", "USD", 100), ("$0.00", "USD", 0), ("100¢", "USD", 100),
    ("100", "USD", 100), ("PRICE 100", "USD", 100),
    ("Calorie drink $1.00", "USD", 100), ("CALORIES USD 1.00", "USD", 100),
    ("Energy $1.00", "USD", 100), ("Calypso $1.00", "USD", 100),
    ("1,000원", "KRW", 1000), ("100円", "JPY", 100), ("1,00 €", "EUR", 100),
])
def test_cash_prices_and_ordinary_numeric_tags_remain_usable(tag, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag), currency, 249) == expected


@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("tag", ["100 kcal", "CALORIES 100", "ENERGY 100 kJ"])
def test_a_nutrition_label_preserves_identity_and_the_existing_selling_price(known, tag):
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
