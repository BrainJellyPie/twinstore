"""Uploads preserve damaged metadata and remain compatible with older manifests."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage import images
from store_emulator.application.storage.io import write_json


def seed_photo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(data, format="PNG")
    images.save_image("proj_test", "tea", data.getvalue(), "tea.png")
    return tmp_path / ".data" / "images" / "proj_test", data.getvalue()


@pytest.mark.parametrize("manifest_bytes", [b"{", b"[]", b'{"tea":false}', b'{"tea":{"path":42}}', b"\xff"])
@pytest.mark.parametrize("sku", ["tea", "new"])
def test_upload_preserves_corrupt_manifest_and_existing_photos(tmp_path, monkeypatch, manifest_bytes, sku):
    root, data = seed_photo(tmp_path, monkeypatch)
    (root / "manifest.json").write_bytes(manifest_bytes)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    from store_emulator.server.main import app

    response = TestClient(app).post(
        "/api/projects/proj_test/sku-images", params={"sku": sku},
        files={"file": ("new.png", data, "image/png")},
    )
    assert response.status_code == 500, response.text
    assert "Stored image metadata" in response.json()["detail"]
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


@pytest.mark.parametrize("empty", [False, True])
def test_upload_accepts_empty_and_legacy_manifests(tmp_path, monkeypatch, empty):
    root, data = seed_photo(tmp_path, monkeypatch)
    entry = images.load_manifest("proj_test")["tea"]
    legacy = {"path": entry["path"], "mime": entry["mime"]}
    write_json(root / "manifest.json", {} if empty else {"tea": legacy})
    from store_emulator.server.main import app

    client = TestClient(app)
    response = client.post(
        "/api/projects/proj_test/sku-images", params={"sku": "new"},
        files={"file": ("new.png", data, "image/png")},
    )
    assert response.status_code == 200, response.text
    assert client.get(response.json()["url"]).content == data
    if not empty:
        assert images.load_manifest("proj_test")["tea"] == legacy
        assert client.get("/api/projects/proj_test/images", params={"sku": "tea"}).content == data


def test_tolerant_read_keeps_valid_entries_in_a_partially_damaged_manifest(tmp_path, monkeypatch):
    root, data = seed_photo(tmp_path, monkeypatch)
    manifest = images.load_manifest("proj_test")
    write_json(root / "manifest.json", {**manifest, "broken": False})
    assert images.load_manifest("proj_test") == manifest
    resolved = images.resolve_image("proj_test", "tea")
    assert resolved is not None
    assert resolved[0].read_bytes() == data
