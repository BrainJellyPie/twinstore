"""One unusable model-read price must not discard an otherwise recognized shelf."""

import math

import pytest
from PIL import Image

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.engine.capture.catalog_match import price_minor_units, typical_price
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.recognize import FacingGroup, describe


@pytest.mark.parametrize("value", [None, -math.inf, math.inf, math.nan, -1, 0, 5e-324,
                                   .001, .004, .005, .01, .1, .5, .51, 1.8, 249, 1e306, 1e308])
@pytest.mark.parametrize("currency", ["USD", "EUR", "KRW", "JPY"])
@pytest.mark.parametrize("typical", [None, 1, 200])
@pytest.mark.parametrize("text", ["", "1,800원", "???"])
def test_all_accepted_numeric_price_boundaries_are_convertible_or_unreadable(value, currency, typical, text):
    result = price_minor_units(ShelfItemLabel(price=value, price_text=text), currency, typical)
    assert result is None or isinstance(result, int) and result > 0
    if text:
        # A readable tag takes precedence over an invalid numeric guess.
        if text == "1,800원":
            assert result == price_minor_units(ShelfItemLabel(price_text=text), currency, typical)


@pytest.mark.parametrize("currency", ["USD", "EUR", "KRW", "JPY"])
@pytest.mark.parametrize("value", [math.inf, math.nan, -math.inf, 5e-324])
def test_nonrepresentable_prices_remain_explicitly_unreadable(currency, value):
    assert price_minor_units(ShelfItemLabel(price=value), currency, 200) is None


@pytest.mark.parametrize("currency", ["KRW", "JPY"])
@pytest.mark.parametrize("value,expected", [(.001, 1), (.01, 10), (.1, 100), (.5, 500)])
def test_thousand_unit_abbreviations_survive_a_literal_rounding_to_zero(currency, value, expected):
    label = ShelfItemLabel(price=value)
    assert price_minor_units(label, currency, 200) == expected
    # No category price means there is no evidence for interpreting an abbreviation.
    assert price_minor_units(label, currency, None) is None


@pytest.mark.parametrize("value", [.001, .005, math.inf, 1e308])
def test_invalid_price_does_not_discard_other_recognized_products(value):
    image = Image.new("RGB", (100, 80), "white")
    frame = make_frame(image)
    labels = [ShelfItemLabel(name="Cola 500ml", category="soft drink", price=value),
              ShelfItemLabel(name="Mineral Water 500ml", category="water", price_text="$1.25")]
    groups = []
    for i, label in enumerate(labels):
        detection = Detection(x1=i * 50, y1=0, x2=i * 50 + 40, y2=60, band=0)
        groups.append(FacingGroup(band=0, facings=[detection], descriptor=describe(image, detection), label=label))
    items, _ = build_items(frame, groups, [3], currency="USD", rack_type="shelf")
    assert len(items) == 2 and all(item.labeled for item in items)
    assert items[0].price_estimated and items[0].price == typical_price("soft_drinks", "Cola 500ml", "USD")[0]
    assert not items[1].price_estimated and items[1].price == 125
