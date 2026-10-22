"""End-to-end API flow on the bundled sample project, using the LLM-free engine."""

import json
import time

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # DATA_DIR is relative (".data"), so the test owns a fresh copy
    from store_emulator.server.main import app
    with TestClient(app) as c:  # lifespan seeds the sample project into tmp_path/.data
        yield c


def _wait(client: TestClient, run_id: str) -> dict[str, object]:
    for _ in range(600):
        status = client.get(f"/api/projects/{PID}/runs/{run_id}/status").json()
        if status["status"] in ("completed", "failed"):
            return status
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def _preview(client: TestClient, setup_id: str, run_id: str) -> dict[str, object]:
    resp = client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": setup_id, "run_id": run_id, "engine_type": "rule_based",
        "seed": 5, "max_customers": 300, "preview": True,
    })
    assert resp.status_code == 200, resp.text
    status = _wait(client, run_id)
    assert status["status"] == "completed", status.get("error")
    return status


def test_engines_endpoint(client):
    engines = client.get("/api/engines").json()
    assert {e["engine_type"] for e in engines} == {"pattern_intent_impulse", "rule_based", "vlm_glance"}
    vision = next(e for e in engines if e["engine_type"] == "vlm_glance")
    assert vision["uses_llm"] is True and vision["model"]


def test_preview_runs_compare_export_and_fidelity(client, tmp_path):
    # Both sample setups are already finalized; preview runs are allowed on them and do not touch them.
    status_a = _preview(client, "setup_7d6d", "prev_a")
    _preview(client, "setup_eaf5", "prev_b")
    assert status_a["completed_customers"] == 300 and status_a["preview"] is True
    assert client.get(f"/api/projects/{PID}/setups/setup_7d6d").json()["status"] == "locked"

    summary = client.get(f"/api/projects/{PID}/runs/prev_a/summary").json()["summary"]
    assert summary["total_customers"] == 300
    assert 0 < summary["conversion_rate"] <= 1
    assert summary["racks"] and summary["segments"]["age_group"]

    diag = client.get(f"/api/projects/{PID}/runs/prev_a/diagnostics").json()
    assert diag["manifest"]["engine_type"] == "rule_based" and diag["manifest"]["seed"] == 5
    assert diag["diagnostics"]["failed_customers"] == []

    heat = client.get(f"/api/projects/{PID}/runs/prev_a/heatmap").json()
    assert heat["dwell_heatmap"] and sum(map(sum, heat["dwell_heatmap"])) > 0

    report = client.get(f"/api/projects/{PID}/compare", params={"a": "prev_a", "b": "prev_b", "n_bootstrap": 300}).json()
    assert report["paired_customers"] == 300
    assert {m["metric"] for m in report["metrics"]} >= {"spend", "bought", "path_tiles"}

    csv_resp = client.get(f"/api/projects/{PID}/runs/prev_a/export.csv")
    assert csv_resp.status_code == 200 and csv_resp.text.lstrip("﻿").startswith("persona_id,day,arrival_time")

    # Use the simulated receipts as a stand-in POS export: fidelity must be perfect.
    timeline = client.get(f"/api/projects/{PID}/runs/prev_a/timeline").json()
    rows = ["receipt_id,sku,qty,unit_price,hour"]
    for c in timeline:
        for e in c["timeline"]:
            if e["action"] == "buy":
                rows.append(f"{c['persona_id']},{e['product_sku']},{e['quantity']},{e['price']},{c['arrival_time'][:2]}")
    fid = client.post(f"/api/projects/{PID}/runs/prev_a/fidelity",
                      files={"file": ("pos.csv", "\n".join(rows).encode(), "text/csv")}).json()
    values = {m["name"]: m["value"] for m in fid["metrics"]}
    assert values["sku_js_similarity"] == 1.0 and values["hourly_js_similarity"] == 1.0

    sku = next(e["product_sku"] for c in timeline for e in c["timeline"] if e["action"] == "buy")
    returns = f"receipt_id,sku,qty,unit_price,hour\nrefund,{sku},-1,100,12\n".encode()
    response = client.post(f"/api/projects/{PID}/runs/prev_a/fidelity", files={"file": ("returns.csv", returns, "text/csv")})
    assert response.status_code == 200, response.text
    report = response.json()
    scores = {metric["name"]: metric["value"] for metric in report["metrics"]}
    assert scores["sku_js_similarity"] is None and scores["sku_ndcg@10"] is None
    assert any("negative net POS units" in note for note in report["notes"])
    saved = json.loads((tmp_path / ".data" / PID / "runs" / "prev_a" / "output" / "fidelity.json").read_text())
    assert saved == report

    # A POS export in another product code matches nothing: refused, and the saved report stays.
    foreign = b"receipt_id,sku,qty,unit_price,hour\nr1,8801234567890,1,100,12\nr2,8801234567891,2,150,13\n"
    refused = client.post(f"/api/projects/{PID}/runs/prev_a/fidelity", files={"file": ("pos.csv", foreign, "text/csv")})
    assert refused.status_code == 400 and "None of the 2 POS lines" in refused.json()["detail"]
    assert json.loads((tmp_path / ".data" / PID / "runs" / "prev_a" / "output" / "fidelity.json").read_text()) == report


def test_locked_setup_rejects_non_preview_runs(client):
    resp = client.post(f"/api/projects/{PID}/runs", json={"setup_id": "setup_7d6d", "engine_type": "rule_based"})
    assert resp.status_code == 409
    assert "preview" in resp.json()["detail"]
