"""Terminal run polls must follow the layout state change they tell the UI to fetch."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import simulation
from store_emulator.application.storage.setups import read_setup
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("succeeds", [False, True])
def test_terminal_status_is_not_visible_while_layout_finalization_is_pending(layout, monkeypatch, succeeds):
    rid, store, people, address, profile, _ = simulation.prepare_simulation(PID, SID, "run_terminal")
    if not succeeds:
        async def fail(*args, **kwargs):
            raise RuntimeError("offline simulation failure")
        monkeypatch.setattr(simulation, "run_simulation", fail)
    entered, release = Event(), Event()
    original = simulation.write_setup

    def paused(pid, sid, data):
        entered.set()
        assert release.wait(5)
        return original(pid, sid, data)

    monkeypatch.setattr(simulation, "write_setup", paused)
    client = TestClient(app, raise_server_exceptions=False)
    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(simulation.run_simulation_background, PID, rid, SID, store, people,
                             SimulationConfig(engine_type=EngineType.RULE_BASED), address, profile)
        try:
            assert entered.wait(5)
            status = client.get(f"/api/projects/{PID}/runs/{rid}/status")
            assert status.status_code == 200, status.text
            assert read_setup(PID, SID)["status"] == "running"
            assert status.json()["status"] == "running", "polling stopped before the layout changed"
        finally:
            release.set()
        worker.result(timeout=5)
    assert simulation.get_run_status(PID, rid)["status"] == ("completed" if succeeds else "failed")
    saved = read_setup(PID, SID)
    assert saved["status"] == ("locked" if succeeds else "draft")
    assert saved.get("runId") == (rid if succeeds else None)


@pytest.mark.parametrize("succeeds", [False, True])
def test_preview_terminal_status_leaves_the_source_layout_unchanged(layout, monkeypatch, succeeds):
    before = read_setup(PID, SID)
    rid, store, people, address, profile, _ = simulation.prepare_simulation(PID, SID, "run_preview", preview=True)
    if not succeeds:
        async def fail(*args, **kwargs):
            raise RuntimeError("offline preview failure")
        monkeypatch.setattr(simulation, "run_simulation", fail)
    simulation.run_simulation_background(PID, rid, SID, store, people,
        SimulationConfig(engine_type=EngineType.RULE_BASED), address, profile, simulation.RunOptions(preview=True))
    assert simulation.get_run_status(PID, rid)["status"] == ("completed" if succeeds else "failed")
    assert read_setup(PID, SID) == before


@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("after_write", [False, True])
def test_failed_terminal_publication_does_not_leave_a_draft_locked_by_the_failed_run(
    layout, monkeypatch, preview, after_write,
):
    before = read_setup(PID, SID)
    rid, store, people, address, profile, _ = simulation.prepare_simulation(PID, SID, "run_write_error", preview=preview)
    original = simulation.write_status

    def write(pid, run_id, status, *args, **kwargs):
        if status == "completed":
            if after_write:
                original(pid, run_id, status, *args, **kwargs)
            raise OSError("offline status-write failure")
        return original(pid, run_id, status, *args, **kwargs)

    monkeypatch.setattr(simulation, "write_status", write)
    simulation.run_simulation_background(PID, rid, SID, store, people,
        SimulationConfig(engine_type=EngineType.RULE_BASED), address, profile, simulation.RunOptions(preview=preview))
    assert simulation.get_run_status(PID, rid)["status"] == "failed"
    saved = read_setup(PID, SID)
    assert saved["status"] == "draft" and saved.get("runId") is None
    if preview:
        assert saved == before
