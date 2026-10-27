"""A visible currency mark must not be discarded by the price-unit heuristic."""

import unicodedata

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


CURRENCIES = [("THB", "฿"), ("RUB", "₽"), ("TRY", "₺"), ("PHP", "₱"),
              ("ILS", "₪"), ("UAH", "₴"), ("NGN", "₦")]


@pytest.mark.parametrize("tag", ["B100", "B 100", "P100", "P 100", "100 B", "100 P", "Ｐ１００", "B.99"])
@pytest.mark.parametrize("currency", ["USD", "THB", "PHP"])
@pytest.mark.parametrize("guess", [None, 1, 100])
def test_an_unresolved_letter_is_not_a_reliable_currency_or_unmarked_price(tag, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), currency, 249) is None


@pytest.mark.parametrize("tag,currency,expected", [("ITEM $1.00", "USD", 100), ("GRADE B $1.00", "USD", 100),
    ("d1000", "VND", 1000), ("1000 d", "VND", 1000), ("USD100", "USD", 10000),
    ("100 cents", "USD", 100), ("PRICE 1.00", "USD", 100), ("25 lei", "RON", 2500)])
def test_printed_units_and_existing_price_wording_still_establish_a_price(tag, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=tag), currency, None) == expected


@pytest.mark.parametrize("code,sign", CURRENCIES)
@pytest.mark.parametrize("guess", [None, 1, 100])
@pytest.mark.parametrize("store_currency", ["USD", "KRW", "RON"])
def test_foreign_marks_and_codes_cannot_override_the_store_currency(code, sign, guess, store_currency):
    for tag in [f"{sign}100", f"100 {sign}", f"{code}100", f"100 {code.lower()}"]:
        assert price_minor_units(ShelfItemLabel(price_text=tag, price=guess), store_currency, 249) is None, tag


@pytest.mark.parametrize("code,sign", CURRENCIES)
@pytest.mark.parametrize("amount,expected", [("100", 10000), ("0", 0), ("0.01", 1), ("1,000", 100000), ("１００", 10000)])
def test_matching_marks_preserve_literal_major_units(code, sign, amount, expected):
    for tag in [f"{sign}{amount}", f"{amount} {sign}", f"{code} {amount}"]:
        assert price_minor_units(ShelfItemLabel(price_text=tag, price=1), code.lower(), 249) == expected, tag


@pytest.mark.parametrize("code,sign", CURRENCIES)
@pytest.mark.parametrize("template", ["SAVE {}100", "{}100 OFF", "FROM {}100", "{}100+",
    "-{}100", "{}100 / L", "DEPOSIT {}100", "{}100 USD", "{}100 ¤"])
def test_matching_currency_keeps_non_selling_and_conflicting_price_guards(code, sign, template):
    assert price_minor_units(ShelfItemLabel(price_text=template.format(sign), price=100), code, 249) is None


@pytest.mark.parametrize("tag", ["¤100", "₿100", "₨100", "﷼100", "$1.00 ¤", "¤", "₿", "﷼"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "RON", "THB"])
def test_unresolved_currency_symbols_are_not_erased_even_by_normalization(tag, currency):
    assert any(unicodedata.category(char) == "Sc" for char in tag)
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=100), currency, 249) is None


@pytest.mark.parametrize("tag", ["$100", "€100", "¥100", "₹100", "₩100", "￦１００", "＄１００"])
def test_a_store_without_a_known_symbol_does_not_adopt_foreign_symbols(tag):
    assert price_minor_units(ShelfItemLabel(price_text=tag, price=100), "RON", 249) is None


@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("tag", ["฿100", "₽100", "THB100", "¤100", "P100", "B 100"])
def test_foreign_or_unknown_price_preserves_product_identity_and_existing_price(known, tag):
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
