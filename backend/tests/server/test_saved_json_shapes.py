"""Syntactically valid but wrong-shaped JSON cannot hide every saved project."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def api(layout):
    write_json(setup_path(PID, SID), {**read_setup(PID, SID), "runId": None, "memo": "",
                                    "created_at": "2026-10-23", "updated_at": "2026-10-23"})
    good = "proj_healthy"
    write_json(metadata_path(good), {"project_id": good, "name": "Healthy", "created_at": "2026-10-23"})
    write_json(personas_path(good), read_json(personas_path(PID)))
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("value", [None, False, 3, "customers", {"unexpected": "object"}])
def test_invalid_customer_container_keeps_projects_open_and_requests_regeneration(api, value):
    path = personas_path(PID)
    write_json(path, value)
    before = path.read_bytes()
    listed = api.get("/api/projects")
    assert listed.status_code == 200, listed.text
    assert {p["name"] for p in listed.json()} >= {"Healthy", "Race test"}
    opened = api.get(f"/api/projects/{PID}")
    assert opened.status_code == 200, opened.text
    assert opened.json()["personas"] == []
    assert "no_personas" in opened.json()["setups"][0]["readiness"]["reasons"]
    assert api.get("/api/projects/proj_healthy").status_code == 200
    assert path.read_bytes() == before


@pytest.mark.parametrize("value", [None, False, 3, "layout", [], ["layout"]])
def test_invalid_layout_container_does_not_hide_healthy_projects_or_layouts(api, value):
    bad_sid = "setup_bad_shape"
    path = setup_path(PID, bad_sid)
    write_json(path, value)
    before = path.read_bytes()
    listed = api.get("/api/projects")
    assert listed.status_code == 200, listed.text
    opened = api.get(f"/api/projects/{PID}")
    assert opened.status_code == 200, opened.text
    assert [s["id"] for s in opened.json()["setups"]] == [SID]
    assert api.get(f"/api/projects/{PID}/setups/{SID}").status_code == 200
    broken = api.get(f"/api/projects/{PID}/setups/{bad_sid}")
    assert broken.status_code == 500
    assert f"{bad_sid}.json" in broken.json()["detail"] and "JSON object" in broken.json()["detail"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("value", [None, False, 17, [], {}])
def test_invalid_metadata_sort_value_cannot_break_other_projects(api, value):
    write_json(metadata_path(PID), {**read_json(metadata_path(PID)), "created_at": value})
    before = metadata_path(PID).read_bytes()
    response = api.get("/api/projects")
    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert metadata_path(PID).read_bytes() == before


def test_valid_customer_and_layout_containers_keep_existing_contents(api):
    people = read_json(personas_path(PID))
    saved = read_setup(PID, SID)
    opened = api.get(f"/api/projects/{PID}")
    assert opened.status_code == 200 and opened.json()["personas"] == people
    assert api.get(f"/api/projects/{PID}/setups/{SID}").json()["store"] == saved["store"]
