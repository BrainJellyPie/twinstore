"""A marketing A/B variant carried over to an online store: its price, discount, category and shelf-height changes
reach the products with the same SKU in a variant of the store, and what has no web counterpart is reported, not
guessed."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_a_tests_changes_become_an_online_variant_by_sku(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store"}).json()
    first, second, tail = site["products"][0], site["products"][1], site["products"][-1]
    category = next(c for c in site["categories"] if c["id"] == second["category_id"])
    url = f"/api/projects/{PID}/online/sites/{site['id']}/from-test"
    changes = [
        {"kind": "price", "sku": first["sku"], "price": first["price"] + 50},
        {"kind": "category_price", "category": category["name"], "percent": -10},
        {"kind": "promo", "sku": first["sku"], "promo": "1+1"},
        {"kind": "move", "sku": tail["sku"], "rack_id": "r1", "level": 3},
        {"kind": "discount", "sku": "NOT-HERE", "percent": -20},
    ]
    r = client.post(url, json={"name": "Shelf test online", "note": "From the A/B test", "currency": site["currency"],
                               "changes": changes})
    assert r.status_code == 200, r.text
    result = r.json()
    variant = result["site"]
    assert variant["variant_of"] == site["id"] and variant["name"] == "Shelf test online" and variant["note"] == "From the A/B test"
    by_id = {p["id"]: p for p in variant["products"]}
    assert by_id[first["id"]]["price"] in (first["price"] + 50, round((first["price"] + 50) * 0.9))
    in_category = [p for p in site["products"] if p["category_id"] == category["id"] and p["id"] != first["id"]]
    for product in in_category:
        assert by_id[product["id"]]["price"] < product["price"] or product["price"] == 0
    assert len(result["applied"]) == 3
    assert any("sign has no web counterpart" in s for s in result["skipped"])
    # An eye-level shelf becomes the first place in the list, which the featured order shows first.
    assert variant["products"][0]["id"] == tail["id"] and any("first in its category" in a for a in result["applied"])
    assert any("NOT-HERE" in s for s in result["skipped"])
    # The original store is unchanged.
    assert client.get(f"/api/projects/{PID}/online/sites/{site['id']}").json()["products"] == site["products"]


def test_a_discount_shows_the_was_price_and_nothing_fitting_is_refused(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store"}).json()
    product = next(p for p in site["products"] if p["price"] > 100 and not p["list_price"])
    url = f"/api/projects/{PID}/online/sites/{site['id']}/from-test"
    r = client.post(url, json={"currency": site["currency"], "changes": [{"kind": "discount", "sku": product["sku"], "percent": -20}]})
    discounted = next(p for p in r.json()["site"]["products"] if p["id"] == product["id"])
    assert discounted["price"] == round(product["price"] * 0.8) and discounted["list_price"] == product["price"]
    r = client.post(url, json={"currency": site["currency"], "changes": [{"kind": "promo", "sku": product["sku"], "promo": "SALE"}]})
    assert r.status_code == 400 and "None of these changes fits" in r.json()["detail"]
    other = "KRW" if site["currency"] != "KRW" else "USD"
    r = client.post(url, json={"currency": other, "changes": [{"kind": "discount", "sku": product["sku"], "percent": -20}]})
    assert r.status_code == 400 and "same currency" in r.json()["detail"]


def test_a_lower_shelf_ends_the_list_and_a_move_along_the_shelf_is_skipped(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store"}).json()
    a, b = site["products"][0], site["products"][1]
    url = f"/api/projects/{PID}/online/sites/{site['id']}/from-test"
    r = client.post(url, json={"currency": site["currency"], "changes": [
        {"kind": "move", "sku": a["sku"], "rack_id": "r1", "level": 1},
        {"kind": "move", "sku": b["sku"], "rack_id": "r1", "face": "N"},
    ]})
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["site"]["products"][-1]["id"] == a["id"] and len(result["site"]["products"]) == len(site["products"])
    assert any("last in its category" in x for x in result["applied"])
    assert any("same shelf" in x for x in result["skipped"])


def test_the_store_list_says_which_stores_sell_a_tests_products(client: TestClient) -> None:
    mart = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store"}).json()
    fashion = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    skus = [mart["products"][0]["sku"], mart["products"][1]["sku"], "NOT-HERE"]
    listed = client.get(f"/api/projects/{PID}/online/sites", params={"sku": skus}).json()
    carries = {s["id"]: s["carries"] for s in listed}
    assert carries[mart["id"]] == 2 and carries[fashion["id"]] == 0
    assert all(s["carries"] is None for s in client.get(f"/api/projects/{PID}/online/sites").json())


def test_zero_matching_skus_does_not_rule_out_a_category_price_change(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store"}).json()
    product = next(p for p in site["products"] if p["price"] > 100)
    category = next(c for c in site["categories"] if c["id"] == product["category_id"])
    listed = client.get(f"/api/projects/{PID}/online/sites", params={"sku": ["MISSING"]}).json()
    assert next(s for s in listed if s["id"] == site["id"])["carries"] == 0
    result = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/from-test", json={
        "currency": site["currency"], "changes": [
            {"kind": "price", "sku": "MISSING", "price": 249},
            {"kind": "category_price", "category": category["name"], "percent": -10},
        ],
    })
    assert result.status_code == 200, result.text
    body = result.json()
    changed = next(p for p in body["site"]["products"] if p["id"] == product["id"])
    assert changed["price"] == round(product["price"] * 0.9)
    assert body["applied"] and any("MISSING" in message for message in body["skipped"])
    assert client.get(f"/api/projects/{PID}/online/sites/{site['id']}").json()["products"] == site["products"]
