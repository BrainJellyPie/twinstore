"""A variant shows shoppers its original store's name; the run still labels each store by its own name."""

import csv
import io
import re

from fastapi.testclient import TestClient

from store_emulator.application import online
from store_emulator.application.storage.io import read_json, write_json
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
    rows = list(csv.DictReader(io.StringIO(client.get(f"{runs}/{status['run_id']}/clickstream.csv").text.lstrip("\ufeff"))))
    assert {row["site"] for row in rows if row["variant"] == "1"} == {"Pets – no ads"}


def test_a_rival_variant_hides_its_experiment_label_from_shoppers_but_keeps_report_labels(client: TestClient) -> None:
    control = _site(client, "pet_store")
    parent = _site(client, "pet_store")
    sites = f"/api/projects/{PID}/online/sites"
    parent = client.put(f"{sites}/{parent['id']}", json={**parent, "name": "Rival Pets"}).json()
    variant = client.post(f"{sites}/{parent['id']}/copy", json={"name": "SECRET no-ads rival", "note": ""}).json()
    runs = f"/api/projects/{PID}/online/runs"
    response = client.post(runs, json={"site_ids": [control["id"]], "rival_site_id": variant["id"],
        "shoppers": 6, "seed": 2, "max_steps": 5, "missions": {"purchase": 1}, "arrivals": {"search_engine": 1}})
    assert response.status_code == 200, response.text
    status = response.json()
    view = _wait(client, status["run_id"])
    assert view["status"]["status"] == "completed", view["status"].get("error")
    assert view["result"]["rival_name"] == variant["name"]
    visits = [client.get(f"{runs}/{status['run_id']}/sessions/1/{shopper['id']}") for shopper in view["result"]["shoppers"]]
    visits = [response.json() for response in visits if response.status_code == 200]
    assert visits
    assert all(visit["site_name"] == variant["name"] for visit in visits)
    assert all("www.rivalpets.shop" in step["url"] for visit in visits for step in visit["session"]["steps"])
    rows = list(csv.DictReader(io.StringIO(client.get(f"{runs}/{status['run_id']}/clickstream.csv").text.lstrip("\ufeff"))))
    assert {row["site"] for row in rows if row["variant"] == "1"} == {variant["name"]}
    # Historical display/labels come from the run, even after live family names change.
    client.put(f"{sites}/{parent['id']}", json={**parent, "name": "Later renamed shop"})
    client.put(f"{sites}/{variant['id']}", json={**variant, "name": "Later renamed version"})
    again = client.get(f"{runs}/{status['run_id']}/sessions/1/{visits[0]['shopper']['id']}").json()
    assert again == visits[0]
    # Older runs kept the rival label in its snapshot and have no separate status label.
    folder = online._run_dir(PID, status["run_id"])
    saved_status = read_json(folder / "status.json")
    saved_status.pop("rival_name")
    write_json(folder / "status.json", saved_status)
    saved_rival = read_json(folder / "rival.json")
    saved_rival["name"] = variant["name"]
    write_json(folder / "rival.json", saved_rival)
    legacy = client.get(f"{runs}/{status['run_id']}/sessions/1/{visits[0]['shopper']['id']}").json()
    assert legacy["site_name"] == variant["name"]
