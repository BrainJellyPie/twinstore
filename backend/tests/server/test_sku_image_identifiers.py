"""Photo identifiers must retain every character accepted in a SKU."""
import io
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False)


def photo():
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(data, format="PNG")
    return data.getvalue()


@pytest.mark.parametrize("sku", ["tea", "A/B", "../tea", ".", "..", "%2F", "%25", "coffee 100%", "tea?size=1#box", "차/대형", ""])
def test_query_sku_photo_round_trip(client, sku):
    data = photo()
    response = client.post("/api/projects/proj_test/sku-images", params={"sku": sku}, files={"file": ("tea.png", data, "image/png")})
    assert response.status_code == 200, response.text
    assert response.json()["sku"] == sku
    downloaded = client.get(response.json()["url"])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == data


@pytest.mark.parametrize("sku", ["tea", "A/B", "차/대형"])
def test_legacy_photo_paths_still_work(client, sku):
    data = photo()
    encoded = quote(sku, safe="")
    uploaded = client.post(f"/api/projects/proj_test/sku-images/{encoded}", files={"file": ("tea.png", data, "image/png")})
    assert uploaded.status_code == 200, uploaded.text
    downloaded = client.get(f"/api/projects/proj_test/images/{encoded}")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == data
