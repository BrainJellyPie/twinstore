"""An online variant's prices back to the store: the run's copy of the variant is compared with its control, the
prices that differ reach the layout's products with the same SKU, and design, pictures and ads stay online."""

import time

import pytest
from fastapi.testclient import TestClient

from store_emulator.engine.prompting import display_price

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_a_variants_prices_are_reviewed_on_a_layout_and_kept(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store", "setup_id": SETUP}).json()
    cheaper, unchanged = site["products"][0], site["products"][1]
    products = [{**p, "price": p["price"] - 10} if p["id"] == cheaper["id"] else p for p in site["products"]]
    options = {**site["options"], "page_style": "luxury"}
    variant = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/copy",
                          json={"name": "Lower price", "options": options, "products": products}).json()
    run = client.post(f"/api/projects/{PID}/online/runs", json={"site_ids": [site["id"], variant["id"]], "shoppers": 3}).json()
    for _ in range(300):
        if client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}").json()["status"]["status"] == "completed":
            break
        time.sleep(0.1)
    # Later edits of the store do not change what the run tested.
    edited = client.get(f"/api/projects/{PID}/online/sites/{variant['id']}").json()
    edited["products"] = [{**p, "price": p["price"] + 99} if p["id"] == unchanged["id"] else p for p in edited["products"]]
    assert client.put(f"/api/projects/{PID}/online/sites/{variant['id']}", json=edited).status_code == 200

    url = f"/api/projects/{PID}/online/runs/{run['run_id']}/variants"
    assert client.get(f"{url}/0/store-changes").status_code == 404  # the control has nothing to bring
    r = client.get(f"{url}/1/store-changes")
    assert r.status_code == 200, r.text
    found = r.json()
    assert found["name"] == "Lower price" and found["currency"] == site["currency"].upper()
    assert found["changes"] == [{**found["changes"][0], "kind": "price", "sku": cheaper["sku"], "price": cheaper["price"] - 10}]
    assert unchanged["sku"] not in str(found["changes"])
    assert any("page design" in s for s in found["skipped"])

    check = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit/check",
                        json={"name": found["name"], "changes": found["changes"], "currency": found["currency"]})
    assert check.status_code == 200, check.text
    was, now = display_price(cheaper["price"], found["currency"]), display_price(cheaper["price"] - 10, found["currency"])
    assert any(f"{cheaper['name']}: price {was} → {now}" in a for a in check.json()["applied"])  # as on a tag, not cents
    other = "KRW" if found["currency"] != "KRW" else "USD"
    wrong = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit/check",
                        json={"name": found["name"], "changes": found["changes"], "currency": other})
    assert wrong.status_code == 400 and "same currency" in wrong.json()["detail"]


def test_two_different_stores_share_no_products(client: TestClient) -> None:
    sites = [client.post(f"/api/projects/{PID}/online/sites", json={"template_id": t}).json() for t in ("fashion", "electronics")]
    run = client.post(f"/api/projects/{PID}/online/runs", json={"site_ids": [s["id"] for s in sites], "shoppers": 2}).json()
    for _ in range(300):
        if client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}").json()["status"]["status"] == "completed":
            break
        time.sleep(0.1)
    found = client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}/variants/1/store-changes").json()
    # Template products reuse ids across stores; none of them is the other store's product.
    assert found["changes"] == [] and not any("SKU" in s or "picture" in s for s in found["skipped"])
