"""A variant shows shoppers its original store's name; the run still labels each store by its own name."""

import re

from fastapi.testclient import TestClient

from tests.server.test_online_rival_api import PID, _site, _wait, client  # noqa: F401  (fixture)


def test_every_store_of_a_test_shows_the_original_name(client: TestClient) -> None:
    control = _site(client, "pet_store")
    sites = f"/api/projects/{PID}/online/sites"
    variant = client.post(f"{sites}/{control['id']}/copy", json={"name": "Pets – no ads", "note": ""}).json()
    deeper = client.post(f"{sites}/{variant['id']}/copy", json={"name": "Pets – no ads, coupon", "note": ""}).json()
    slug = re.sub(r"[^a-z0-9]+", "", control["name"].lower())

    page = client.post(f"{sites}/{deeper['id']}/browse", json={}).json()
    assert page["title"] == control["name"] and f"www.{slug}.shop" in page["url"]

    runs = f"/api/projects/{PID}/online/runs"
    status = client.post(runs, json={"site_ids": [control["id"], variant["id"]], "shoppers": 3, "seed": 2}).json()
    view = _wait(client, status["run_id"])
    assert view["status"]["status"] == "completed"
    assert [v["site_name"] for v in view["result"]["variants"]] == [control["name"], "Pets – no ads"]
    assert [c["site_name"] for c in view["result"]["comparisons"]] == ["Pets – no ads"]
    visit = client.get(f"{runs}/{status['run_id']}/sessions/1/os0001").json()
    assert visit["site_name"] == "Pets – no ads"
    assert all(f"www.{slug}.shop" in step["url"] for step in visit["session"]["steps"])
