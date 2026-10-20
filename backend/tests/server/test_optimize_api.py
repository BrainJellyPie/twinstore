"""Optimization jobs through the API: start, poll, apply as a new layout."""

import time

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_optimize_job_end_to_end(client):
    spec = {"objective": "revenue_per_visitor", "scope": "planogram", "algorithm": "hill_climb",
            "budget": 6, "eval_customers": 80, "validation_customers": 120, "seed": 1}
    started = client.post(f"/api/projects/{PID}/setups/setup_7d6d/optimize",
                          json={"spec": spec, "scenario_id": "heatwave_weekend"})
    assert started.status_code == 200, started.text
    job = started.json()["job_id"]
    for _ in range(900):
        view = client.get(f"/api/projects/{PID}/optimizations/{job}").json()
        if view["status"]["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert view["status"]["status"] == "completed", view["status"]["error"]
    result = view["result"]
    assert result["evaluations"] <= 6 and result["best_score"] >= result["baseline_score"]
    assert view["status"]["scenario"] == "Heatwave weekend"
    assert [j["job_id"] for j in client.get(f"/api/projects/{PID}/optimizations").json()] == [job]

    applied = client.post(f"/api/projects/{PID}/optimizations/{job}/apply", json={}).json()
    assert applied["status"] == "draft" and applied["parentId"] == "setup_7d6d"
    assert client.get(f"/api/projects/{PID}/optimizations/{job}").json()["status"]["applied_setup_id"] == applied["id"]
    assert client.post(f"/api/projects/{PID}/setups/nope/optimize", json={"spec": spec}).status_code == 404
