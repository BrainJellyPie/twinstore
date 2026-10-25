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


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("products,printed,expected", [
    ({"a": "Tea 500ml"}, "", ""),
    ({"a": "Tea 500ml"}, " \t\u3000", ""),
    ({"a": "Tea 500ml", "b": "TEA 500ML"}, "Tea 500ml", ""),
    ({"a": "Tea 500ml", "b": "Tea-500ml"}, "TEA 500ML", ""),
    ({"a": "Tea 500ml", "b": "Ｔｅａ ５００ｍｌ"}, "Tea 500ml", ""),
    ({"a": "Tea 500ml", "b": "Tea 500ml", "c": "Tea 500ml XL"}, "Tea 500ml", ""),
    ({"a": "Tea 500ml", "b": "Tea 500ml", "c": "Tea 500ml XL"}, "Tea 500m", ""),
    ({"a": "Tea 500ml", "b": "Tea 550ml"}, "Tea 50ml", ""),
    ({"a": "Tea 500ml", "b": "Orange juice"}, "Tea 500m", ""),
    ({"a": "Coca-Cola Original 500ml"}, "Coca-Cola Original 1500ml", ""),
    ({"a": "Organic Vanilla Yogurt 500g"}, "Organic Banana Yogurt 500g", ""),
    ({"a": "오리지널 요거트 500ml"}, "오리지널 요거트 1500ml", ""),
    ({"a": "Organic Tea Pack 6"}, "Organic Tea Pack 16", ""),
    ({"a": "TwinStore Organic Tea 500ml"}, "WinStore Organic Tea 500ml", ""),
    ({"a": "Organic Milk 1% 500ml"}, "Organic Milk 2% 500ml", ""),
    ({"a": "Tea 500ml", "b": "Tea 550ml"}, "TEA-500ML", "a"),
    ({"a": "Tea 500ml", "b": "Tea 500ml", "c": "Tea 500ml XL"}, "Tea 500ml XL", "c"),
])
def test_receipt_matching_keeps_ambiguous_products_for_manual_review(client, monkeypatch, reverse, products, printed, expected):
    from store_emulator.application import vision_inputs
    from tests.engine.test_vision_inputs import _Fake

    client.get(f"/api/projects/{PID}/setups/setup_7d6d")
    if reverse:
        products = dict(reversed(list(products.items())))
    monkeypatch.setattr(vision_inputs, "_receipt_target", lambda *args: (products, "USD"))
    fake = _Fake({"currency": "USD", "lines": [{"name": printed, "quantity": 1, "unit_price": 1}]})
    monkeypatch.setattr(vision_inputs, "_client", lambda *args: fake)

    response = client.post(f"/api/projects/{PID}/receipts", files=[("photos", ("r.png", _png(True), "image/png"))])
    assert response.status_code == 200, response.text
    body = response.json()
    line = body["receipts"][0]["lines"][0]
    assert line["sku"] == expected
    assert line["matched"] is bool(expected)
    assert body["matched_lines"] == int(bool(expected))
    assert body["unmatched_lines"] == int(not expected)
    assert body["products"] == products
    if not expected:
        assert len(body["csv"].splitlines()) == 1
        reviewed = client.post(f"/api/projects/{PID}/receipts/review", json={"receipts": body["receipts"]})
        assert reviewed.status_code == 200, reviewed.text
        assert not reviewed.json()["ready"] and not reviewed.json()["csv"]
        assert any(issue["code"] == "sku" for issue in reviewed.json()["issues"])


def test_a_failed_vision_model_leaves_the_venue_unchanged(client, monkeypatch):
    from store_emulator.application import vision_inputs

    class _Broken:
        model = "anthropic/claude-haiku-5-5"

        async def generate_structured_with_image_async(self, *a, **k):
            raise RuntimeError("RateLimitError: too many requests")

    town = client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "residential", "seed": 1}).json()
    focal = town["focal_venue_id"]
    before = next(v for v in town["venues"] if v["id"] == focal)["attractiveness"]
    monkeypatch.setattr(vision_inputs, "_client", lambda *a, **k: _Broken())
    res = client.post(f"/api/projects/{PID}/town/venues/{focal}/storefront", files={"photo": ("front.png", _png(True), "image/png")})
    assert res.status_code == 502 and "limiting requests" in res.json()["detail"]
    after = client.get(f"/api/projects/{PID}/town").json()
    assert next(v for v in after["venues"] if v["id"] == focal)["attractiveness"] == before


@pytest.mark.parametrize("score,pull", [(0, .6), (10, 1.4)])
def test_complete_model_rating_with_null_reason_updates_only_the_target_venue(client, monkeypatch, score, pull):
    from store_emulator.application import vision_inputs
    from tests.engine.test_vision_inputs import _Fake

    town = client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "residential", "seed": 1}).json()
    focal = town["focal_venue_id"]
    before = {v["id"]: v["attractiveness"] for v in town["venues"]}
    model = _Fake(dict(signage=score, entrance=score, window=score, upkeep=score, overall=score, reasons=None))
    model.model = "openai/offline-storefront"
    monkeypatch.setattr(vision_inputs, "_client", lambda *a, **k: model)
    response = client.post(f"/api/projects/{PID}/town/venues/{focal}/storefront",
        files={"photo": ("front.png", _png(True), "image/png")})
    assert response.status_code == 200, response.text
    assert response.json()["appeal"]["method"] == "vlm"
    saved = client.get(f"/api/projects/{PID}/town").json()
    assert {v["id"]: v["attractiveness"] for v in saved["venues"]} == {**before, focal: pull}
