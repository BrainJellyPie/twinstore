"""A decorative crop outside the photo must not prevent applying a reviewed shelf."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.images import load_manifest
from store_emulator.application.storage.io import write_json
from store_emulator.domain.capture import Box, CaptureItem, CaptureResult, CaptureStatus
from tests.server.test_capture_api import PID, SETUP


@pytest.mark.parametrize("box,expected_size", [
    ((400, 10, 400, 60), None), ((10, 300, 60, 300), None),
    ((450, 10, 400, 60), None), ((10, 350, 60, 300), None),
    ((-80, 10, -40, 60), None), ((10, -80, 60, -40), None),
    ((10.1, 10.1, 10.4, 10.4), None), ((390, 290, 420, 320), (10, 10)),
    ((-20, -10, 20, 30), (20, 30)), ((40, 50, 140, 180), (100, 130)),
])
def test_apply_skips_empty_thumbnails_and_clips_partial_ones(tmp_path, monkeypatch, box, expected_size):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        folder = tmp_path / ".data" / PID / "captures" / "cap_border"
        result = CaptureResult(image_size=(400, 300), items=[
            CaptureItem(id="i1", band=0, level=3, order=0, name="Visible bottle", sku="border-visible", price=199,
                        labeled=True, category="soft_drinks", boxes=[Box(x1=30, y1=40, x2=90, y2=160)]),
            CaptureItem(id="i2", band=0, level=3, order=1, name="Reviewed bottle", sku="border-reviewed", price=299,
                        labeled=True, category="soft_drinks", boxes=[Box(x1=box[0], y1=box[1], x2=box[2], y2=box[3])]),
        ])
        write_json(folder / "result.json", result.model_dump(mode="json"))
        write_json(folder / "status.json", CaptureStatus(capture_id="cap_border", status="completed").model_dump(mode="json"))
        Image.new("RGB", (400, 300), "red").save(folder / "image.jpg")
        original = client.get(f"/api/projects/{PID}/setups/{SETUP}").json()
        applied = client.post(f"/api/projects/{PID}/captures/cap_border/apply", json={"setup_id": SETUP, "new_rack": True})
        assert applied.status_code == 200, applied.text
        data = applied.json()
        saved = client.get(f"/api/projects/{PID}/setups/{data['setup_id']}").json()
        stocks = {i["sku"] for r in saved["store"]["racks"] for s in r["slots"] for i in s["items"]}
        assert {"border-visible", "border-reviewed"} <= stocks
        assert client.get(f"/api/projects/{PID}/setups/{SETUP}").json() == original
        manifest = load_manifest(PID)
        assert "border-visible" in manifest
        assert ("border-reviewed" in manifest) == (expected_size is not None)
        if expected_size is not None:
            image = client.get(f"/api/projects/{PID}/images/border-reviewed")
            assert image.status_code == 200
            with Image.open(io.BytesIO(image.content)) as thumbnail:
                assert thumbnail.size == expected_size
                assert thumbnail.getpixel((0, 0))[0] >= 250
        status = client.get(f"/api/projects/{PID}/captures/cap_border").json()["status"]
        assert status["applied_setup_ids"] == [data["setup_id"]]
