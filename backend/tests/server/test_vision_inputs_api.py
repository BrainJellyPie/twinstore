"""Photo inputs through the API: a storefront photo sets the store's pull in the neighborhood."""

import io

import pytest
from fastapi.testclient import TestClient

from tests.engine.test_vision_inputs import storefront

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _png(bright: bool) -> bytes:
    buf = io.BytesIO()
    storefront(bright).save(buf, format="PNG")
    return buf.getvalue()


def test_storefront_sets_venue_pull(client):
    town = client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "residential", "seed": 1}).json()
    focal = town["focal_venue_id"]
    before = client.get(f"/api/projects/{PID}/town/demand").json()
    res = client.post(f"/api/projects/{PID}/town/venues/{focal}/storefront", files={"photo": ("front.png", _png(False), "image/png")},
                      data={"model": "none"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["appeal"]["method"] == "image_stats" and body["appeal"]["attractiveness"] < 1.0
    venue = next(v for v in body["town"]["venues"] if v["id"] == focal)
    assert venue["attractiveness"] == body["appeal"]["attractiveness"]
    after = client.get(f"/api/projects/{PID}/town/demand").json()
    assert after != before  # the demand model sees the new pull
    assert client.post(f"/api/projects/{PID}/town/venues/nope/storefront", files={"photo": ("f.png", _png(True), "image/png")}).status_code == 404


def test_receipts_need_a_vision_model(client):
    res = client.post(f"/api/projects/{PID}/receipts", files=[("photos", ("r.png", _png(True), "image/png"))], data={"model": "none"})
    assert res.status_code == 400


def test_receipt_review_uses_catalog_and_requires_corrections(client):
    store = client.get(f"/api/projects/{PID}/setups/setup_7d6d").json()["store"]
    item = next(item for rack in store["racks"] for slot in rack["slots"] for item in slot["items"])
    body = {"setup_id": "setup_7d6d", "receipts": [{"receipt_id": "r1", "currency": "KRW", "lines": [
        {"name": "OCR typo", "sku": "not_in_store", "matched": True, "quantity": 2, "line_total": 1000},
    ]}]}
    res = client.post(f"/api/projects/{PID}/receipts/review", json=body)
    assert res.status_code == 200, res.text
    assert not res.json()["ready"] and res.json()["csv"] == ""
    line = body["receipts"][0]["lines"][0]
    line["sku"] = item["sku"]
    body["receipts"][0]["currency"] = res.json()["currency"]
    fixed = client.post(f"/api/projects/{PID}/receipts/review", json=body).json()
    assert fixed["ready"] and fixed["included_lines"] == 1 and fixed["csv"]
    assert fixed["receipts"][0]["lines"][0]["matched"]
    assert client.post("/api/projects/no_such_project/receipts/review", json=body).status_code == 404
    body["run_id"] = "../outside"
    assert client.post(f"/api/projects/{PID}/receipts/review", json=body).status_code == 422


def test_receipt_review_uses_saved_run_currency(client, tmp_path):
    import json
    from store_emulator.server.deps import get_config

    store = client.get(f"/api/projects/{PID}/setups/setup_7d6d").json()["store"]
    item = next(item for rack in store["racks"] for slot in rack["slots"] for item in slot["items"])
    target = tmp_path / ".data" / PID / "runs" / "receipt_review" / "input"
    target.mkdir(parents=True)
    (target / "store.json").write_text(json.dumps(store))
    config = get_config().model_copy(update={"currency": "JPY"})
    (target / "config.json").write_text(config.model_dump_json())
    body = {"run_id": "receipt_review", "receipts": [{"receipt_id": "r1", "currency": "JPY", "lines": [
        {"name": item["name"], "sku": item["sku"], "quantity": 1, "unit_price": 150},
    ]}]}
    response = client.post(f"/api/projects/{PID}/receipts/review", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["ready"] and response.json()["currency"] == "JPY"
