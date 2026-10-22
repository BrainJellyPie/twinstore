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


def test_vlm_judged_optimization_applies_the_vlm_winner(client, monkeypatch):
    from store_emulator.application import optimize as opt_service
    from tests.engine.test_vlm_judge import FakeShopperVLM

    from store_emulator.application import local_vlm

    monkeypatch.setattr(opt_service, "build_client", lambda *args, **kwargs: FakeShopperVLM())
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: True)   # the local model is up
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    spec = {"objective": "revenue_per_visitor", "scope": "planogram", "budget": 6, "eval_customers": 40, "seed": 2}
    started = client.post(f"/api/projects/{PID}/setups/setup_7d6d/optimize", json={
        "spec": spec, "judge": "vlm", "vlm_customers": 8, "top_k": 2, "calibrate": True,
    })
    assert started.status_code == 200, started.text
    assert started.json()["judge"]["judge"] == "vlm"
    job = started.json()["job_id"]
    for _ in range(1800):
        view = client.get(f"/api/projects/{PID}/optimizations/{job}").json()
        if view["status"]["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert view["status"]["status"] == "completed", view["status"]["error"]
    assert view["status"]["phase"] == "done"
    result = view["result"]
    judge = result["judge"]
    assert judge["candidates"][0]["label"] == "baseline" and len(judge["candidates"]) == 3
    assert judge["calibration"]["grid_points"] >= 8 and judge["customers"] == 8
    winner = next(c for c in judge["candidates"] if c["winner"])
    assert judge["winner"] == winner["label"] and result["best_score"] == winner["vlm_score"]
    assert result["applied_moves"] == winner["moves"] and "top_candidates" not in result
    applied = client.post(f"/api/projects/{PID}/optimizations/{job}/apply", json={}).json()
    saved = client.get(f"/api/projects/{PID}/setups/{applied['id']}").json()
    assert saved["store"] == result["best_store"]
    # A canceled (or finished) job reports its status; unknown jobs are 404.
    assert client.post(f"/api/projects/{PID}/optimizations/{job}/cancel").json()["status"] == "completed"
    assert client.post(f"/api/projects/{PID}/optimizations/nope/cancel").status_code == 404
    bad = client.post(f"/api/projects/{PID}/setups/setup_7d6d/optimize",
                      json={"spec": spec, "judge": "vlm", "model": "anthropic:claude-haiku-5-5"})
    assert bad.status_code == 400 and "API key" in bad.text
    assert client.post(f"/api/projects/{PID}/setups/setup_7d6d/optimize",
                       json={"spec": spec, "judge": "vlm", "vlm_customers": 401}).status_code == 422
