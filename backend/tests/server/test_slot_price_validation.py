"""Product upload errors must preserve the previously saved shelf contents."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    client = TestClient(app, raise_server_exceptions=False)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test"})
    setup = client.post("/api/projects/proj_test/setups", json={"mode": "empty"}).json()
    url = f"/api/projects/proj_test/setups/{setup['id']}"
    store = {"id": "store", "name": "Test", "type": "cafe", "grid_size": [8, 6], "racks": [
        {"id": "entry", "type": "entrance", "shape": [[1]], "position": [0, 0]},
        {"id": "exit", "type": "exit", "shape": [[1]], "position": [7, 5]},
        {"id": "shelf", "type": "shelf", "shape": [[1]], "position": [2, 2], "slots": [
            {"block": 0, "face": "N", "level": 1, "items": [{"sku": "original", "name": "Original", "price": 100}]}]},
    ]}
    saved = client.put(url, json={"setup": {"store": store}})
    assert saved.status_code == 200, saved.text
    path = root / "setups" / f"{setup['id']}.json"
    return client, url, store, path


@pytest.mark.parametrize("field", ["price", "regular_price"])
def test_saved_item_rejects_negative_prices(shelf, field):
    client, url, store, path = shelf
    before = read_json(path)
    store["racks"][2]["slots"][0]["items"][0][field] = -1
    response = client.put(url, json={"setup": {"store": store}})
    assert response.status_code == 422, response.text
    assert read_json(path) == before


def row(sku, price=100):
    return {"rack_id": "shelf", "block": 0, "face": "N", "level": 1, "sku": sku, "name": sku, "price": price}


@pytest.mark.parametrize("rows,code", [([row("negative", -1)], 422), ([row(str(i)) for i in range(5)], 400)])
def test_invalid_bulk_products_do_not_replace_existing_items(shelf, rows, code):
    client, url, _, path = shelf
    before = read_json(path)
    response = client.put(f"{url}/slots", json={"slots": rows})
    assert response.status_code == code, response.text
    assert read_json(path) == before


def test_four_free_products_can_be_registered(shelf):
    client, url, _, path = shelf
    response = client.put(f"{url}/slots", json={"slots": [row(str(i), 0) for i in range(4)]})
    assert response.status_code == 200 and response.json()["count"] == 4
    assert [i["price"] for i in read_json(path)["store"]["racks"][2]["slots"][0]["items"]] == [0, 0, 0, 0]


@pytest.mark.parametrize("regular_price", [0, 100, 200, 999999])
def test_bulk_import_keeps_the_reference_price(shelf, regular_price):
    client, url, _, path = shelf
    response = client.put(f"{url}/slots", json={"slots": [{**row("sale", 100), "regular_price": regular_price}]})
    assert response.status_code == 200, response.text
    item = read_json(path)["store"]["racks"][2]["slots"][0]["items"][0]
    assert item["price"] == 100 and item["regular_price"] == regular_price


@pytest.mark.parametrize("regular_price", [-1, 1.5, "unknown", None])
def test_invalid_reference_prices_do_not_replace_saved_products(shelf, regular_price):
    client, url, _, path = shelf
    before = read_json(path)
    response = client.put(f"{url}/slots", json={"slots": [{**row("sale"), "regular_price": regular_price}]})
    assert response.status_code == 422, response.text
    assert read_json(path) == before


@pytest.mark.parametrize("image_url", [True, 123, {}, []])
def test_invalid_image_references_do_not_replace_saved_products(shelf, image_url):
    client, url, _, path = shelf
    before = read_json(path)
    response = client.put(f"{url}/slots", json={"slots": [{**row("photo"), "image_url": image_url}]})
    assert response.status_code == 422, response.text
    assert read_json(path) == before
