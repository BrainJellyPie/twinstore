"""Neighborhood API and town-driven runs, on the bundled sample project."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_generate_edit_demand_and_synergy(client):
    assert client.get(f"/api/projects/{PID}/town").status_code == 404
    town = client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "university", "seed": 3}).json()
    assert town["archetype"] == "university" and town["focal_venue_id"]
    focal = next(v for v in town["venues"] if v["is_focal"])
    base = client.get(f"/api/projects/{PID}/town/demand").json()
    assert base["total_daily_visitors"] > 100 and len(base["hourly_totals"]) == 24

    rival = client.post(f"/api/projects/{PID}/town/venues",
                        json={"category": "convenience", "x": focal["x"] + 15, "y": focal["y"], "name": "Rival"}).json()
    rival_id = next(v["id"] for v in rival["venues"] if v["name"] == "Rival")
    with_rival = client.get(f"/api/projects/{PID}/town/demand").json()
    assert with_rival["total_daily_visitors"] < base["total_daily_visitors"]

    rows = client.get(f"/api/projects/{PID}/town/synergy").json()
    assert next(r for r in rows if r["venue_id"] == rival_id)["role"] == "competitor"

    assert client.delete(f"/api/projects/{PID}/town/venues/{rival_id}").status_code == 200
    assert client.delete(f"/api/projects/{PID}/town/venues/{focal['id']}").status_code == 400  # focal is protected

    rainy = client.get(f"/api/projects/{PID}/town/demand", params={"scenario_id": "typhoon"}).json()
    assert rainy["total_daily_visitors"] < 0.6 * base["total_daily_visitors"]


def test_run_with_town_visitors_saves_arrivals(client):
    client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "residential", "seed": 1})
    resp = client.post(f"/api/projects/{PID}/runs", json={
        "setup_id": "setup_7d6d", "run_id": "town_run", "engine_type": "rule_based", "seed": 2,
        "preview": True, "use_town": True, "town_scale": 0.05, "scenario_id": "rainy_commute",
    })
    assert resp.status_code == 200, resp.text
    for _ in range(600):
        status = client.get(f"/api/projects/{PID}/runs/town_run/status").json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert status["status"] == "completed", status.get("error")
    out = Path(".data") / PID / "runs" / "town_run" / "output"
    arrivals = json.loads((out / "town_arrivals.json").read_text())
    assert arrivals["arrivals"] and all(a["persona_id"].count("~t") == 1 for a in arrivals["arrivals"])
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["town"] and manifest["scenario_id"] == "rainy_commute"
    personas = json.loads((out.parent / "input" / "personas.json").read_text())
    assert any("m (" in p["description"] for p in personas)  # walk distance annotation
