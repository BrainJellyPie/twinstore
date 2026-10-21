"""OCR currency text is normalized before converting printed receipt amounts."""

import asyncio

import pytest
from PIL import Image

from store_emulator.application.pos import parse_pos_csv
from store_emulator.domain.vision_inputs import ReceiptReading
from store_emulator.engine.receipt_review import review_receipts
from store_emulator.engine.vision_inputs import match_lines, vlm_receipt
from tests.engine.test_vision_inputs import _Fake


@pytest.mark.parametrize("printed,default,currency,minor", [
    (" KRW ", "USD", "KRW", 1234),
    ("\t jpy\n", "USD", "JPY", 1234),
    (" usd ", "KRW", "USD", 123400),
    ("   ", "JPY", "JPY", 1234),
    ("", " KRW ", "KRW", 1234),
    ("", "USD", "USD", 123400),
    ("KRW", "USD", "KRW", 1234),
    ("jpy", "USD", "JPY", 1234),
])
def test_ocr_currency_whitespace_preserves_minor_units_through_review(printed, default, currency, minor):
    fake = _Fake({"currency": printed, "date": "2026-10-21", "time": "10:00", "total": 2468,
                  "lines": [{"name": "Tea", "quantity": 2, "unit_price": 1234, "line_total": 2468}]})
    receipt: ReceiptReading = asyncio.run(vlm_receipt(fake, Image.new("RGB", (2, 2)), receipt_id="r1", default_currency=default))
    assert receipt.lines[0].unit_price == minor
    assert receipt.lines[0].line_total == receipt.total == minor * 2
    assert receipt.currency == currency
    review = review_receipts([match_lines(receipt, {"tea": "Tea"})], {"tea": "Tea"}, currency)
    assert review.ready
    pos = parse_pos_csv(review.csv.encode())
    assert pos[0].unit_price == minor and pos[0].quantity == 2
