"""Printed prices use the app's currency units and never merge ambiguous amounts."""

import random

import pytest
from PIL import Image

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.engine.capture.catalog_match import price_minor_units, typical_price
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.recognize import FacingGroup, describe
from store_emulator.engine.prompting import display_price

CURRENCIES = ["KRW", "JPY", "VND", "IDR", "CLP", "ISK", "HUF", "TWD", "USD", "EUR"]
AMBIGUOUS = ["1.2,3.45", "1,2.3,45", "2.49 3.99", "2.49\n3.99", "1.2.3", "1,,234",
             "1..234", "1,23,456,7", "-2.49", "-$2.49", "−2.49", "20% OFF", "2 for $5",
             "$2.49–$3.99", "1e3", "($2.49)"]


def test_prices_printed_by_the_app_round_trip_in_every_supported_unit_convention():
    rng = random.Random(261023227)
    amounts = [1, 49, 100, 1234, 1234567, *(rng.randrange(1, 10_000_000) for _ in range(60))]
    for currency in CURRENCIES:
        for amount in amounts:
            label = ShelfItemLabel(price_text=display_price(amount, currency))
            assert price_minor_units(label, currency.lower(), None) == amount, (currency, amount, label.price_text)


@pytest.mark.parametrize("text,currency,expected", [
    ("$2.49", "USD", 249), ("12,50 €", "EUR", 1250), ("1,800원", "KRW", 1800),
    ("1.800", "KRW", 1800), ("1 800원", "KRW", 1800), ("1\u202f234,50 €", "EUR", 123450),
    ("1,234.50 USD", "USD", 123450), ("1.234,50 EUR", "EUR", 123450),
    ("CHF 1'234.50", "CHF", 123450), ("CHF 1’234.50", "CHF", 123450),
    ("1,23,456.78 INR", "INR", 12345678), ("＄１，２３４．５０", "USD", 123450),
    ("$.49", "USD", 49), (",49 €", "EUR", 49), ("25000.00 VND", "VND", 25000),
])
def test_unambiguous_localized_price_formats(text, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=text), currency, None) == expected


@pytest.mark.parametrize("text,currency,typical,expected", [
    ("$249", "USD", 229, 24900), ("249 USD", "USD", 229, 24900),
    ("249 €", "EUR", 229, 24900), ("£249", "GBP", 229, 24900),
    ("₩1.8", "KRW", 2000, 2), ("1.8 JPY", "JPY", 2000, 2),
    ("249¢", "USD", None, 249), ("249¢", "USD", 229, 249),
    ("249 cents", "EUR", None, 249), ("249 USD cents", "USD", 229, 249),
    ("249¢", "KRW", 2000, None), ("$249¢", "USD", 229, None),
    ("$0.004", "USD", 229, None), ("0.001원", "KRW", 2000, None),
    ("249", "USD", 229, 249), ("1.8", "KRW", 2000, 1800),
])
def test_explicit_price_units_take_precedence_over_catalog_guesses(text, currency, typical, expected):
    assert price_minor_units(ShelfItemLabel(price_text=text), currency, typical) == expected


@pytest.mark.parametrize("text", AMBIGUOUS)
def test_ambiguous_or_negative_tag_is_unreadable_even_with_a_numeric_guess(text):
    for currency in ("USD", "KRW", "VND"):
        for numeric in (None, 2.49):
            assert price_minor_units(ShelfItemLabel(price_text=text, price=numeric), currency, 249) is None


@pytest.mark.parametrize("text", ["1.2,3.45", "2.49 3.99", "-2.49", "20% OFF"])
def test_one_bad_tag_does_not_discard_a_recognized_shelf_or_look_like_a_read_price(text):
    image = Image.new("RGB", (100, 80), "white")
    labels = [ShelfItemLabel(name="Cola 500ml", category="soft drink", price_text=text, price=2.49),
              ShelfItemLabel(name="Mineral Water 500ml", category="water", price_text="$1.25")]
    groups = []
    for index, label in enumerate(labels):
        detection = Detection(x1=index * 50, y1=0, x2=index * 50 + 40, y2=60, band=0)
        groups.append(FacingGroup(band=0, facings=[detection], descriptor=describe(image, detection), label=label))
    items, _ = build_items(make_frame(image), groups, [3], currency="USD", rack_type="shelf")
    assert len(items) == 2 and all(item.labeled for item in items)
    assert items[0].price_estimated
    assert items[0].price == typical_price("soft_drinks", "Cola 500ml", "USD")[0]
    assert items[1].price == 125 and not items[1].price_estimated
