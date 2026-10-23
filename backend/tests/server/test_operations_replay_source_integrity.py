"""Missing shared-store evidence must not turn already-depleted purchases into fresh plans."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import operations_lab
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.domain.operations import OperationsConfig
from store_emulator.engine.simulation.shared_store import resolve_shared_store
from store_emulator.server.main import app
from tests.engine.test_shared_store import _shopper, _store

PID, RID = "proj_replay", "run_source"


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = Path(".data") / PID / "runs" / RID
    store = _store()
    planned = [_shopper("buyer", "12:00:00", [("chips", 1)])]
    operations = OperationsConfig(stock_overrides={"chips": 0}, substitute_share=0, restock_every_min=None)
    resolved, report = resolve_shared_store(store, planned, operations, seed=1)
    assert planned[0].total_spent == 300 and resolved[0].total_spent == 0
    write_json(root / "input" / "store.json", store.model_dump(mode="json"))
    write_json(root / "input" / "config.json", {"seed": 1, "operations": operations.model_dump(mode="json")})
    write_json(root / "status.json", {"status": "completed"})
    write_json(root / "output" / "timeline.json", [r.model_dump(mode="json") for r in resolved])
    write_json(root / "output" / "timeline_planned.json", [r.model_dump(mode="json") for r in planned])
    write_json(root / "output" / "operations.json", report.model_dump(mode="json"))
    return TestClient(app, raise_server_exceptions=False), root


@pytest.mark.parametrize("endpoint", ["replay", "plan"])
@pytest.mark.parametrize("declared,planned_present", [(True, True), (True, False), (False, True)])
def test_missing_shared_report_is_rejected_before_replaying_stockouts(saved, monkeypatch, endpoint, declared, planned_present):
    client, root = saved
    (root / "output" / "operations.json").unlink()
    if not planned_present:
        (root / "output" / "timeline_planned.json").unlink()
    if not declared:
        write_json(root / "input" / "config.json", {"seed": 1})
    before = {p: p.read_bytes() for p in root.rglob("*.json")}
    search = Mock(side_effect=AssertionError("planner must not consume incomplete source files"))
    monkeypatch.setattr(operations_lab, "plan_operations", search)
    response = client.post(f"/api/projects/{PID}/runs/{RID}/operations/{endpoint}", json={})
    assert response.status_code == 422, response.text
    assert "operations" in response.json()["detail"]
    search.assert_not_called()
    assert {p: p.read_bytes() for p in root.rglob("*.json")} == before


@pytest.mark.parametrize("config", [None, [], True, "broken"])
def test_nonobject_saved_configuration_is_not_a_valid_replay_source(saved, config):
    client, root = saved
    write_json(root / "input" / "config.json", config)
    response = client.post(f"/api/projects/{PID}/runs/{RID}/operations/replay", json={})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("legacy", [False, True])
def test_intact_shared_run_replays_its_original_demand(saved, legacy):
    client, root = saved
    if legacy:
        write_json(root / "input" / "config.json", {"seed": 1})
    response = client.post(f"/api/projects/{PID}/runs/{RID}/operations/replay", json={})
    assert response.status_code == 200, response.text
    assert response.json()["planned_revenue"] == response.json()["outcome"]["revenue"] == 300


@pytest.mark.parametrize("explicit", [False, True])
def test_unshared_runs_without_a_shared_report_remain_replayable(saved, explicit):
    client, root = saved
    original = read_json(root / "output" / "timeline_planned.json")
    (root / "output" / "timeline_planned.json").unlink()
    (root / "output" / "operations.json").unlink()
    write_json(root / "output" / "timeline.json", original)
    write_json(root / "input" / "config.json", {"seed": 1, **({"operations": None} if explicit else {})})
    response = client.post(f"/api/projects/{PID}/runs/{RID}/operations/replay", json={})
    assert response.status_code == 200, response.text
    assert response.json()["planned_revenue"] == response.json()["outcome"]["revenue"] == 300
