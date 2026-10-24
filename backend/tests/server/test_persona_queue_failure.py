"""A customer job that cannot start must not reserve the project indefinitely."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import BrokenThreadPool
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import generation_async, projects
from store_emulator.application.storage.generations import find_active_generation, list_generations
from store_emulator.application.storage.setups import metadata_path, personas_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("error", [RuntimeError("cannot schedule new futures after shutdown"),
                                  BrokenThreadPool("offline worker initialization failure")])
@pytest.mark.parametrize("has_upload", [False, True])
def test_rejected_customer_job_is_failed_and_retryable(layout, monkeypatch, error, has_upload):
    upload = b"timestamp,receipt_id\n2026-10-19T09:00:00,001\n"
    if has_upload:
        generation_async._keep_upload(PID, upload, "customers.csv")
    before = personas_path(PID).read_bytes()
    rejected = Mock(side_effect=error)
    monkeypatch.setattr(generation_async.executor, "submit", rejected)
    client = TestClient(app, raise_server_exceptions=False)
    first = client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
    jobs = list_generations(PID)
    assert len(jobs) == 1 and jobs[0]["status"] == "failed", jobs
    assert first.status_code == 503, first.text
    assert "could not start" in first.json()["detail"].lower()
    assert find_active_generation(PID) is None
    assert personas_path(PID).read_bytes() == before

    accepted = Mock()
    monkeypatch.setattr(generation_async.executor, "submit", accepted)
    second = client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
    assert second.status_code == 200, second.text
    assert second.json()["gen_id"] != jobs[0]["gen_id"]
    accepted.assert_called_once()
    assert accepted.call_args.kwargs["supplemental_bytes"] == (upload if has_upload else None)
    assert sorted(job["status"] for job in list_generations(PID)) == ["failed", "pending"]


@pytest.mark.parametrize("after_failure", ["keep", "delete", "status_write_failed"])
def test_a_job_queued_before_worker_start_failure_never_runs_later(layout, monkeypatch, after_failure):
    before = personas_path(PID).read_bytes()
    model = Mock(side_effect=AssertionError("A rejected job must not call the model"))
    monkeypatch.setattr(generation_async, "assistive_client", model)
    client = TestClient(app, raise_server_exceptions=False)
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(generation_async, "executor", pool)
        # ThreadPoolExecutor queues the work item before trying to start a thread.
        with monkeypatch.context() as failure:
            failure.setattr(pool, "_adjust_thread_count", Mock(side_effect=RuntimeError("can't start new thread")))
            if after_failure == "status_write_failed":
                failure.setattr(generation_async, "write_status", Mock(side_effect=OSError("offline status write failure")))
            response = client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
        assert response.status_code == (500 if after_failure == "status_write_failed" else 503), response.text
        if after_failure == "delete":
            projects.delete_project(PID)
        pool.submit(lambda: None).result(timeout=5)
    model.assert_not_called()
    if after_failure == "delete":
        assert not metadata_path(PID).parent.exists()
    else:
        assert personas_path(PID).read_bytes() == before
        assert [job["status"] for job in list_generations(PID)] == ["pending" if after_failure == "status_write_failed" else "failed"]
