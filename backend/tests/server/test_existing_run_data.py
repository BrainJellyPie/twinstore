"""A missing status file does not make an existing run directory safe to overwrite."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import simulation
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, read_setup
from store_emulator.server.main import app
from store_emulator.server.routes import simulate
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("engine", ["rule_based", "vlm_glance"])
@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("artifact", ["output/summary.json", "input/store.json", "input/images/manifest.json", "empty"])
@pytest.mark.parametrize("when", ["before_start", "after_input_load"])
def test_existing_run_data_is_reserved_even_without_status(layout, monkeypatch, engine, preview, artifact, when):
    folder = metadata_path(PID).parent / "runs/run_saved"
    original_files = {}

    def existing_data():
        folder.mkdir(parents=True, exist_ok=True)
        if artifact != "empty":
            write_json(folder / artifact, {"saved_evidence": "must remain byte-identical"})
            original_files[artifact] = (folder / artifact).read_bytes()

    if when == "before_start":
        existing_data()
    else:
        load = simulation._load_simulation_inputs

        def load_then_arrive(*args):
            result = load(*args)
            existing_data()
            return result

        monkeypatch.setattr(simulation, "_load_simulation_inputs", load_then_arrive)
    monkeypatch.setattr(simulate, "ensure_resolvable", lambda config: None)
    submit = Mock()
    monkeypatch.setattr(simulate.executor, "submit", submit)
    response = TestClient(app, raise_server_exceptions=False).post(f"/api/projects/{PID}/runs", json={
        "setup_id": SID, "run_id": "run_saved", "preview": preview, "engine_type": engine,
    })
    assert response.status_code == 409, response.text
    assert "already exists" in response.json()["detail"]
    submit.assert_not_called()
    assert read_setup(PID, SID)["status"] == "draft"
    assert not (folder / "status.json").exists()
    files = {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    assert files == original_files
