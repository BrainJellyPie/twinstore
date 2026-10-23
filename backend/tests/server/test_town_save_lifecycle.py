"""Neighborhood commits share the project's deletion and study-snapshot boundary."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import projects, setups, town as towns, town_synergy
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.town import Town, TownArchetype, Venue, VenueCategory
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def neighborhood(layout):
    town = Town(id="town", name="Before edit", archetype=TownArchetype.RESIDENTIAL, size_m=200,
                focal_venue_id="store", venues=[
                    Venue(id="store", name="Store", category=VenueCategory.CONVENIENCE, x=100, y=100, setup_id=SID),
                    Venue(id="cafe", name="Cafe", category=VenueCategory.CAFE, x=110, y=100),
                ])
    write_json(metadata_path(PID).parent / "town.json", town.model_dump(mode="json"))
    return TestClient(app), town


@pytest.mark.parametrize("operation", ["save", "generate", "import", "add", "remove"])
@pytest.mark.parametrize("save_first", [False, True])
def test_neighborhood_commit_and_deletion_cannot_resurrect_project(neighborhood, monkeypatch, operation, save_first):
    client, town = neighborhood
    url = f"/api/projects/{PID}/town"
    monkeypatch.setattr(towns, "fetch_overpass", lambda *args, **kwargs: {})
    monkeypatch.setattr(towns, "town_from_overpass", lambda *args, **kwargs: town)

    def save():
        if operation == "save":
            return client.put(url, json={**town.model_dump(mode="json"), "name": "Edited"})
        if operation == "generate":
            return client.post(f"{url}/generate", json={"size_m": 200, "density": 0.2})
        if operation == "import":
            return client.post(f"{url}/import-osm", json={"lat": 37, "lon": 127, "radius_m": 200})
        if operation == "add":
            return client.post(f"{url}/venues", json={"category": "cafe", "x": 120, "y": 120})
        return client.delete(f"{url}/venues/cafe")

    delete = lambda: client.delete(f"/api/projects/{PID}")
    if save_first:
        saved, removed = overlap(monkeypatch, towns, "write_json", save, delete)
    else:
        removed, saved = overlap(monkeypatch, projects, "remove_tree", delete, save)
    assert saved.status_code == (200 if save_first else 404), saved.text
    assert removed.status_code == 200, removed.text
    assert not metadata_path(PID).parent.exists()


def test_study_waits_for_an_accepted_neighborhood_save(neighborhood, monkeypatch):
    client, town = neighborhood
    monkeypatch.setattr(town_synergy, "ensure_resolvable", lambda *args: None)
    monkeypatch.setattr(town_synergy, "with_vision_default", lambda config, model: config)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    saved, started = overlap(monkeypatch, towns, "write_json",
        lambda: client.put(f"/api/projects/{PID}/town", json={**town.model_dump(mode="json"), "name": "Edited"}),
        lambda: client.post(f"/api/projects/{PID}/town/venues/cafe/synergy-vlm", json={"setup_id": SID}))
    assert saved.status_code == started.status_code == 200
    submit.assert_called_once()
    assert submit.call_args.args[3].name == "Edited"


def test_busy_project_does_not_overwrite_neighborhood(neighborhood, monkeypatch):
    client, town = neighborhood
    path = metadata_path(PID).parent / "town.json"
    before = path.read_bytes()
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    lock = setups.setup_lock_path(PID, "tree").with_name(".setup-tree.lock")
    with FileLock(lock, timeout=0):
        response = client.put(f"/api/projects/{PID}/town", json={**town.model_dump(mode="json"), "name": "Blocked"})
    assert response.status_code == 503, response.text
    assert path.read_bytes() == before
