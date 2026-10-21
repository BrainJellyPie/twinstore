"""Deleting a project must not remove files from underneath its active workers."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json

JOB_PATHS = (
    "runs/run_test", "generations/gen_test", "optimizations/opt_test", "captures/cap_test",
    "captures/cap_test/lab/jobs/lab_test", "marketing/experiments/exp_test", "marketing/surveys/srv_test",
    "synergy/syn_test",
)


@pytest.mark.parametrize("job_path", JOB_PATHS)
@pytest.mark.parametrize("state", ["pending", "running"])
def test_project_with_an_active_job_cannot_be_deleted(tmp_path, monkeypatch, job_path, state):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test"})
    write_json(root / job_path / "status.json", {"status": state})
    from store_emulator.server.main import app
    response = TestClient(app).delete("/api/projects/proj_test")
    assert response.status_code == 409
    assert (root / "metadata.json").exists()
    assert (root / job_path / "status.json").exists()


@pytest.mark.parametrize("state", ["completed", "failed", "canceled"])
def test_project_with_only_terminal_jobs_can_be_deleted(tmp_path, monkeypatch, state):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test"})
    for job_path in JOB_PATHS:
        write_json(root / job_path / "status.json", {"status": state})
    from store_emulator.server.main import app
    client = TestClient(app)
    assert client.delete("/api/projects/proj_test").status_code == 200
    assert not root.exists()
    assert client.delete("/api/projects/proj_test").status_code == 404


@pytest.mark.parametrize("invalid", ["{", "[]"])
def test_corrupt_old_job_status_does_not_prevent_project_cleanup(tmp_path, monkeypatch, invalid):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test"})
    path = root / "runs" / "run_bad" / "status.json"
    path.parent.mkdir(parents=True)
    path.write_text(invalid)
    from store_emulator.server.main import app
    assert TestClient(app).delete("/api/projects/proj_test").status_code == 200
    assert not root.exists()
