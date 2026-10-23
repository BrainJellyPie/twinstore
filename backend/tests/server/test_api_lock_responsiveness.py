"""A busy layout must not stall unrelated requests on the same server loop."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import setups, simulation
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("operation", [
    "run", "preview", "slots", "empty", "racks", "racks_and_items",
    "delete_layout_tree", "delete_layout", "delete_project", "personas",
])
def test_lock_wait_leaves_health_available_and_resumes_after_release(layout, monkeypatch, operation):
    @asynccontextmanager
    async def no_startup(_app):
        # Keep the production routes and single event loop, without seeding
        # sample data or starting/stopping local model services.
        yield

    monkeypatch.setattr(app.router, "lifespan_context", no_startup)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    base = f"/api/projects/{PID}"
    setup_url = f"{base}/setups/{SID}"
    method, url, payload = "POST", f"{base}/runs", {
        "setup_id": SID, "run_id": "run_responsive", "engine_type": "rule_based",
        "preview": operation == "preview",
    }
    if operation == "slots":
        method, url, payload = "PUT", f"{setup_url}/slots", {"slots": []}
    elif operation == "personas":
        method, url, payload = "PUT", f"{base}/personas", {"personas": read_json(personas_path(PID))}
    elif operation in {"empty", "racks", "racks_and_items"}:
        url, payload = f"{base}/setups", {"source_setup_id": SID, "mode": operation}
    elif operation.startswith("delete"):
        method, url, payload = "DELETE", base if operation == "delete_project" else setup_url, None

    held_path = setups.setup_lock_path(PID, SID)
    if operation in {"empty", "racks", "racks_and_items", "delete_layout_tree", "delete_project"}:
        held_path = held_path.with_name(".setup-tree.lock")
    attempted = Event()

    def observed_lock(path, timeout):
        if Path(path) == held_path:
            attempted.set()
        return FileLock(path, timeout=timeout)

    monkeypatch.setattr(simulation if operation in {"run", "preview"} else setups, "FileLock", observed_lock)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        with FileLock(held_path, timeout=0):
            pending = pool.submit(client.request, method, url, json=payload)
            assert attempted.wait(5), "the request did not reach its real file lock"
            health = pool.submit(client.get, "/api/health")
            assert health.result(timeout=1).json() == {"status": "ok"}
            assert not pending.done(), "the protected request bypassed the held lock"
        response = pending.result(timeout=5)
    assert response.status_code == 200, response.text
    if operation in {"run", "preview"}:
        assert submit.call_count == 1
        assert simulation.get_run_status(PID, "run_responsive")["status"] == "pending"
        assert read_setup(PID, SID)["status"] == ("draft" if operation == "preview" else "running")
    elif operation == "slots":
        assert response.json()["count"] == 0
        assert all(not rack["slots"] for rack in read_setup(PID, SID)["store"]["racks"])
    elif operation == "personas":
        assert response.json() == {"status": "saved"}
    elif operation == "delete_project":
        assert not metadata_path(PID).exists()
    elif operation.startswith("delete_layout"):
        assert not setup_path(PID, SID).exists()
    else:
        child = read_setup(PID, response.json()["id"])
        assert child["parentId"] == SID
