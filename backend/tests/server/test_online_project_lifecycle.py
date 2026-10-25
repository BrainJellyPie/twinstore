"""Accepted online jobs keep their project until their worker has finished."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import online, projects
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID, layout


@pytest.fixture
def study(layout, monkeypatch):
    submit = Mock()
    monkeypatch.setattr(online, "submit_background", submit)
    client = TestClient(app)
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"})
    assert site.status_code == 200

    def start():
        return client.post(f"/api/projects/{PID}/online/runs",
                           json={"site_ids": [site.json()["id"]], "shoppers": 1, "max_steps": 3})

    return client, submit, start


@pytest.mark.parametrize("state", ["pending", "running"])
def test_delete_waits_for_registered_online_worker_and_allows_cleanup_after_completion(study, state):
    client, submit, start = study
    accepted = start()
    assert accepted.status_code == 200
    args = submit.call_args.args
    status = args[3]
    status.status = state
    online._write_status(PID, status)
    root = metadata_path(PID).parent
    snapshots = {p: p.read_bytes() for p in (root / "online").rglob("*.json")}
    removed = client.delete(f"/api/projects/{PID}")
    assert removed.status_code == 409 and status.run_id in removed.text
    assert metadata_path(PID).is_file()
    assert all(path.read_bytes() == data for path, data in snapshots.items())
    args[1](*args[2:])  # The captured rule worker is deterministic and makes no model calls.
    saved = read_json(root / "online" / "runs" / status.run_id / "status.json")
    assert saved["status"] == "completed" and saved["done"] == saved["total"] == 1
    assert client.delete(f"/api/projects/{PID}").status_code == 200
    assert not root.exists()


@pytest.mark.parametrize("start_first", [False, True])
def test_registration_and_deletion_respect_the_project_lock(study, monkeypatch, start_first):
    client, submit, start = study
    delete = lambda: client.delete(f"/api/projects/{PID}")
    if start_first:
        started, removed = overlap(monkeypatch, online, "_write_status", start, delete)
    else:
        removed, started = overlap(monkeypatch, projects, "remove_tree", delete, start)
    assert started.status_code == (200 if start_first else 404), started.text
    assert removed.status_code == (409 if start_first else 200), removed.text
    assert submit.call_count == (1 if start_first else 0)
    assert metadata_path(PID).parent.exists() is start_first
    assert len(online.list_runs(PID)) == (1 if start_first else 0)
