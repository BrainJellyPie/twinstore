"""Rejected run starts cannot leave a layout running or an unqueued pending job."""

import pytest

from store_emulator.application import simulation
from store_emulator.application.storage.setups import metadata_path, read_setup
from tests.server.test_simulation_image_snapshot import running
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("engine", ["rule_based", "vlm_glance"])
@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("after_write", [False, True])
def test_pending_registration_failure_rolls_back_start(running, monkeypatch, engine, preview, after_write):
    client, submit = running
    before = read_setup(PID, SID)
    original = simulation.write_status

    def fail(pid, rid, status, *args, **kwargs):
        if status == "pending":
            if after_write:
                original(pid, rid, status, *args, **kwargs)
            raise OSError("offline pending registration failure")
        return original(pid, rid, status, *args, **kwargs)

    monkeypatch.setattr(simulation, "write_status", fail)
    body = {"setup_id": SID, "engine_type": engine, "preview": preview, "run_id": "run_failed_start"}
    response = client.post(f"/api/projects/{PID}/runs", json=body)
    assert response.status_code == 500, response.text
    submit.assert_not_called()
    assert read_setup(PID, SID) == before, "rejected start changed the source layout"
    assert not (metadata_path(PID).parent / "runs/run_failed_start").exists()
    monkeypatch.setattr(simulation, "write_status", original)
    response = client.post(f"/api/projects/{PID}/runs", json=body)
    assert response.status_code == 200, response.text
    submit.assert_called_once()


@pytest.mark.parametrize("engine", ["rule_based", "vlm_glance"])
@pytest.mark.parametrize("after_write", [False, True])
def test_running_layout_write_failure_rolls_back_start(running, monkeypatch, engine, after_write):
    client, submit = running
    before = read_setup(PID, SID)
    original = simulation.write_setup

    def fail(pid, sid, data):
        if data["status"] == "running":
            if after_write:
                original(pid, sid, data)
            raise OSError("offline running-state failure")
        return original(pid, sid, data)

    monkeypatch.setattr(simulation, "write_setup", fail)
    body = {"setup_id": SID, "engine_type": engine, "run_id": "run_failed_start"}
    response = client.post(f"/api/projects/{PID}/runs", json=body)
    assert response.status_code == 500, response.text
    submit.assert_not_called()
    assert read_setup(PID, SID) == before
    assert not (metadata_path(PID).parent / "runs/run_failed_start").exists()
    monkeypatch.setattr(simulation, "write_setup", original)
    response = client.post(f"/api/projects/{PID}/runs", json=body)
    assert response.status_code == 200, response.text
    submit.assert_called_once()
