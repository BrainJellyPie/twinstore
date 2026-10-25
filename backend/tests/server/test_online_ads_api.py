"""Ad campaigns through the API: saving them with a store, and what a run reports about them."""

import time

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _wait(client: TestClient, run_id: str) -> dict:  # type: ignore[type-arg]
    for _ in range(300):
        view = client.get(f"/api/projects/{PID}/online/runs/{run_id}").json()
        if view["status"]["status"] in ("completed", "failed"):
            return view
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_ads_are_saved_validated_and_measured_against_the_store_without_them(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "beauty"}).json()
    site = {**site, "options": {**site["options"], "welcome_popup": "none"}}
    url = f"/api/projects/{PID}/online/sites/{site['id']}"
    product = site["products"][0]["id"]
    ad = {"id": "ad_banner", "name": "Spring banner", "product_id": product, "placement": "hero_banner", "cost": 30}
    assert client.put(url, json={**site, "ads": [ad, ad]}).status_code == 422
    assert client.put(url, json={**site, "ads": [{**ad, "product_id": "nope"}]}).status_code == 422
    assert client.put(url, json={**site, "ads": [{**ad, "placement": "billboard"}]}).status_code == 422
    with_ad = client.put(url, json={**site, "ads": [ad]}).json()
    assert with_ad["ads"][0]["placement"] == "hero_banner" and with_ad["ads"][0]["pricing"] == "cpc"

    page = client.post(f"{url}/browse", json={}).json()
    assert any(o["ad_id"] == "ad_banner" and o["label"].startswith("Ad · ") for o in page["options"])

    assert client.post(f"{url}/copy", json={"ads": [{**ad, "product_id": "nope"}]}).status_code == 422
    plain = client.post(f"{url}/copy", json={"name": "No ads", "ads": [{**ad, "active": False}]}).json()
    assert plain["ads"][0]["active"] is False and client.get(url).json()["ads"][0]["active"] is True
    status = client.post(f"/api/projects/{PID}/online/runs",
                         json={"site_ids": [site["id"], plain["id"]], "shoppers": 30, "seed": 5}).json()
    view = _wait(client, status["run_id"])
    assert view["status"]["status"] == "completed", view["status"]["error"]
    result = view["result"]
    rows = result["variants"][0]["ads"]
    assert [r["ad_id"] for r in rows] == ["ad_banner"] and rows[0]["reach"] > 0
    assert result["variants"][1]["ads"] == []  # a paused ad is not reported
    # The control store runs the ad and the variant does not: the lift still reads "with the ad minus without".
    lift = result["comparisons"][0]["ad_lifts"][0]
    assert lift["site_id"] == site["id"] and lift["units_diff"] == lift["units_with"] - lift["units_without"]
    variants = [result["variants"][0]["revenue"], result["variants"][1]["revenue"]]
    assert lift["revenue_diff"] == variants[0] - variants[1]
    csv_text = client.get(f"/api/projects/{PID}/online/runs/{status['run_id']}/clickstream.csv").text
    assert ",ad_id," in csv_text.splitlines()[0]
