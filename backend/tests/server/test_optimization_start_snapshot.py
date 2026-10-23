"""Optimization registration captures committed inputs and excludes project deletion."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import optimize, projects, setups
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup
from store_emulator.domain.operations import OperationsConfig
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def requests(layout, monkeypatch):
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    return TestClient(app), submit


def _overlap(monkeypatch, module, method, first, second):
    ready, release = Event(), Event()
    original = getattr(module, method)

    def paused(*args, **kwargs):
        ready.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, method, paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        try:
            assert ready.wait(5)
            b = pool.submit(second)
            try:
                b.result(timeout=0.2)
            except TimeoutError:
                pass
        finally:
            release.set()
        return a.result(timeout=5), b.result(timeout=5)


@pytest.mark.parametrize("start_first", [False, True])
def test_optimization_registration_cannot_recreate_a_deleted_project(requests, monkeypatch, start_first):
    client, submit = requests

    def start():
        return client.post(f"/api/projects/{PID}/setups/{SID}/optimize", json={})

    def delete():
        return client.delete(f"/api/projects/{PID}")

    if start_first:
        started, deleted = _overlap(monkeypatch, optimize, "_write_status", start, delete)
    else:
        deleted, started = _overlap(monkeypatch, projects, "remove_tree", delete, start)
    assert started.status_code == (200 if start_first else 404), started.text
    assert deleted.status_code == (409 if start_first else 200), deleted.text
    assert submit.call_count == (1 if start_first else 0)
    assert metadata_path(PID).parent.exists() is start_first
    assert len(optimize.list_optimizations(PID)) == (1 if start_first else 0)


@pytest.mark.parametrize("kind", ["layout", "customers", "operations", "clear_operations"])
def test_optimization_waits_for_accepted_input_edits(requests, monkeypatch, kind):
    client, submit = requests
    setups.save_layout_operations(PID, SID, OperationsConfig(stock_per_facing=5))
    store = {**read_setup(PID, SID)["store"], "name": "Edited store"}
    people = [{**read_json(personas_path(PID))[0], "id": "edited_customer"}]
    operations = None if kind == "clear_operations" else OperationsConfig(stock_per_facing=33)

    def edit():
        if kind == "layout":
            return setups.save_setup_with_lock(PID, SID, {"store": store})
        if kind == "customers":
            return projects.save_project_personas(PID, people)
        return setups.save_layout_operations(PID, SID, operations)

    _, started = _overlap(monkeypatch, projects if kind == "customers" else setups,
        "write_json" if kind == "customers" else "write_setup", edit,
        lambda: client.post(f"/api/projects/{PID}/setups/{SID}/optimize", json={}),
    )
    assert started.status_code == 200, started.text
    submit.assert_called_once()
    if kind == "layout":
        assert submit.call_args.args[3].name == "Edited store"
    elif kind == "customers":
        assert [person.id for person in submit.call_args.args[4]] == ["edited_customer"]
    else:
        assert submit.call_args.args[5].operations == operations
        assert started.json()["operations"] == (None if operations is None else operations.model_dump(mode="json"))


@pytest.mark.parametrize("mode", ["inherit", "shared", "alone", "override"])
@pytest.mark.parametrize("saved", [False, True])
def test_optimization_keeps_operating_settings_precedence(requests, mode, saved):
    client, submit = requests
    stored = OperationsConfig(stock_per_facing=5) if saved else None
    override = OperationsConfig(stock_per_facing=77)
    setups.save_layout_operations(PID, SID, stored)
    body = {}
    if mode in ("shared", "alone"):
        body["shared_store"] = mode == "shared"
    if mode in ("override", "alone"):
        body["operations"] = override.model_dump(mode="json")
    started = client.post(f"/api/projects/{PID}/setups/{SID}/optimize", json=body)
    assert started.status_code == 200, started.text
    expected = None if mode == "alone" else override if mode == "override" else stored
    if mode == "shared" and expected is None:
        expected = OperationsConfig()
    assert submit.call_args.args[5].operations == expected


@pytest.mark.parametrize("locked", ["tree", SID, "unrelated"])
def test_busy_optimization_inputs_return_retryable_error_without_a_job(requests, monkeypatch, locked):
    client, submit = requests
    factory = lambda path, timeout: FileLock(path, timeout=0)
    monkeypatch.setattr(setups, "FileLock", factory)
    monkeypatch.setattr(optimize, "FileLock", factory, raising=False)
    path = setups.setup_lock_path(PID, locked)
    if locked == "tree":
        path = path.with_name(".setup-tree.lock")
    with FileLock(path, timeout=0):
        response = client.post(f"/api/projects/{PID}/setups/{SID}/optimize", json={})
    expected = 200 if locked == "unrelated" else 503
    assert response.status_code == expected, response.text
    assert submit.call_count == (1 if expected == 200 else 0)
    assert len(optimize.list_optimizations(PID)) == (1 if expected == 200 else 0)
