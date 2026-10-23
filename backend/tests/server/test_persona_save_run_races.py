"""A final run and customer edits agree on the population being locked."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import projects, setups, simulation
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import personas_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


def _new_people():
    return [{**read_json(personas_path(PID))[0], "id": "new_customer", "identity": "Edited customer"}]


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_run_start_waits_for_an_accepted_customer_save(layout, monkeypatch, preview, empty):
    ready, release, attempted_start, started = Event(), Event(), Event(), Event()
    original_write, original_pending = projects.write_json, simulation.write_status
    people = [] if empty else _new_people()

    def paused_people(path, data):
        if path == personas_path(PID):
            ready.set()
            assert release.wait(5)
        original_write(path, data)

    def observed_lock(path, timeout):
        attempted_start.set()
        return FileLock(path, timeout=timeout)

    def observed_pending(pid, rid, status, **extra):
        original_pending(pid, rid, status, **extra)
        started.set()

    monkeypatch.setattr(projects, "write_json", paused_people)
    monkeypatch.setattr(simulation, "FileLock", observed_lock)
    monkeypatch.setattr(simulation, "write_status", observed_pending)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        saving = pool.submit(client.put, f"/api/projects/{PID}/personas", json={"personas": people})
        try:
            assert ready.wait(5)
            starting = pool.submit(client.post, f"/api/projects/{PID}/runs", json={
                "setup_id": SID, "run_id": "run_after_edit", "engine_type": "rule_based", "preview": preview,
            })
            assert attempted_start.wait(5)
            started.wait(0.25)
        finally:
            release.set()
        saved, run = saving.result(timeout=5), starting.result(timeout=5)
    assert saved.status_code == 200, saved.text
    assert run.status_code == (409 if empty else 200), run.text
    assert read_json(personas_path(PID)) == people
    if empty:
        submit.assert_not_called()
    else:
        assert [p.model_dump(mode="json") for p in submit.call_args.args[5]] == people


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_final_run_locks_its_loaded_customers_before_a_later_edit(layout, monkeypatch, preview, empty):
    ready, release, edited = Event(), Event(), Event()
    original_load, original_write = simulation._load_simulation_inputs, projects.write_json
    before = read_json(personas_path(PID))
    people = [] if empty else _new_people()

    def paused_load(*args, **kwargs):
        result = original_load(*args, **kwargs)
        ready.set()
        assert release.wait(5)
        return result

    def observed_people(path, data):
        original_write(path, data)
        if path == personas_path(PID):
            edited.set()

    monkeypatch.setattr(simulation, "_load_simulation_inputs", paused_load)
    monkeypatch.setattr(projects, "write_json", observed_people)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        starting = pool.submit(client.post, f"/api/projects/{PID}/runs", json={
            "setup_id": SID, "run_id": "run_before_edit", "engine_type": "rule_based", "preview": preview,
        })
        try:
            assert ready.wait(5)
            saving = pool.submit(client.put, f"/api/projects/{PID}/personas", json={"personas": people})
            edited.wait(0.25)
        finally:
            release.set()
        run, saved = starting.result(timeout=5), saving.result(timeout=5)
    assert run.status_code == 200, run.text
    assert saved.status_code == (200 if preview else 409), saved.text
    assert read_json(personas_path(PID)) == (people if preview else before)
    assert [p.model_dump(mode="json") for p in submit.call_args.args[5]] == before


@pytest.mark.parametrize("locked", [SID, "setup_unrelated"])
def test_customer_save_returns_retryable_busy_error_without_changing_people(layout, monkeypatch, locked):
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    before = read_json(personas_path(PID))
    people = _new_people()
    with FileLock(setups.setup_lock_path(PID, locked), timeout=0):
        response = TestClient(app).put(f"/api/projects/{PID}/personas", json={"personas": people})
    assert response.status_code == (503 if locked == SID else 200), response.text
    assert read_json(personas_path(PID)) == (before if locked == SID else people)
