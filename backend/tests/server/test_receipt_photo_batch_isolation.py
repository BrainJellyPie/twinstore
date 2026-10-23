"""A bad receipt photo must not discard other receipts already read in its batch."""

import csv
import io

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from store_emulator.application import vision_inputs
from store_emulator.application.errors import AppError
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.vision_inputs import ReceiptLine, ReceiptReading
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


def picture(size=8):
    out = io.BytesIO()
    Image.new("RGB", (size, size), "red").save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def receipts(layout, monkeypatch):
    seen = []
    monkeypatch.setattr(vision_inputs, "_client", lambda *args: object())
    monkeypatch.setattr(vision_inputs, "_receipt_target", lambda *args: ({"chips": "Chips"}, "USD"))

    async def read(client, image, *, receipt_id, default_currency):
        assert image.getpixel((0, 0)) == (255, 0, 0)
        seen.append(image)
        return ReceiptReading(receipt_id=receipt_id, currency=default_currency,
                              lines=[ReceiptLine(name="Chips", quantity=1, unit_price=300)])

    monkeypatch.setattr(vision_inputs, "vlm_receipt", read)
    return TestClient(app, raise_server_exceptions=False), seen


def bad_photo(kind, monkeypatch):
    if kind == "invalid":
        return b"not an image"
    if kind == "truncated":
        return picture()[:12]
    if kind == "oversize":
        monkeypatch.setattr(vision_inputs, "MAX_PHOTO_BYTES", 256)
        return b"x" * 257
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    return picture(64)


@pytest.mark.parametrize("kind", ["invalid", "truncated", "oversize", "dimensions"])
@pytest.mark.parametrize("bad_index", [0, 1, 2])
def test_bad_images_keep_other_reads_and_receipt_identifiers(receipts, monkeypatch, kind, bad_index):
    client, seen = receipts
    photos = [picture()] * 3
    photos[bad_index] = bad_photo(kind, monkeypatch)
    response = client.post(f"/api/projects/{PID}/receipts", data={"setup_id": SID},
        files=[("photos", (f"receipt-{i}.png", data, "image/png")) for i, data in enumerate(photos)])
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(seen) == 2
    assert [r["receipt_id"] for r in body["receipts"]] == ["r001", "r002", "r003"]
    failed = body["receipts"][bad_index]
    assert failed["lines"] == [] and failed["notes"]
    good = [r for i, r in enumerate(body["receipts"]) if i != bad_index]
    assert all(r["lines"][0]["matched"] and r["lines"][0]["unit_price"] == 300 for r in good)
    assert body["matched_lines"] == 2 and body["unmatched_lines"] == 0
    assert len(list(csv.DictReader(io.StringIO(body["csv"])))) == 2
    review = client.post(f"/api/projects/{PID}/receipts/review", json={"setup_id": SID, "receipts": body["receipts"]})
    assert not review.json()["ready"], "an unreadable receipt must still require exclusion or correction"


@pytest.mark.parametrize("kind", ["invalid", "truncated", "oversize", "dimensions"])
def test_all_bad_images_are_explicit_failures_without_model_calls(receipts, monkeypatch, kind):
    client, seen = receipts
    response = client.post(f"/api/projects/{PID}/receipts", data={"setup_id": SID},
        files=[("photos", ("bad.png", bad_photo(kind, monkeypatch), "image/png"))])
    assert response.status_code == 200, response.text
    body = response.json()
    assert not seen
    assert body["matched_lines"] == body["unmatched_lines"] == 0
    assert body["receipts"][0]["notes"] and not body["receipts"][0]["lines"]
    assert len(list(csv.DictReader(io.StringIO(body["csv"])))) == 0


@pytest.mark.parametrize("model_error", [False, True])
def test_decoded_photos_are_released_after_each_read(receipts, monkeypatch, model_error):
    client, seen = receipts
    original = vision_inputs.vlm_receipt

    async def read(*args, **kwargs):
        result = await original(*args, **kwargs)
        if model_error and kwargs["receipt_id"] == "r001":
            raise RuntimeError("offline model failure")
        return result

    monkeypatch.setattr(vision_inputs, "vlm_receipt", read)
    response = client.post(f"/api/projects/{PID}/receipts", data={"setup_id": SID},
        files=[("photos", ("good.png", picture(), "image/png"))] * 2)
    assert response.status_code == 200, response.text
    for image in seen:
        with pytest.raises(ValueError, match="closed image"):
            image.getpixel((0, 0))


@pytest.mark.parametrize("streamed", [False, True])
def test_empty_receipt_sources_remain_invalid(receipts, streamed):
    _, seen = receipts
    with pytest.raises(AppError, match="no receipt photo"):
        vision_inputs.read_receipts(PID, iter([]) if streamed else [], setup_id=SID, model="offline", config=SimulationConfig())
    assert not seen
