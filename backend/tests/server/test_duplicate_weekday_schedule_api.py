"""Conflicting schedules cannot create projects, replace layouts or run paid generation."""

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import generation_async, projects
from store_emulator.application.storage.generations import init_generation, read_status
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.server.main import app
from tests.engine.test_duplicate_weekday_schedules import duplicate_rows
from tests.server.test_project_templates import _meta, client
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("kind", ["same", "split", "closed"])
@pytest.mark.parametrize("with_layout", [False, True])
def test_wizard_rejects_duplicate_days_before_project_creation(client, kind, with_layout):
    api, generation = client
    meta = {**_meta(), "weekly_schedule": duplicate_rows(1, kind)}
    if with_layout:
        meta["layout"] = {"template_id": "station_kiosk"}
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps(meta)})
    assert response.status_code == 422 and "at most once" in response.text
    assert api.get("/api/projects").json() == before
    generation.assert_not_called()


@pytest.mark.parametrize("kind", ["same", "split", "closed"])
def test_layout_edit_rejects_conflicting_schedule_and_preserves_saved_layout(layout, kind):
    before = setup_path(PID, SID).read_bytes()
    store = {**read_setup(PID, SID)["store"], "weekly_schedule": duplicate_rows(7, kind)}
    response = TestClient(app).put(f"/api/projects/{PID}/setups/{SID}", json={"setup": {"store": store}})
    assert response.status_code == 422, response.text
    assert setup_path(PID, SID).read_bytes() == before


def test_direct_project_creation_rejects_invalid_schedule_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generation = Mock()
    monkeypatch.setattr(projects, "start_persona_generation", generation)
    with pytest.raises(ValueError, match="at most once"):
        projects.create_project_without_layout(config=SimulationConfig(), name="test", description="", store_type="shop",
            address="offline", customer_profile="offline", supplemental_bytes=None,
            weekly_schedule=[DaySchedule.model_validate(row) for row in duplicate_rows(1, "same")])
    assert not list(tmp_path.rglob("metadata.json"))
    generation.assert_not_called()


def test_old_metadata_fails_background_generation_before_model_or_supplemental_calls(layout, monkeypatch):
    meta = {**read_json(metadata_path(PID)), "weekly_schedule": duplicate_rows(2, "closed")}
    write_json(metadata_path(PID), meta)
    before = personas_path(PID).read_bytes()
    model = Mock(side_effect=AssertionError("Invalid schedules cannot start the model"))
    monkeypatch.setattr(generation_async, "assistive_client", model)
    gid = init_generation(PID, SID, "persona")
    generation_async._run_persona_background(SimulationConfig(), PID, SID, gid, "",
                                            supplemental_bytes=b"a,b\n1,2", supplemental_filename="data.csv")
    status = read_status(PID, gid)
    assert status["status"] == "failed" and "at most once" in status["error"]
    assert personas_path(PID).read_bytes() == before
    assert read_json(metadata_path(PID)) == meta
    model.assert_not_called()
