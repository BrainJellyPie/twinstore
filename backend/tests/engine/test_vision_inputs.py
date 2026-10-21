"""Photo inputs offline: storefront appeal from image statistics or a fake VLM; receipts with a fake VLM
matched to store products and written as a POS export the fidelity parser reads."""

import asyncio

from PIL import Image, ImageDraw
from pydantic import BaseModel

from store_emulator.application.pos import parse_pos_csv
from store_emulator.engine.vision_inputs import (
    attractiveness_for,
    classic_appeal,
    match_lines,
    receipts_csv,
    vlm_appeal,
    vlm_receipt,
)


def storefront(bright: bool) -> Image.Image:
    img = Image.new("RGB", (640, 480), (220, 216, 205) if bright else (40, 38, 36))
    d = ImageDraw.Draw(img)
    if bright:
        d.rectangle((40, 30, 600, 110), fill=(200, 30, 40))
        for x in range(60, 580, 40):
            d.text((x, 55), "SHOP", fill=(255, 255, 255))
        d.rectangle((80, 160, 560, 440), fill=(250, 240, 180))
        for i, c in enumerate([(40, 120, 220), (230, 160, 30), (40, 170, 90)]):
            d.rectangle((110 + i * 140, 300, 200 + i * 140, 420), fill=c)
    return img


def test_image_statistics_prefer_a_bright_colourful_front() -> None:
    lively, dull = classic_appeal(storefront(True)), classic_appeal(storefront(False))
    assert lively.overall > dull.overall and lively.attractiveness > dull.attractiveness
    assert lively.method == "image_stats" and 0.5 <= dull.attractiveness <= 1.5


def test_attractiveness_scale() -> None:
    assert attractiveness_for(5) == 1.0 and attractiveness_for(10) == 1.4 and attractiveness_for(0) == 0.6


class _Fake:
    def __init__(self, answer: dict[str, object]) -> None:
        self.answer = answer

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        return response_model.model_validate(self.answer)


def test_vlm_storefront_rating() -> None:
    fake = _Fake({"signage": 8, "entrance": 7, "window": 9, "upkeep": 8, "overall": 8, "reasons": "bright sign, open door"})
    appeal = asyncio.run(vlm_appeal(fake, storefront(True), model="fake"))
    assert appeal.method == "vlm" and appeal.overall == 8 and appeal.attractiveness == 1.24


def test_receipt_lines_become_a_pos_export() -> None:
    fake = _Fake({"store": "Sample store", "date": "2026-10-21", "time": "14:05", "currency": "USD", "total": 6.47, "lines": [
        {"name": "COCA-COLA CLASSIC 20OZ", "quantity": 2, "unit_price": 2.49, "line_total": 4.98},
        {"name": "Mystery item", "quantity": 1, "unit_price": 1.49},
    ]})
    reading = asyncio.run(vlm_receipt(fake, storefront(False), receipt_id="r001"))
    assert reading.total == 647 and reading.lines[0].unit_price == 249 and reading.timestamp == "2026-10-21 14:05"
    matched = match_lines(reading, {"A0009": "Coca-Cola Classic 20oz", "A0002": "Pepsi 20oz"})
    assert [line.matched for line in matched.lines] == [True, False] and matched.lines[0].sku == "A0009"
    csv = receipts_csv([matched])
    pos = parse_pos_csv(csv.encode(), "receipts.csv")
    assert len(pos) == 1 and pos[0].sku == "A0009" and pos[0].quantity == 2 and pos[0].unit_price == 249 and pos[0].hour == 14
