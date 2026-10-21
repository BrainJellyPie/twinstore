"""Project-wide personas cannot be replaced by competing layout jobs or edits."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import generation_async
from store_emulator.application.setups import get_setup
from store_emulator.application.storage.generations import init_generation, write_status
from store_emulator.application.storage.setups import read_setup, write_setup
from store_emulator.domain.persona import Persona


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    root.mkdir(parents=True)
    (root / "metadata.json").write_text(json.dumps({"name": "Test", "currency": "USD"}))
    persona = Persona(id="p_test", identity="Student", age_group="20s", gender="Female",
                      description="Shops after class", intent="snack", purpose="snack").model_dump(mode="json")
    (root / "personas.json").write_text(json.dumps([persona]))
    for sid in ("setup_a", "setup_b"):
        write_setup("proj_test", sid, {"id": sid, "status": "draft", "runId": None})
    executor = Mock()
    monkeypatch.setattr(generation_async, "executor", executor)
    from store_emulator.server.main import app
    return TestClient(app), root, executor, persona


@pytest.mark.parametrize("status, expected", [("pending", 409), ("running", 409), ("completed", 200), ("failed", 200)])
def test_persona_generation_on_another_layout_respects_project_job_state(project, status, expected):
    client, _, executor, _ = project
    gid = init_generation("proj_test", "setup_a", "persona")
    write_status("proj_test", gid, status)
    response = client.post("/api/projects/proj_test/setups/setup_b/regenerate-persona")
    assert response.status_code == expected
    assert executor.submit.call_count == (1 if expected == 200 else 0)


def test_independent_projects_can_generate_personas_at_the_same_time(project):
    client, root, executor, _ = project
    write_setup("proj_other", "setup_other", {"id": "setup_other", "status": "draft", "runId": None})
    (root.parent / "proj_other" / "metadata.json").write_text(json.dumps({"name": "Other", "currency": "USD"}))
    assert client.post("/api/projects/proj_test/setups/setup_a/regenerate-persona").status_code == 200
    assert client.post("/api/projects/proj_other/setups/setup_other/regenerate-persona").status_code == 200
    assert executor.submit.call_count == 2


def test_running_simulation_blocks_persona_generation_on_another_layout(project):
    client, _, executor, _ = project
    setup = read_setup("proj_test", "setup_a")
    write_setup("proj_test", "setup_a", {**setup, "status": "running"})
    response = client.post("/api/projects/proj_test/setups/setup_b/regenerate-persona")
    assert response.status_code == 409
    executor.submit.assert_not_called()


@pytest.mark.parametrize("status", ["pending", "running"])
def test_manual_edit_does_not_compete_with_persona_generation(project, status):
    client, root, _, persona = project
    gid = init_generation("proj_test", "setup_a", "persona")
    write_status("proj_test", gid, status)
    previous = (root / "personas.json").read_bytes()
    response = client.put("/api/projects/proj_test/personas", json={"personas": [{**persona, "identity": "Changed"}]})
    assert response.status_code == 409
    assert (root / "personas.json").read_bytes() == previous


def test_manual_edit_preserves_personas_during_a_simulation(project):
    client, root, _, persona = project
    setup = read_setup("proj_test", "setup_a")
    write_setup("proj_test", "setup_a", {**setup, "status": "running"})
    previous = (root / "personas.json").read_bytes()
    response = client.put("/api/projects/proj_test/personas", json={"personas": [{**persona, "identity": "Changed"}]})
    assert response.status_code == 409
    assert (root / "personas.json").read_bytes() == previous


@pytest.mark.parametrize("kind, status, ready", [
    ("persona", "pending", False), ("persona", "running", False),
    ("persona", "completed", True), ("layout", "pending", True),
])
def test_layout_readiness_accounts_for_shared_persona_generation(project, kind, status, ready):
    sample = Path(__file__).resolve().parents[2] / "sample_data/proj_67916afd/runs/run_ab0039/input/store.json"
    setup = read_setup("proj_test", "setup_b")
    write_setup("proj_test", "setup_b", {**setup, "store": json.loads(sample.read_text())})
    assert get_setup("proj_test", "setup_b")["readiness"]["ready"] is True
    gid = init_generation("proj_test", "setup_a", kind)
    write_status("proj_test", gid, status)
    readiness = get_setup("proj_test", "setup_b")["readiness"]
    assert readiness["ready"] is ready
    assert ("personas_pending" in readiness["reasons"]) is (not ready)
