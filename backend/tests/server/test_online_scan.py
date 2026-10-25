"""Screening changes to an online store on rule shoppers: each change is read against the store on the same shoppers,
nothing is saved, and a price change must keep the store's products."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_changes_are_screened_on_the_same_shoppers(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    before = client.get(f"/api/projects/{PID}/online/sites").json()
    slow = {**site["options"], "page_load_ms": 9000}
    cheaper = [{**p, "price": max(1, round(p["price"] * 0.7))} for p in site["products"]]
    r = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/scan", json={"shoppers": 60, "candidates": [
        {"id": "same", "options": site["options"]},
        {"id": "slow", "options": slow},
        {"id": "cheaper", "options": site["options"], "products": cheaper},
    ]})
    assert r.status_code == 200, r.text
    scan = r.json()
    assert scan["shoppers"] == 60 and [row["id"] for row in scan["rows"]] == ["same", "slow", "cheaper"]
    same = {d["metric"]: d for d in scan["rows"][0]["deltas"]}
    assert same["conversion"]["diff"] == 0 and scan["rows"][0]["won"] == scan["rows"][0]["lost"] == 0
    assert {"conversion", "revenue_per_session"} <= set(same)
    slow_conversion = next(d for d in scan["rows"][1]["deltas"] if d["metric"] == "conversion")
    assert slow_conversion["diff"] <= 0  # slower pages never help rule shoppers
    assert client.get(f"/api/projects/{PID}/online/sites").json() == before  # nothing saved

    wrong = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/scan", json={"candidates": [
        {"id": "fewer", "options": site["options"], "products": site["products"][:3]}]})
    assert wrong.status_code == 400 and "keep the store's products" in wrong.json()["detail"]
