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


def test_demand_of_an_unknown_scenario_is_rejected(client: TestClient):
    client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "residential", "seed": 1, "size_m": 400})
    resp = client.get(f"/api/projects/{PID}/town/demand", params={"scenario_id": "nope"})
    assert resp.status_code == 400 and "nope" in resp.json()["detail"]


def test_demand_and_synergy_follow_the_active_layouts_hours_and_store_format(client: TestClient):
    from store_emulator.application.scenarios import get_preset
    from store_emulator.application.storage.setups import (
        read_setup,
        read_state,
        write_setup,
    )
    from store_emulator.domain.town import Town
    from store_emulator.engine.scenario import compile_scenario, priors_for
    from store_emulator.engine.town import estimate_demand
    from store_emulator.server.deps import get_config

    town = Town.model_validate(client.post(f"/api/projects/{PID}/town/generate",
                                           json={"archetype": "residential", "seed": 1, "size_m": 400}).json())
    # The sample's active layout opens 8–20 on weekdays and is closed at the weekend.
    weekday = client.get(f"/api/projects/{PID}/town/demand").json()
    assert weekday["total_daily_visitors"] > 0
    assert all(v == 0 for h, v in enumerate(weekday["hourly_totals"]) if not 8 <= h < 20)
    open_8_20 = town.model_copy(update={"venues": [
        v.model_copy(update={"open_hour": 8, "close_hour": 20}) if v.is_focal else v for v in town.venues]})
    expected = estimate_demand(open_8_20, hours=range(8, 20))
    assert weekday["total_daily_visitors"] == pytest.approx(expected.total_daily_visitors)
    assert weekday["market_share"] == pytest.approx(expected.market_share)  # rivals' trips at closed hours left out
    assert client.get(f"/api/projects/{PID}/town/demand", params={"day_type": "weekend"}).json()[
        "total_daily_visitors"] == 0
    rows = client.get(f"/api/projects/{PID}/town/synergy", params={"day_type": "weekend"}).json()
    assert rows and all(r["effect_on_focal_visitors"] == 0 for r in rows)

    setup_id = read_state(PID)["activeSetupId"]
    setup = read_setup(PID, setup_id)
    setup["store"]["weekly_schedule"] = [{"day": d, "is_open": True, "open_hour": 0, "close_hour": 24}
                                         for d in range(1, 8)]
    setup["store"]["type"] = "supermarket"
    write_setup(PID, setup_id, setup)
    always = client.get(f"/api/projects/{PID}/town/demand").json()
    assert sum(always["hourly_totals"][:7]) > 0  # a 24-hour store has night visitors
    assert always["total_daily_visitors"] == pytest.approx(estimate_demand(town, hours=range(24)).total_daily_visitors)
    rainy = client.get(f"/api/projects/{PID}/town/demand", params={"scenario_id": "rainy_commute"}).json()
    scenario = get_preset("rainy_commute")
    assert scenario is not None
    traffic = compile_scenario(scenario, priors_for("supermarket", get_config().scenario_priors)).base_traffic
    assert traffic != compile_scenario(scenario).base_traffic
    assert rainy["total_daily_visitors"] == pytest.approx(traffic * always["total_daily_visitors"], rel=1e-3)


def test_runs_with_neighborhood_visitors_need_a_neighborhood(client: TestClient):
    body = {"setup_id": "setup_7d6d", "run_id": "no_town", "engine_type": "rule_based", "preview": True,
            "max_customers": 5, "use_town": True}
    for path in ("runs/estimate", "runs"):
        resp = client.post(f"/api/projects/{PID}/{path}", json=body)
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == ("This project has no neighborhood yet — generate one or import a map on the "
                                         "Area page, or turn off neighborhood visitors.")
    assert not (Path(".data") / PID / "runs" / "no_town").exists()  # nothing was started
    assert client.post(f"/api/projects/{PID}/runs/estimate", json={**body, "use_town": False}).status_code == 200


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


def test_vlm_synergy_job(client, monkeypatch):
    from store_emulator.application import town_synergy
    from tests.engine.test_vlm_synergy import CafeLoverVLM

    from store_emulator.application import local_vlm

    monkeypatch.setattr(town_synergy, "build_client", lambda *args, **kwargs: CafeLoverVLM())
    monkeypatch.setattr(local_vlm, "server_answers", lambda base: True)   # the local model is up
    town = client.post(f"/api/projects/{PID}/town/generate",
                       json={"archetype": "residential", "seed": 4, "size_m": 400, "n_competitors": 1,
                             "venue_density": 0.0}).json()
    focal = next(v for v in town["venues"] if v["is_focal"])
    edited = client.post(f"/api/projects/{PID}/town/venues",
                         json={"category": "cafe", "x": focal["x"] + 12, "y": focal["y"], "name": "Corner Cafe"}).json()
    cafe = next(v["id"] for v in edited["venues"] if v["name"] == "Corner Cafe")
    started = client.post(f"/api/projects/{PID}/town/venues/{cafe}/synergy-vlm",
                          json={"customers": 10, "setup_id": "setup_7d6d", "scenario_id": "rainy_commute"})
    assert started.status_code == 200, started.text
    job = started.json()["job_id"]
    for _ in range(900):
        view = client.get(f"/api/projects/{PID}/town/synergy-jobs/{job}").json()
        if view["status"]["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert view["status"]["status"] == "completed", view["status"]["error"]
    result = view["result"]
    assert result["venue_name"] == "Corner Cafe" and result["scenario"] == "Rainy commute"
    assert result["delta_visitors"] > 0 and result["delta_spend_per_visitor"] > 0
    assert result["delta_revenue_per_day"] > 0 and result["category_shifts"]
    assert view["status"]["done"] == view["status"]["total"] == 10 + result["affected_customers"]
    assert [j["job_id"] for j in client.get(f"/api/projects/{PID}/town/synergy-jobs").json()] == [job]
    assert client.post(f"/api/projects/{PID}/town/venues/{focal['id']}/synergy-vlm", json={}).status_code == 400
    assert client.post(f"/api/projects/{PID}/town/venues/nope/synergy-vlm", json={}).status_code == 404
    assert client.get(f"/api/projects/{PID}/town/synergy-jobs/nope").status_code == 404
