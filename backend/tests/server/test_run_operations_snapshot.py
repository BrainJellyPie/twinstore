"""A run captures saved operating settings in the same transaction as its layout."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import setups, simulation
from store_emulator.application.async_executor import executor
from store_emulator.domain.operations import OperationsConfig
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("clear", [False, True])
@pytest.mark.parametrize("mode", ["inherit", "shared", "alone", "override"])
def test_run_waiting_for_an_accepted_operations_save_uses_that_save(layout, monkeypatch, preview, clear, mode):
    old = OperationsConfig(stock_per_facing=5)
    changed = None if clear else OperationsConfig(stock_per_facing=33, patience_sec=31.25)
    override = OperationsConfig(stock_per_facing=77)
    setups.save_layout_operations(PID, SID, old)
    ready, release, run_waiting = Event(), Event(), Event()
    original_write = setups.write_setup

    def paused_write(*args):
        ready.set()
        assert release.wait(5)
        original_write(*args)

    def observed_lock(path, timeout):
        run_waiting.set()
        return FileLock(path, timeout=timeout)

    monkeypatch.setattr(setups, "write_setup", paused_write)
    monkeypatch.setattr(simulation, "FileLock", observed_lock)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    extra = {}
    if mode in ("shared", "alone"):
        extra["shared_store"] = mode == "shared"
    elif mode == "override":
        extra["operations"] = override.model_dump(mode="json")
    with ThreadPoolExecutor(max_workers=2) as pool:
        saving = pool.submit(setups.save_layout_operations, PID, SID, changed)
        try:
            assert ready.wait(5)
            starting = pool.submit(TestClient(app).post, f"/api/projects/{PID}/runs", json={
                "setup_id": SID, "run_id": "run_settings", "engine_type": "rule_based", "preview": preview, **extra,
            })
            assert run_waiting.wait(5)
        finally:
            release.set()
        saving.result(timeout=5)
        response = starting.result(timeout=5)
    assert response.status_code == 200, response.text
    submit.assert_called_once()
    expected = None if mode == "alone" else override if mode == "override" else changed
    if mode == "shared" and expected is None:
        expected = OperationsConfig()
    assert submit.call_args.args[9].operations == expected
    assert setups.layout_operations(PID, SID) == changed


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("clear", [False, True])
def test_a_later_operations_save_does_not_change_the_runs_captured_settings(layout, monkeypatch, preview, clear):
    old = OperationsConfig(stock_per_facing=5, patience_sec=31.25)
    changed = None if clear else OperationsConfig(stock_per_facing=33)
    setups.save_layout_operations(PID, SID, old)
    ready, release, edit_waiting = Event(), Event(), Event()
    original_load = simulation._load_simulation_inputs

    def paused_load(*args):
        captured = original_load(*args)
        ready.set()
        assert release.wait(5)
        return captured

    def observed_lock(path, timeout):
        edit_waiting.set()
        return FileLock(path, timeout=timeout)

    monkeypatch.setattr(simulation, "_load_simulation_inputs", paused_load)
    monkeypatch.setattr(setups, "FileLock", observed_lock)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        starting = pool.submit(TestClient(app).post, f"/api/projects/{PID}/runs", json={
            "setup_id": SID, "run_id": "run_first", "engine_type": "rule_based", "preview": preview,
        })
        try:
            assert ready.wait(5)
            saving = pool.submit(setups.save_layout_operations, PID, SID, changed)
            assert edit_waiting.wait(5)
        finally:
            release.set()
        response = starting.result(timeout=5)
        saving.result(timeout=5)
    assert response.status_code == 200, response.text
    submit.assert_called_once()
    assert submit.call_args.args[9].operations == old
    assert setups.layout_operations(PID, SID) == changed
