"""A run whose shoppers share the store saves and serves what sharing it did."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _run(c: TestClient, sid: str, **extra: object) -> str:
    rid = c.post(f"/api/projects/{PID}/runs", json={
        "setup_id": sid, "engine_type": "rule_based", "max_customers": 60, "preview": True, "seed": 4, **extra,
    }).json()["run_id"]
    for _ in range(600):
        st = c.get(f"/api/projects/{PID}/runs/{rid}/status").json()
        if st["status"] in ("completed", "failed"):
            assert st["status"] == "completed", st
            return rid
        time.sleep(0.05)
    raise AssertionError("the run did not finish")


def test_a_shared_store_run_reports_its_stock_and_tills(client):
    sid = client.post(f"/api/projects/{PID}/setups",
                      json={"mode": "racks_and_items", "source_setup_id": "setup_7d6d"}).json()["id"]
    alone = _run(client, sid)
    assert client.get(f"/api/projects/{PID}/runs/{alone}/operations").status_code == 404

    shared = _run(client, sid, operations={"stock_per_facing": 1, "restock_every_min": None, "open_counters": 1})
    response = client.get(f"/api/projects/{PID}/runs/{shared}/operations")
    assert response.status_code == 200
    report = response.json()
    assert report["config"]["stock_per_facing"] == 1 and report["counters"] == 1
    assert report["queued"] > 0 and report["hours"]
    customers = client.get(f"/api/projects/{PID}/runs/{shared}/timeline").json()
    summary = client.get(f"/api/projects/{PID}/runs/{shared}/summary").json()["summary"]
    assert summary["total_revenue"] == sum(c["total_spent"] for c in customers)
    waits = [c["queue_wait_sec"] for c in customers if c["total_spent"] > 0 or c["left_queue"]]
    assert len(waits) == report["queued"]
    assert sum(waits) / len(waits) == pytest.approx(report["avg_wait_sec"], abs=0.6)
    config = json.loads(Path(f".data/{PID}/runs/{shared}/input/config.json").read_text(encoding="utf-8"))
    assert config["operations"]["open_counters"] == 1


def test_a_damaged_report_is_named_instead_of_a_server_error(client):
    sid = client.post(f"/api/projects/{PID}/setups",
                      json={"mode": "racks_and_items", "source_setup_id": "setup_7d6d"}).json()["id"]
    rid = _run(client, sid, operations={})
    Path(f".data/{PID}/runs/{rid}/output/operations.json").write_text('{"queued": ', encoding="utf-8")
    response = client.get(f"/api/projects/{PID}/runs/{rid}/operations")
    assert response.status_code == 422 and "damaged" in response.json()["detail"]


@pytest.mark.parametrize("bad", [{"stock_per_facing": 0}, {"open_counters": 0}, {"substitute_share": 1.5},
                                 {"restock_every_min": 1}, {"patience_sec": -5},
                                 {"stock_overrides": {"chips": -1}},
                                 {"stock_overrides": {"chips": 10_001}},
                                 {"stock_overrides": {"chips": 1.5}},
                                 {"stock_overrides": {"chips": None}}])
def test_impossible_store_settings_are_refused(client, bad):
    response = client.post(f"/api/projects/{PID}/runs",
                           json={"setup_id": "setup_7d6d", "engine_type": "rule_based", "preview": True,
                                 "operations": bad})
    assert response.status_code == 422


def test_the_customer_export_carries_each_shoppers_wait_and_missing_products(client):
    sid = client.post(f"/api/projects/{PID}/setups",
                      json={"mode": "racks_and_items", "source_setup_id": "setup_7d6d"}).json()["id"]
    rid = _run(client, sid, operations={"stock_per_facing": 1, "open_counters": 1})
    lines = client.get(f"/api/projects/{PID}/runs/{rid}/export.csv").text.lstrip("﻿").splitlines()
    header = lines[0].split(",")
    assert header[-4:] == ["queue_wait_sec", "left_queue", "lost_units", "substituted_units"]
    customers = {c["persona_id"]: c for c in client.get(f"/api/projects/{PID}/runs/{rid}/timeline").json()}
    for line in lines[1:]:
        cells = line.split(",")
        if cells[0] in customers:
            assert int(cells[-4]) == customers[cells[0]]["queue_wait_sec"]
            assert int(cells[-2]) == customers[cells[0]]["lost_units"]
