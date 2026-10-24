"""Worker rejection cannot lock a layout or run a simulation after deletion."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import BrokenThreadPool
from unittest.mock import Mock

import pytest

from store_emulator.application import projects, simulation
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, read_setup, setup_path
from store_emulator.server.routes import simulate
from tests.server.test_simulation_image_snapshot import running
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("engine", ["rule_based", "vlm_glance"])
@pytest.mark.parametrize("preview, initial_status", [(False, "draft"), (True, "draft"), (True, "locked")])
@pytest.mark.parametrize("error", [RuntimeError("cannot schedule new futures after shutdown"),
                                  BrokenThreadPool("offline worker initialization failure")])
def test_rejected_run_records_failure_and_releases_only_its_layout(running, monkeypatch, engine, preview, initial_status, error):
    client, submit = running
    before = read_setup(PID, SID)
    before.update(status=initial_status, memo="Keep this note")
    if initial_status == "locked":
        before["runId"] = "run_previous"
    write_json(setup_path(PID, SID), before)
    submit.side_effect = error
    body = {"setup_id": SID, "engine_type": engine, "preview": preview, "run_id": "run_rejected"}
    first = client.post(f"/api/projects/{PID}/runs", json=body)
    saved = read_setup(PID, SID)
    assert saved["status"] == initial_status, saved
    assert saved["memo"] == before["memo"] and saved["store"] == before["store"]
    assert saved.get("runId") == before.get("runId")
    assert first.status_code == 503, first.text
    status = simulation.get_run_status(PID, "run_rejected")
    assert status["status"] == "failed" and status["preview"] == preview
    assert "could not start" in status["error"].lower()
    submit.side_effect = None
    second = client.post(f"/api/projects/{PID}/runs", json={**body, "run_id": "run_retry"})
    assert second.status_code == 200, second.text
    assert submit.call_count == 2


@pytest.mark.parametrize("preview", [False, True])
def test_run_queued_before_start_failure_cannot_resurrect_deleted_project(running, monkeypatch, preview):
    client, _ = running
    work = Mock(side_effect=AssertionError("A rejected run must not start"))
    monkeypatch.setattr(simulation, "run_simulation_background", work)
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(simulate, "executor", pool)
        with monkeypatch.context() as failure:
            failure.setattr(pool, "_adjust_thread_count", Mock(side_effect=RuntimeError("can't start new thread")))
            response = client.post(f"/api/projects/{PID}/runs", json={
                "setup_id": SID, "engine_type": "rule_based", "preview": preview, "run_id": "run_rejected"})
        assert response.status_code == 503, response.text
        projects.delete_project(PID)
        pool.submit(lambda: None).result(timeout=5)
    work.assert_not_called()
    assert not metadata_path(PID).parent.exists()
