"""Editor saves and simulation state changes must not overwrite one another."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import setups, simulation
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.persona import Persona
from store_emulator.engine.layout_gen import generate_store

PID, SID = "proj_race", "setup_race"


@pytest.fixture
def layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = generate_store("station_kiosk")
    person = Persona(id="p", identity="shopper", age_group="20s", gender="Female",
                     description="Offline race test", intent="snack", purpose="snack")
    write_json(metadata_path(PID), {"name": "Race test", "currency": "USD"})
    write_json(personas_path(PID), [person.model_dump(mode="json")])
    write_json(setup_path(PID, SID), {"id": SID, "name": "Original", "status": "draft",
                                    "parentId": "setup_root", "store": store.model_dump(mode="json")})


def _edit(kind):
    if kind == "operations":
        return setups.save_layout_operations(PID, SID, OperationsConfig(stock_per_facing=31))
    payload = {kind: "Edited"}
    if kind == "store":
        payload = {"store": {**read_setup(PID, SID)["store"], "name": "Edited store"}}
    return setups.save_setup_with_lock(PID, SID, payload)


def _overlap_editor(monkeypatch, kind, action):
    ready, release, state_written = Event(), Event(), Event()
    editor_write, state_write = setups.write_setup, simulation.write_setup

    def paused_editor(pid, sid, data):
        ready.set()
        assert release.wait(5), "the editor save was not released"
        editor_write(pid, sid, data)

    def observed_state_write(pid, sid, data):
        state_write(pid, sid, data)
        state_written.set()

    monkeypatch.setattr(setups, "write_setup", paused_editor)
    monkeypatch.setattr(simulation, "write_setup", observed_state_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        editor = pool.submit(_edit, kind)
        try:
            assert ready.wait(5), "the editor did not reach its protected write"
            worker = pool.submit(action)
            # An unprotected state write finishes before the held editor save,
            # which then overwrites it. A protected write waits for release.
            if state_written.wait(0.3):
                worker.result(timeout=10)
        finally:
            release.set()
        editor.result(timeout=5)
        return worker.result(timeout=10)


def _assert_edit_kept(saved, kind):
    if kind == "operations":
        assert saved["operations"]["stock_per_facing"] == 31
    elif kind == "store":
        assert saved["store"]["name"] == "Edited store"
    else:
        assert saved[kind] == "Edited"


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("kind", ["name", "store", "operations"])
def test_start_keeps_the_saved_input_snapshot_and_running_state(layout, monkeypatch, preview, kind):
    prepared = _overlap_editor(monkeypatch, kind, lambda: simulation.prepare_simulation(PID, SID, "run_start", preview=preview))
    saved = read_setup(PID, SID)
    _assert_edit_kept(saved, kind)
    assert saved["status"] == ("draft" if preview else "running")
    assert simulation.get_run_status(PID, "run_start")["status"] == "pending"
    assert prepared[1].name == saved["store"]["name"]


@pytest.mark.parametrize("succeeds", [False, True])
@pytest.mark.parametrize("kind", ["name", "memo", "operations"])
def test_finishing_a_run_keeps_editor_changes_and_its_terminal_state(layout, monkeypatch, succeeds, kind):
    rid, store, personas, address, profile, _ = simulation.prepare_simulation(PID, SID, "run_finish")
    if not succeeds:
        def fail(*args, **kwargs):
            raise RuntimeError("offline test failure")
        monkeypatch.setattr(simulation, "run_shoppers", fail)
    _overlap_editor(monkeypatch, kind, lambda: simulation.run_simulation_background(
        PID, rid, SID, store, personas, SimulationConfig(engine_type=EngineType.RULE_BASED), address, profile,
    ))
    saved = read_setup(PID, SID)
    _assert_edit_kept(saved, kind)
    assert simulation.get_run_status(PID, rid)["status"] == ("completed" if succeeds else "failed")
    assert saved["status"] == ("locked" if succeeds else "draft")
    assert saved.get("runId") == (rid if succeeds else None)


@pytest.mark.parametrize("phase", ["start", "success", "failure"])
def test_operations_saved_during_a_state_write_are_not_lost(layout, monkeypatch, phase):
    if phase == "start":
        def action():
            return simulation.prepare_simulation(PID, SID, "run_reverse")
    else:
        rid, store, personas, address, profile, _ = simulation.prepare_simulation(PID, SID, "run_reverse")
        if phase == "failure":
            def fail(*args, **kwargs):
                raise RuntimeError("offline test failure")
            monkeypatch.setattr(simulation, "run_shoppers", fail)

        def action():
            return simulation.run_simulation_background(
                PID, rid, SID, store, personas, SimulationConfig(engine_type=EngineType.RULE_BASED), address, profile,
            )

    ready, release, edit_written = Event(), Event(), Event()
    original_state_write, original_editor_write = simulation.write_setup, setups.write_setup

    def paused_state_write(pid, sid, data):
        ready.set()
        assert release.wait(5)
        original_state_write(pid, sid, data)

    def observed_editor_write(pid, sid, data):
        original_editor_write(pid, sid, data)
        edit_written.set()

    monkeypatch.setattr(simulation, "write_setup", paused_state_write)
    monkeypatch.setattr(setups, "write_setup", observed_editor_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(action)
        try:
            assert ready.wait(5)
            editor = pool.submit(_edit, "operations")
            if edit_written.wait(0.3):
                editor.result(timeout=5)
        finally:
            release.set()
        worker.result(timeout=10)
        editor.result(timeout=5)
    saved = read_setup(PID, SID)
    assert saved["operations"]["stock_per_facing"] == 31
    assert saved["status"] == {"start": "running", "success": "locked", "failure": "draft"}[phase]


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("same_layout", [False, True])
def test_api_rejects_a_busy_layout_without_starting_a_job_and_keeps_locks_isolated(layout, monkeypatch, preview, same_layout):
    from store_emulator.application.async_executor import executor
    from store_emulator.server.main import app

    def immediate_lock(path, timeout):
        return FileLock(path, timeout=0)

    submit = Mock()
    monkeypatch.setattr(simulation, "FileLock", immediate_lock)
    monkeypatch.setattr(executor, "submit", submit)
    target = (PID, SID) if same_layout else ("proj_other", "setup_other")
    with FileLock(str(setups.setup_lock_path(*target)), timeout=0):
        response = TestClient(app).post(f"/api/projects/{PID}/runs", json={
            "setup_id": SID, "run_id": "run_busy", "engine_type": "rule_based", "preview": preview,
        })
    assert response.status_code == (503 if same_layout else 200), response.text
    assert submit.call_count == int(not same_layout)
    assert read_setup(PID, SID)["status"] == ("draft" if preview or same_layout else "running")
    if same_layout:
        assert "another request is modifying" in response.json()["detail"]
        assert not (metadata_path(PID).parent / "runs" / "run_busy" / "status.json").exists()
