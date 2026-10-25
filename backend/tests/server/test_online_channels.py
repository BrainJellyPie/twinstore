"""The same customers in both twins: an online run of the project's customers read next to a store run of them."""

import time

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"
STORE_RUN = "run_efd57c"  # the sample project's finished store run


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _run(client: TestClient, source: str) -> dict:  # type: ignore[type-arg]
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store"}).json()
    run = client.post(f"/api/projects/{PID}/online/runs", json={"site_ids": [site["id"]], "shoppers": 40, "source": source}).json()
    for _ in range(600):
        view = client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}").json()
        if view["status"]["status"] == "completed":
            return view
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_customers_split_into_store_online_both_and_neither(client: TestClient) -> None:
    view = _run(client, "project")
    run_id = view["result"]["run_id"]
    r = client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels")
    assert r.status_code == 200, r.text
    mix = r.json()
    assert mix["store_run_id"] == STORE_RUN and mix["online_store"] == view["result"]["variants"][0]["site_name"]
    assert 0 < mix["customers"] <= 40
    assert mix["both"] + mix["store_only"] + mix["online_only"] + mix["neither"] == mix["customers"]
    online_buyers = sum(1 for s in view["result"]["shoppers"]
                        if s["persona_id"] and view["result"]["visits"][s["id"]][0]["outcome"] == "purchased")
    assert mix["both"] + mix["online_only"] <= online_buyers
    assert sum(g["customers"] for g in mix["by_age"]) == mix["customers"] == sum(g["customers"] for g in mix["by_gender"])
    assert mix["store_spend"] >= 0 and mix["online_spend"] >= 0 and mix["store_currency"] and mix["online_currency"]
    assert client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels", params={"store_run": STORE_RUN}).json() == mix
    assert client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels", params={"store_run": "run_none"}).status_code == 404


def test_panel_shoppers_are_nobody_in_the_store(client: TestClient) -> None:
    run_id = _run(client, "panel")["result"]["run_id"]
    r = client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels")
    assert r.status_code == 400 and "built-in panel" in r.json()["detail"]


def test_no_store_run_of_these_customers_is_no_mix(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application import channels

    run_id = _run(client, "project")["result"]["run_id"]
    monkeypatch.setattr(channels, "_store_runs", lambda pid: [])
    r = client.get(f"/api/projects/{PID}/online/runs/{run_id}/channels")
    assert r.status_code == 200 and r.json() is None
