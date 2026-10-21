"""Restart recovery makes persisted photo, optimization, and shelf-lab jobs actionable."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.optimize import OptimizationStatus
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.domain.capture import CaptureStatus
from store_emulator.domain.optimize import OptimizeSpec
from store_emulator.domain.shelf_lab import LabJobStatus


@pytest.mark.parametrize("kind", ["capture", "optimization", "lab"])
@pytest.mark.parametrize("state", ["pending", "running", "completed", "failed"])
def test_restart_recovers_background_jobs_and_preserves_finished_results(tmp_path, monkeypatch, kind, state):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server import main
    monkeypatch.setattr(main, "seed_sample_projects", lambda: 0)
    root = tmp_path / ".data" / "proj_test"
    if kind == "capture":
        status = CaptureStatus(capture_id="cap_test", status=state)
        folder = root / "captures" / "cap_test"
        endpoint = "/api/projects/proj_test/captures/cap_test"
    elif kind == "optimization":
        status = OptimizationStatus(job_id="opt_test", setup_id="setup_test", status=state, spec=OptimizeSpec())
        folder = root / "optimizations" / "opt_test"
        endpoint = "/api/projects/proj_test/optimizations/opt_test"
    else:
        status = LabJobStatus(job_id="lab_test", capture_id="cap_test", kind="audit", status=state)
        folder = root / "captures" / "cap_test" / "lab" / "jobs" / "lab_test"
        endpoint = "/api/projects/proj_test/captures/cap_test/lab/jobs/lab_test"
    saved = status.model_dump(mode="json")
    write_json(folder / "status.json", saved)
    (folder / "input.bin").write_bytes(b"original input")

    with TestClient(main.app) as client:
        response = client.get(endpoint)
        assert response.status_code == 200
        current = read_json(folder / "status.json")
        if state in ("pending", "running"):
            assert current["status"] == "failed"
            assert "restart" in current["error"] and current["finished_at"]
        else:
            assert current == saved
        assert (folder / "input.bin").read_bytes() == b"original input"
        if kind == "capture":
            assert client.delete(endpoint).status_code == 204
