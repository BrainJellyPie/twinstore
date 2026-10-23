"""A synergy job accepts one committed layout/customer snapshot before deletion can proceed."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import projects, setups, town_synergy
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.domain.town import Town, TownArchetype, Venue, VenueCategory
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture(params=[False, True])
def study(layout, monkeypatch, request):
    write_json(setup_path(PID, SID), {**read_setup(PID, SID), "runId": None, "memo": "",
                                     "created_at": "2026-10-23T00:00:00+00:00"})
    town = Town(id="town", name="Town", archetype=TownArchetype.RESIDENTIAL, size_m=200,
                focal_venue_id="store", venues=[
                    Venue(id="store", name="Store", category=VenueCategory.CONVENIENCE, x=100, y=100, setup_id=SID),
                    Venue(id="cafe", name="Cafe", category=VenueCategory.CAFE, x=110, y=100),
                ])
    write_json(metadata_path(PID).parent / "town.json", town.model_dump(mode="json"))
    monkeypatch.setattr(town_synergy, "ensure_resolvable", lambda *args: None)
    monkeypatch.setattr(town_synergy, "with_vision_default", lambda config, model: config)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    client = TestClient(app)

    def start():
        return client.post(f"/api/projects/{PID}/town/venues/cafe/synergy-vlm",
                           json={"setup_id": SID} if request.param else {})

    return client, submit, start


@pytest.mark.parametrize("start_first", [False, True])
def test_start_and_delete_cannot_leave_orphaned_or_erased_accepted_jobs(study, monkeypatch, start_first):
    client, submit, start = study
    delete = lambda: client.delete(f"/api/projects/{PID}")
    if start_first:
        started, removed = overlap(monkeypatch, town_synergy, "_write_status", start, delete)
    else:
        removed, started = overlap(monkeypatch, projects, "remove_tree", delete, start)
    assert started.status_code == (200 if start_first else 404), started.text
    assert removed.status_code == (409 if start_first else 200), removed.text
    assert submit.call_count == (1 if start_first else 0)
    assert metadata_path(PID).parent.exists() is start_first
    assert len(town_synergy.list_synergy_jobs(PID)) == (1 if start_first else 0)


@pytest.mark.parametrize("kind", ["layout", "customers"])
def test_study_waits_for_an_already_accepted_input_save(study, monkeypatch, kind):
    client, submit, start = study

    def save():
        if kind == "customers":
            people = [{**read_json(personas_path(PID))[0], "id": "edited_customer"}]
            return client.put(f"/api/projects/{PID}/personas", json={"personas": people})
        store = {**read_setup(PID, SID)["store"], "name": "Edited store"}
        return client.put(f"/api/projects/{PID}/setups/{SID}", json={"setup": {"store": store}})

    saved, started = overlap(monkeypatch, projects if kind == "customers" else setups,
                             "write_json" if kind == "customers" else "write_setup", save, start)
    assert saved.status_code == started.status_code == 200
    submit.assert_called_once()
    if kind == "customers":
        assert [p.id for p in submit.call_args.args[5]] == ["edited_customer"]
    else:
        assert submit.call_args.args[4].name == "Edited store"


@pytest.mark.parametrize("lock", ["tree", SID])
def test_busy_inputs_return_retryable_errors_without_registering(study, monkeypatch, lock):
    _, submit, start = study
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    path = setups.setup_lock_path(PID, lock)
    if lock == "tree":
        path = path.with_name(".setup-tree.lock")
    with FileLock(path, timeout=0):
        response = start()
    assert response.status_code == 503, response.text
    submit.assert_not_called()
    assert not town_synergy.list_synergy_jobs(PID)
