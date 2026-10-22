"""Photos stay with the same generated product when another layout is created."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test", "currency": "USD"})
    from store_emulator.server.main import app
    return TestClient(app)


def generated_items(client, options):
    created = client.post("/api/projects/proj_test/setups/generate", json=options)
    assert created.status_code == 200, created.text
    saved = client.get("/api/projects/proj_test/setups/" + created.json()["id"])
    assert saved.status_code == 200, saved.text
    return [item for rack in saved.json()["store"]["racks"] for slot in rack["slots"] for item in slot["items"]]


def upload_photo(client, sku):
    photo = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(photo, format="PNG")
    response = client.post("/api/projects/proj_test/sku-images", params={"sku": sku},
                           files={"file": ("product.png", photo.getvalue(), "image/png")})
    assert response.status_code == 200, response.text
    return response.json()["url"]


def test_photo_does_not_attach_to_a_different_generated_product(client):
    original = generated_items(client, {"template_id": "urban_cvs"})[0]
    url = upload_photo(client, original["sku"])
    books = generated_items(client, {"template_id": "bookstore"})
    assert all(item["sku"] == original["sku"] for item in books if item.get("image_url") == url)


@pytest.mark.parametrize("options,product_name", [
    ({"template_id": "urban_cvs", "excluded_categories": ["checkout_impulse"]}, "Cola 500ml"),
    ({"template_id": "hypermarket"}, "Cola 500ml"),
    ({"template_id": "urban_cvs", "currency": "JPY"}, "Cola 500ml"),
    ({"template_id": "urban_cvs", "currency": "KRW"}, "콜라 500ml"),
])
def test_photo_follows_its_product_across_layout_options(client, options, product_name):
    first = generated_items(client, {"template_id": "urban_cvs"})
    original = next(item for item in first if item["name"] == "Cola 500ml")
    url = upload_photo(client, original["sku"])
    revised = generated_items(client, options)
    target = next(item for item in revised if item["name"] == product_name)
    assert target["image_url"] == url
    assert all(item["sku"] == original["sku"] for item in revised if item.get("image_url") == url)
    assert any((item.get("image_url") or "").startswith("/api/catalog-images/") for item in revised)
