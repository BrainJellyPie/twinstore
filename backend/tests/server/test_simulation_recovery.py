"""A restarted server must not advertise interrupted runs as still progressing."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json


@pytest.mark.parametrize("state", ["pending", "running", "completed", "failed"])
def test_server_restart_recovers_only_active_simulations(tmp_path, monkeypatch, state):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server import main
    monkeypatch.setattr(main, "seed_sample_projects", lambda: 0)
    folder = tmp_path / ".data" / "proj_test" / "runs" / "run_test"
    saved = {"status": state, "setup_id": "setup_test", "completed_customers": 7, "total_customers": 12,
             "error": "existing error" if state == "failed" else "", "created_at": "original"}
    write_json(folder / "status.json", saved)
    write_json(folder / "input" / "personas.json", [{"id": "p1"}])

    with TestClient(main.app) as client:
        response = client.get("/api/projects/proj_test/runs/run_test/status")
        assert response.status_code == 200
        status = response.json()
        if state in ("pending", "running"):
            assert status["status"] == "failed"
            assert "restart" in status["error"] and status["finished_at"]
            assert status["completed_customers"] == 7 and status["created_at"] == "original"
        else:
            assert status == saved
        assert read_json(folder / "input" / "personas.json") == [{"id": "p1"}]


@pytest.mark.parametrize("broken", ["{", "[]"])
def test_unreadable_run_status_does_not_prevent_startup_recovery(tmp_path, monkeypatch, broken):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server import main
    monkeypatch.setattr(main, "seed_sample_projects", lambda: 0)
    runs = tmp_path / ".data" / "proj_test" / "runs"
    bad = runs / "run_bad" / "status.json"
    bad.parent.mkdir(parents=True)
    bad.write_text(broken)
    write_json(runs / "run_good" / "status.json", {"status": "running"})
    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/projects/proj_test/runs/run_good/status").json()["status"] == "failed"
    assert bad.read_text() == broken
