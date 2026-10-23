"""Active jobs survive premature deletion; interrupted jobs become actionable after restart."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing
from store_emulator.application.storage.io import now_iso, read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.marketing import JobStatus

PID = "proj_lifecycle"


def _save_job(kind, state):
    write_json(metadata_path(PID), {"id": PID, "name": "Lifecycle"})
    job = JobStatus(job_id=f"job_{state}", kind=kind, name="Test", status=state, created_at=now_iso())
    folder = marketing._job_dir(PID, kind, job.job_id)
    write_json(folder / "status.json", job.model_dump(mode="json"))
    write_json(folder / "request.json", {"saved": True})
    return job, folder


@pytest.mark.parametrize("kind", ["experiment", "survey"])
@pytest.mark.parametrize("state", ["pending", "running"])
def test_deleting_active_job_is_rejected(tmp_path, monkeypatch, kind, state):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        job, folder = _save_job(kind, state)
        response = client.delete(f"/api/projects/{PID}/{kind}s/{job.job_id}")
        assert response.status_code == 409
        assert "still" in response.json()["detail"]
        assert read_json(folder / "request.json") == {"saved": True}
        assert client.get(f"/api/projects/{PID}/{kind}s/{job.job_id}").json()["status"] == state


@pytest.mark.parametrize("kind", ["experiment", "survey"])
@pytest.mark.parametrize("state", ["completed", "failed"])
def test_terminal_job_can_be_deleted(tmp_path, monkeypatch, kind, state):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        job, folder = _save_job(kind, state)
        url = f"/api/projects/{PID}/{kind}s/{job.job_id}"
        assert client.delete(url).status_code == 204
        assert not folder.exists()
        assert client.get(url).status_code == 404


def test_startup_recovers_interrupted_jobs_and_preserves_finished_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    jobs = [_save_job(kind, state) for kind in ("experiment", "survey")
            for state in ("pending", "running", "completed", "failed")]
    with TestClient(app) as client:
        for job, folder in jobs:
            saved = read_json(folder / "status.json")
            if job.status in ("pending", "running"):
                assert saved["status"] == "failed"
                assert "restart" in saved["error"] and saved["finished_at"]
                url = f"/api/projects/{PID}/{job.kind}s/{job.job_id}"
                assert client.delete(url).status_code == 204
            else:
                assert saved == job.model_dump(mode="json")
