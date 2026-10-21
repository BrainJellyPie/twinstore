"""Playback can display SKU photos added after a run without changing its inputs."""

import io
import json
from urllib.parse import quote

from fastapi.testclient import TestClient
from PIL import Image

PID = "proj_67916afd"
RUN = "run_ab0039"


def test_playback_uses_current_photos_without_rewriting_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app

    with TestClient(app) as client:
        snapshot = tmp_path / ".data" / PID / "runs" / RUN / "input" / "store.json"
        before = snapshot.read_bytes()
        data = json.loads(before)
        product = next(item for rack in data["racks"] for slot in rack["slots"] for item in slot["items"])
        sku = product["sku"]
        photo = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(photo, format="PNG")
        uploaded = client.post(f"/api/projects/{PID}/sku-images/{quote(sku, safe='')}",
                               files={"file": ("pack.png", photo.getvalue(), "image/png")})
        assert uploaded.status_code == 200, uploaded.text
        response = client.get(f"/api/projects/{PID}/runs/{RUN}/store")
        assert response.status_code == 200
        displayed = response.json()
        facings = [item for rack in displayed["racks"] for slot in rack["slots"]
                   for item in slot["items"] if item["sku"] == sku]
        assert facings and all(item["image_url"] == uploaded.json()["url"] for item in facings)
        assert snapshot.read_bytes() == before
        assert displayed["grid_size"] == data["grid_size"]

        # An explicitly recorded package reference takes precedence over later photos.
        product["image_url"] = "https://example.test/recorded-package.png"
        snapshot.write_text(json.dumps(data))
        explicit = snapshot.read_bytes()
        response = client.get(f"/api/projects/{PID}/runs/{RUN}/store")
        recorded = next(item for rack in response.json()["racks"] for slot in rack["slots"]
                        for item in slot["items"] if item["sku"] == sku)
        assert recorded["image_url"] == product["image_url"]
        assert snapshot.read_bytes() == explicit
