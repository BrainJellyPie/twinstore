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
    spells = report["empty_spells"]
    assert spells and all(s["start"] < s["end"] for s in spells)
    assert {(s["rack_id"], s["sku"]) for s in spells} >= {(s["rack_id"], s["sku"]) for s in report["stockouts"]
                                                         if s["first_out"]}
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


def _layout(c: TestClient) -> str:
    return c.post(f"/api/projects/{PID}/setups",
                  json={"mode": "racks_and_items", "source_setup_id": "setup_7d6d"}).json()["id"]


def test_a_replay_with_the_runs_own_plan_gives_the_run_back(client):
    operations = {"stock_per_facing": 2, "open_counters": 1, "patience_sec": 120}
    rid = _run(client, _layout(client), operations=operations)
    assert Path(f".data/{PID}/runs/{rid}/output/timeline_planned.json").exists()
    saved = client.get(f"/api/projects/{PID}/runs/{rid}/operations").json()
    summary = client.get(f"/api/projects/{PID}/runs/{rid}/summary").json()["summary"]
    replay = client.post(f"/api/projects/{PID}/runs/{rid}/operations/replay",
                         json={"operations": saved["config"]}).json()
    assert replay["outcome"]["revenue"] == summary["total_revenue"]
    assert replay["report"] == saved
    assert replay["planned_revenue"] >= replay["outcome"]["revenue"]


def test_any_finished_run_replays_in_a_shared_store_and_gets_a_plan(client):
    rid = _run(client, _layout(client))
    summary = client.get(f"/api/projects/{PID}/runs/{rid}/summary").json()["summary"]
    tight = client.post(f"/api/projects/{PID}/runs/{rid}/operations/replay",
                        json={"operations": {"stock_per_facing": 1, "restock_every_min": None, "open_counters": 1},
                              "costs": {"till_hour": 1000}}).json()
    assert tight["planned_revenue"] == summary["total_revenue"]
    assert tight["outcome"]["revenue"] <= summary["total_revenue"]
    assert tight["outcome"]["labor_cost"] == round(tight["outcome"]["till_hours"] * 1000)
    plan = client.post(f"/api/projects/{PID}/runs/{rid}/operations/plan",
                       json={"costs": {"till_hour": 1000, "restock_round": 300, "stock_unit_day": 1}}).json()
    assert plan["best"]["net"] >= plan["current"]["net"] and plan["replays"] > 1
    assert set(plan["config"]) >= {"stock_per_facing", "restock_every_min", "till_schedule", "stock_overrides"}


def test_a_shared_run_without_its_planned_visits_says_why_it_cannot_replay(client):
    rid = _run(client, _layout(client), operations={})
    Path(f".data/{PID}/runs/{rid}/output/timeline_planned.json").unlink()
    response = client.post(f"/api/projects/{PID}/runs/{rid}/operations/replay", json={})
    assert response.status_code == 409 and "run it again" in response.json()["detail"]
    assert client.post(f"/api/projects/{PID}/runs/run_nothere/operations/plan", json={}).status_code == 404


@pytest.mark.parametrize("bad", [{"costs": {"till_hour": -1}}, {"max_tills": 0},
                                 {"operations": {"till_schedule": {"25": 1}}}])
def test_impossible_plan_requests_are_refused(client, bad):
    response = client.post(f"/api/projects/{PID}/runs/run_x/operations/plan", json=bad)
    assert response.status_code == 422


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("damaged", [None, 0, True, {}, {"shoppers": []}, "", [None]])
def test_damaged_saved_visits_are_reported_without_changing_the_run(client, shared, damaged):
    rid = _run(client, _layout(client), **({"operations": {}} if shared else {}))
    output = Path(f".data/{PID}/runs/{rid}/output")
    path = output / ("timeline_planned.json" if shared else "timeline.json")
    path.write_text(json.dumps(damaged), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    for action in ("replay", "plan"):
        response = client.post(f"/api/projects/{PID}/runs/{rid}/operations/{action}", json={})
        assert response.status_code == 422
        assert "saved files cannot be read" in response.json()["detail"]
    assert {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()} == before


@pytest.mark.parametrize("hour", ["０１", "٠١", " 1", "+1", "-1", "24"])
def test_noncanonical_till_hours_are_rejected_before_loading_a_run(client, hour):
    for action in ("replay", "plan"):
        response = client.post(f"/api/projects/{PID}/runs/run_missing/operations/{action}",
                               json={"operations": {"till_schedule": {hour: 1}}})
        assert response.status_code == 422


def test_a_replay_and_a_plan_follow_the_weeks_when_shoppers_remember(client):
    rid = _run(client, _layout(client))
    memory = {"weeks": 4, "leave_per_missing_unit": 0.2}
    replay = client.post(f"/api/projects/{PID}/runs/{rid}/operations/replay",
                         json={"operations": {"stock_per_facing": 1, "restock_every_min": None}, "memory": memory}).json()
    weeks = replay["weeks"]
    assert [w["week"] for w in weeks["weeks"]] == [1, 2, 3, 4]
    assert weeks["weeks"][0]["revenue"] == replay["outcome"]["revenue"]
    assert all(w["shoppers"] <= w["ideal_shoppers"] for w in weeks["weeks"])
    assert client.post(f"/api/projects/{PID}/runs/{rid}/operations/replay", json={}).json()["weeks"] is None
    plan = client.post(f"/api/projects/{PID}/runs/{rid}/operations/plan",
                       json={"operations": {"stock_per_facing": 1, "restock_every_min": None}, "memory": memory}).json()
    assert plan["best_weeks"]["net"] >= plan["current_weeks"]["net"]


@pytest.mark.parametrize("memory", [{"weeks": 1}, {"weekly_churn": 2}])
def test_impossible_memory_settings_are_refused_by_the_api(client, memory):
    assert client.post(f"/api/projects/{PID}/runs/run_x/operations/replay", json={"memory": memory}).status_code == 422


def test_a_run_made_before_crowding_replays_without_it(client):
    rid = _run(client, _layout(client), operations={"stock_per_facing": 2, "open_counters": 1, "crowd_limit": None})
    path = Path(f".data/{PID}/runs/{rid}/output/operations.json")
    saved = json.loads(path.read_text(encoding="utf-8"))
    for key in ("crowd_limit", "crowd_skip"):
        del saved["config"][key]
    path.write_text(json.dumps(saved), encoding="utf-8")
    summary = client.get(f"/api/projects/{PID}/runs/{rid}/summary").json()["summary"]
    plan = client.post(f"/api/projects/{PID}/runs/{rid}/operations/plan", json={}).json()
    assert plan["current_config"]["crowd_limit"] is None
    assert plan["current"]["revenue"] == summary["total_revenue"]
