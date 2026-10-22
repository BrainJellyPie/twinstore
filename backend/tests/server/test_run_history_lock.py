"""Customers stay locked while final runs use them, even after their layout is deleted; a restart between a final
run's completion and its layout's lock still locks the layout."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import read_setup, recover_running_setups, setup_path

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _final_run_on_a_branch(client: TestClient) -> tuple[str, str]:
    root = client.get(f"/api/projects/{PID}/setups").json()[0]["id"]
    child = client.post(f"/api/projects/{PID}/setups",
                        json={"mode": "racks_and_items", "source_setup_id": root, "name": "child"}).json()["id"]
    run = client.post(f"/api/projects/{PID}/runs",
                      json={"setup_id": child, "engine_type": "rule_based", "max_customers": 30, "seed": 1}).json()["run_id"]
    for _ in range(300):
        if client.get(f"/api/projects/{PID}/runs/{run}/status").json()["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    return child, run


def test_deleting_the_simulated_layout_keeps_the_customers_locked(client, tmp_path):
    # A project whose only history is the branch we run (the sample's own finalized layouts are cleared).
    for setup in client.get(f"/api/projects/{PID}/setups").json():
        data = read_setup(PID, setup["id"])
        data.update(status="draft", runId=None)
        write_json(setup_path(PID, setup["id"]), data)
    for run in (tmp_path / ".data" / PID / "runs").iterdir():
        status = run / "status.json"
        if status.exists():
            write_json(status, {**json.loads(status.read_text()), "preview": True})
    personas = client.get(f"/api/projects/{PID}").json()["personas"]
    assert client.get(f"/api/projects/{PID}").json()["personasLocked"] is False

    child, _ = _final_run_on_a_branch(client)
    assert client.delete(f"/api/projects/{PID}/setups/{child}").status_code in (200, 204)
    project = client.get(f"/api/projects/{PID}").json()
    assert project["personasLocked"] is True
    assert client.put(f"/api/projects/{PID}/personas", json={"personas": personas}).status_code == 409


def test_a_restart_after_a_final_run_completed_locks_its_layout(client):
    child, run = _final_run_on_a_branch(client)
    data = read_setup(PID, child)
    data.update(status="running", runId=None)   # as if the server stopped before locking it
    write_json(setup_path(PID, child), data)
    recover_running_setups()
    recovered = read_setup(PID, child)
    assert recovered["status"] == "locked" and recovered["runId"] == run
