import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import capture
from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test", "currency": "USD"})
    monkeypatch.setattr(capture.executor, "submit", Mock())
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("kind", ["capture", "package", "storefront"])
@pytest.mark.parametrize("limit,expected", [(100, 413), (25600, 200)])
def test_image_pixel_limit_is_a_client_error_before_writes_or_model_calls(client, tmp_path, monkeypatch, kind, limit, expected):
    town = client.post("/api/projects/proj_test/town/generate", json={"seed": 1, "size_m": 200}).json()
    town_path = tmp_path / ".data" / "proj_test" / "town.json"
    previous = town_path.read_bytes()
    buf = io.BytesIO()
    Image.new("RGB", (160, 160), "white").save(buf, format="PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", limit)
    if kind == "capture":
        response = client.post("/api/projects/proj_test/captures", files={"image": ("photo.png", buf.getvalue(), "image/png")},
                               data={"detector": "classic", "model": "none"})
    elif kind == "package":
        response = client.post("/api/projects/proj_test/lab/packages", files={"image": ("photo.png", buf.getvalue(), "image/png")},
                               data={"remove_background": "false"})
    else:
        vid = town["venues"][0]["id"]
        response = client.post(f"/api/projects/proj_test/town/venues/{vid}/storefront",
                               files={"photo": ("photo.png", buf.getvalue(), "image/png")}, data={"model": "none"})
    assert response.status_code == expected, response.text
    if expected == 413:
        assert "image" in response.json()["detail"].lower() or "photo" in response.json()["detail"].lower()
        capture.executor.submit.assert_not_called()
        assert town_path.read_bytes() == previous
        root = tmp_path / ".data" / "proj_test"
        assert not (root / "captures").exists()
        assert not (root / "lab_assets").exists()


@pytest.mark.parametrize("kind", ["capture", "package", "vision"])
@pytest.mark.parametrize("orientation,expected", [(1, [160, 240]), (6, [240, 160])])
def test_phone_photo_orientation_is_applied_before_analysis_or_package_storage(client, kind, orientation, expected):
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[274] = orientation
    Image.new("RGB", (160, 240), "white").save(buf, format="JPEG", exif=exif)
    if kind == "capture":
        response = client.post("/api/projects/proj_test/captures", files={"image": ("photo.jpg", buf.getvalue(), "image/jpeg")},
                               data={"detector": "classic", "model": "none"})
        assert response.status_code == 200, response.text
        actual = response.json()["image_size"]
    elif kind == "package":
        response = client.post("/api/projects/proj_test/lab/packages", files={"image": ("photo.jpg", buf.getvalue(), "image/jpeg")},
                               data={"remove_background": "false"})
        assert response.status_code == 200, response.text
        actual = [response.json()["width"], response.json()["height"]]
    else:
        from store_emulator.application.vision_inputs import _photo
        actual = list(_photo(buf.getvalue()).size)
    assert actual == expected
