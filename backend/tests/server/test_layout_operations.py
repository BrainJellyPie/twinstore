"""A layout remembers how its store is run, and runs, A/B tests and the optimizer on it use that."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _layout(c: TestClient) -> str:
    return c.post(f"/api/projects/{PID}/setups", json={"mode": "racks_and_items", "source_setup_id": SETUP}).json()["id"]


def _finished(c: TestClient, path: str) -> dict[str, object]:
    for _ in range(1200):
        view = c.get(path).json()
        status = view["status"] if isinstance(view.get("status"), str) else view["status"]["status"]
        if status in ("completed", "failed"):
            assert status == "completed", view
            return view
        time.sleep(0.05)
    raise AssertionError(f"{path} did not finish")


def _run(c: TestClient, sid: str, **extra: object) -> str:
    rid = c.post(f"/api/projects/{PID}/runs", json={"setup_id": sid, "engine_type": "rule_based", "max_customers": 40,
                                                    "preview": True, "seed": 2, **extra}).json()["run_id"]
    _finished(c, f"/api/projects/{PID}/runs/{rid}/status")
    return rid


def _ran_with(c: TestClient, rid: str) -> object:
    return json.loads(Path(f".data/{PID}/runs/{rid}/input/config.json").read_text(encoding="utf-8"))["operations"]


def test_a_layout_saves_clears_and_passes_on_how_its_store_is_run(client):
    sid = _layout(client)
    assert client.get(f"/api/projects/{PID}/setups/{sid}/operations").json() == {"operations": None}
    saved = client.put(f"/api/projects/{PID}/setups/{sid}/operations",
                       json={"operations": {"stock_per_facing": 5, "till_schedule": {"18": 2}}}).json()
    assert saved["operations"]["stock_per_facing"] == 5 and saved["operations"]["till_schedule"] == {"18": 2}
    assert client.get(f"/api/projects/{PID}/setups/{sid}/operations").json() == saved
    copy = client.post(f"/api/projects/{PID}/setups", json={"mode": "racks_and_items", "source_setup_id": sid}).json()["id"]
    assert client.get(f"/api/projects/{PID}/setups/{copy}/operations").json() == saved
    assert client.put(f"/api/projects/{PID}/setups/{sid}/operations", json={"operations": None}).json() == {"operations": None}
    assert client.get(f"/api/projects/{PID}/setups/{sid}/operations").json() == {"operations": None}
    assert client.get(f"/api/projects/{PID}/setups/setup_nothere/operations").status_code == 404


def test_a_finalized_layout_can_still_change_how_it_is_run(client):
    sid = _layout(client)
    rid = client.post(f"/api/projects/{PID}/runs", json={"setup_id": sid, "engine_type": "rule_based",
                                                         "max_customers": 20}).json()["run_id"]
    _finished(client, f"/api/projects/{PID}/runs/{rid}/status")
    time.sleep(0.2)
    assert client.get(f"/api/projects/{PID}/setups/{sid}").json()["status"] == "locked"
    response = client.put(f"/api/projects/{PID}/setups/{sid}/operations", json={"operations": {"stock_per_facing": 3}})
    assert response.status_code == 200 and response.json()["operations"]["stock_per_facing"] == 3


@pytest.mark.parametrize("bad", [{"stock_per_facing": 0}, {"till_schedule": {"24": 1}}, {"crowd_limit": 1}])
def test_impossible_layout_operations_are_refused(client, bad):
    response = client.put(f"/api/projects/{PID}/setups/{_layout(client)}/operations", json={"operations": bad})
    assert response.status_code == 422


def test_runs_use_the_layouts_operations_unless_told_otherwise(client):
    sid = _layout(client)
    assert _ran_with(client, _run(client, sid)) is None
    assert _ran_with(client, _run(client, sid, shared_store=True))["stock_per_facing"] == 12   # the defaults
    client.put(f"/api/projects/{PID}/setups/{sid}/operations", json={"operations": {"stock_per_facing": 4}})
    assert _ran_with(client, _run(client, sid))["stock_per_facing"] == 4
    assert _ran_with(client, _run(client, sid, operations={"stock_per_facing": 9}))["stock_per_facing"] == 9
    alone = _run(client, sid, shared_store=False)
    assert _ran_with(client, alone) is None
    assert client.get(f"/api/projects/{PID}/runs/{alone}/operations").status_code == 404


def test_an_ab_test_on_the_layout_shares_its_store(client):
    sid = _layout(client)
    client.put(f"/api/projects/{PID}/setups/{sid}/operations",
               json={"operations": {"stock_per_facing": 1, "restock_every_min": None, "open_counters": 1}})
    body = {"setup_id": sid, "panel": 60, "focus_skus": ["A0017"],
            "variants": [{"name": "Half price", "changes": [{"kind": "discount", "sku": "A0017", "percent": -50}]}]}
    eid = client.post(f"/api/projects/{PID}/experiments", json=body).json()["job_id"]
    report = _finished(client, f"/api/projects/{PID}/experiments/{eid}")["report"]
    assert report["operations"]["stock_per_facing"] == 1
    arms = [report["control"], *report["variants"]]
    assert all({"lost_units", "left_line", "avg_wait_sec"} <= set(arm) for arm in arms)
    assert sum(arm["lost_units"] for arm in arms) > 0
    alone = client.post(f"/api/projects/{PID}/experiments", json={**body, "shared_store": False}).json()["job_id"]
    plain = _finished(client, f"/api/projects/{PID}/experiments/{alone}")["report"]
    assert plain["operations"] is None and plain["control"]["lost_units"] == 0


def test_the_optimizer_judges_layouts_in_the_layouts_store(client):
    sid = _layout(client)
    client.put(f"/api/projects/{PID}/setups/{sid}/operations", json={"operations": {"stock_per_facing": 2}})
    started = client.post(f"/api/projects/{PID}/setups/{sid}/optimize",
                          json={"spec": {"budget": 8, "eval_customers": 30, "validation_customers": 0}})
    assert started.status_code == 200, started.text
    assert started.json()["operations"]["stock_per_facing"] == 2
    off = client.post(f"/api/projects/{PID}/setups/{sid}/optimize",
                      json={"spec": {"budget": 8, "eval_customers": 30, "validation_customers": 0}, "shared_store": False})
    assert off.json()["operations"] is None
