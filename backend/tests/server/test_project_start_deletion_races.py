"""Starting a simulation and removing its project cannot both succeed."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import projects, setups, simulation
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, read_setup, setup_path
from store_emulator.domain.operations import OperationsConfig
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("preview", [False, True])
def test_a_start_publishing_pending_status_prevents_project_deletion(layout, monkeypatch, preview):
    ready, release, removed = Event(), Event(), Event()
    original_write, original_remove = simulation.write_status, projects.remove_tree

    def paused_pending(pid, rid, status, **extra):
        ready.set()
        assert release.wait(5)
        original_write(pid, rid, status, **extra)

    def observed_remove(path):
        original_remove(path)
        removed.set()

    monkeypatch.setattr(simulation, "write_status", paused_pending)
    monkeypatch.setattr(projects, "remove_tree", observed_remove)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        start = pool.submit(client.post, f"/api/projects/{PID}/runs", json={
            "setup_id": SID, "run_id": "run_starting", "engine_type": "rule_based", "preview": preview,
        })
        try:
            assert ready.wait(5)
            deletion = pool.submit(client.delete, f"/api/projects/{PID}")
            removed.wait(0.25)
        finally:
            release.set()
        started, deleted = start.result(timeout=5), deletion.result(timeout=5)
    assert started.status_code == 200, started.text
    assert deleted.status_code == 409, deleted.text
    assert metadata_path(PID).is_file()
    assert read_setup(PID, SID)["status"] == ("draft" if preview else "running")
    assert simulation.get_run_status(PID, "run_starting")["status"] == "pending"
    assert submit.call_count == 1


@pytest.mark.parametrize("preview", [False, True])
def test_a_deleting_project_cannot_accept_a_new_run(layout, monkeypatch, preview):
    deleting, release, attempted_start, pending_written = Event(), Event(), Event(), Event()
    original_remove, original_write = projects.remove_tree, simulation.write_status

    def paused_remove(path):
        deleting.set()
        assert release.wait(5)
        original_remove(path)

    def observed_lock(path, timeout):
        attempted_start.set()
        return FileLock(path, timeout=timeout)

    def observed_pending(pid, rid, status, **extra):
        original_write(pid, rid, status, **extra)
        pending_written.set()

    monkeypatch.setattr(projects, "remove_tree", paused_remove)
    monkeypatch.setattr(simulation, "FileLock", observed_lock)
    monkeypatch.setattr(simulation, "write_status", observed_pending)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(client.delete, f"/api/projects/{PID}")
        try:
            assert deleting.wait(5)
            start = pool.submit(client.post, f"/api/projects/{PID}/runs", json={
                "setup_id": SID, "run_id": "run_too_late", "engine_type": "rule_based", "preview": preview,
            })
            assert attempted_start.wait(5)
            pending_written.wait(0.25)
        finally:
            release.set()
        deleted, started = deletion.result(timeout=5), start.result(timeout=5)
    assert deleted.status_code == 200, deleted.text
    assert started.status_code == 404, started.text
    assert not metadata_path(PID).parent.exists()
    submit.assert_not_called()


@pytest.mark.parametrize("locked", [SID, "setup_unrelated"])
def test_busy_layout_prevents_partial_project_removal(layout, monkeypatch, locked):
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    write_json(setup_path(PID, "setup_first"), {**read_setup(PID, SID), "id": "setup_first"})
    before = setup_path(PID, SID).read_bytes()
    with FileLock(setups.setup_lock_path(PID, locked), timeout=0):
        response = TestClient(app).delete(f"/api/projects/{PID}")
    assert response.status_code == (503 if locked == SID else 200), response.text
    if locked == SID:
        assert metadata_path(PID).is_file()
        assert setup_path(PID, SID).read_bytes() == before
        assert setup_path(PID, "setup_first").is_file()
        with FileLock(setups.setup_lock_path(PID, "setup_first"), timeout=0):
            pass  # a later busy layout must release locks already acquired
    else:
        assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("content", ["{", "[]", "null", '{"id":"wrong"}'])
def test_damaged_layouts_do_not_prevent_project_cleanup(layout, content):
    setup_path(PID, SID).write_text(content)
    setup_path(PID, "unaddressable layout").write_text(content)
    response = TestClient(app).delete(f"/api/projects/{PID}")
    assert response.status_code == 200, response.text
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("operations", [False, True])
def test_pending_layout_save_cannot_recreate_a_deleted_project(layout, monkeypatch, operations):
    ready, release, removed = Event(), Event(), Event()
    original_write, original_remove = setups.write_setup, projects.remove_tree

    def paused_write(pid, sid, data):
        ready.set()
        assert release.wait(5)
        original_write(pid, sid, data)

    def observed_remove(path):
        original_remove(path)
        removed.set()

    monkeypatch.setattr(setups, "write_setup", paused_write)
    monkeypatch.setattr(projects, "remove_tree", observed_remove)
    with ThreadPoolExecutor(max_workers=2) as pool:
        if operations:
            save = pool.submit(setups.save_layout_operations, PID, SID, OperationsConfig(stock_per_facing=31))
        else:
            save = pool.submit(setups.save_setup_with_lock, PID, SID, {"name": "Edited"})
        try:
            assert ready.wait(5)
            deletion = pool.submit(TestClient(app).delete, f"/api/projects/{PID}")
            removed.wait(0.25)
        finally:
            release.set()
        save.result(timeout=5)
        response = deletion.result(timeout=5)
    assert response.status_code == 200, response.text
    assert not metadata_path(PID).parent.exists()
