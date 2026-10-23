"""Late neighborhood writes preserve edits committed while work was in progress."""
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from filelock import FileLock
from PIL import Image

from store_emulator.application import town as towns, vision_inputs
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.town import Town, TownArchetype, Venue, VenueCategory
from store_emulator.domain.vision_inputs import StorefrontAppeal

PID = "proj_conflict"
APPEAL = StorefrontAppeal(method="image_stats", signage=5, entrance=5, window=5, upkeep=5, overall=5, attractiveness=1.25)

@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(metadata_path(PID), {"name": "Conflict test"})
    initial = Town(id="original", name="Original", archetype=TownArchetype.RESIDENTIAL, size_m=800, focal_venue_id="store", venues=[
        Venue(id="store", name="Our store", category=VenueCategory.CONVENIENCE, x=400, y=400, is_focal=True),
        Venue(id="rival", name="Rival", category=VenueCategory.SUPERMARKET, x=300, y=300),
    ])
    towns.save_town(PID, initial)
    return initial

def photo():
    data = io.BytesIO()
    Image.new("RGB", (32, 32), "gray").save(data, format="PNG")
    return data.getvalue()

@pytest.mark.parametrize("edit", ["add", "remove_other", "remove_target", "replace", "reprice", "remove_town", "rename"])
def test_storefront_rating_cannot_overwrite_an_intervening_edit(project, monkeypatch, edit):
    path = Path(".data", PID, "town.json")
    committed = []
    def rating(_image):
        if edit == "add":
            towns.add_venue(PID, VenueCategory.CAFE, 200, 200, "Added while rating")
        elif edit in ("remove_other", "remove_target"):
            towns.delete_venue(PID, "rival")
        elif edit == "remove_town":
            path.unlink()
        elif edit == "reprice":
            towns.save_town(PID, project.model_copy(update={"venues": [v.model_copy(update={"attractiveness": 2.5}) if v.id == "store" else v for v in project.venues]}))
        elif edit == "replace":
            towns.save_town(PID, project.model_copy(update={"id": "regenerated", "name": "Replacement town"}))
        else:
            towns.save_town(PID, project.model_copy(update={"name": "Renamed while rating"}))
        committed.append(path.read_bytes() if path.exists() else None)
        return APPEAL
    monkeypatch.setattr(vision_inputs, "classic_appeal", rating)
    with pytest.raises(AppError) as error:
        vision_inputs.rate_storefront(PID, "rival" if edit == "remove_target" else "store", photo(), model="none", config=SimulationConfig())
    assert error.value.status_code == 409
    assert (path.read_bytes() if path.exists() else None) == committed[0]

def test_storefront_rating_saves_normally_when_its_snapshot_is_current(project, monkeypatch):
    monkeypatch.setattr(vision_inputs, "classic_appeal", lambda _image: APPEAL)
    result = vision_inputs.rate_storefront(PID, "store", photo(), model="none", config=SimulationConfig())
    assert result.previous_attractiveness == 1
    assert result.appeal == APPEAL
    assert towns.require_town(PID) == result.town
    assert result.town.get_venue("store").attractiveness == 1.25
    assert project.get_venue("store").attractiveness == 1
    assert result.town.get_venue("rival") == project.get_venue("rival")

@pytest.mark.parametrize("operation", ["add", "delete"])
def test_venue_edits_detect_an_outdated_read(project, monkeypatch, operation):
    replacement = project.model_copy(update={"name": "Concurrent edit"})
    if operation == "add":
        original = towns.place_venue
        def interleave(current, category, x, y, *, name=None):
            towns.save_town(PID, replacement)
            return original(current, category, x, y, name=name)
        monkeypatch.setattr(towns, "place_venue", interleave)
    else:
        original = towns.remove_venue
        def interleave(current, venue_id):
            towns.save_town(PID, replacement)
            return original(current, venue_id)
        monkeypatch.setattr(towns, "remove_venue", interleave)
    with pytest.raises(AppError) as error:
        if operation == "add": towns.add_venue(PID, VenueCategory.CAFE, 100, 100, "Stale addition")
        else: towns.delete_venue(PID, "rival")
    assert error.value.status_code == 409
    assert towns.require_town(PID) == replacement

def test_two_writers_from_the_same_snapshot_have_one_winner_and_can_retry(project, monkeypatch):
    barrier = Barrier(2)
    original = towns.require_town
    def read_together(pid):
        current = original(pid)
        barrier.wait(timeout=5)
        return current
    def add(index):
        try:
            towns.add_venue(PID, VenueCategory.CAFE, 100 + index * 50, 100, f"Cafe {index}")
            return index, 200
        except AppError as error:
            return index, error.status_code
    with monkeypatch.context() as patch:
        patch.setattr(towns, "require_town", read_together)
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(add, range(2)))
    assert sorted(status for _, status in outcomes) == [200, 409]
    failed = next(index for index, status in outcomes if status == 409)
    assert add(failed) == (failed, 200)
    saved = towns.require_town(PID)
    assert {v.name for v in saved.venues} == {"Our store", "Rival", "Cafe 0", "Cafe 1"}

def test_replacement_respects_another_writer_lock(project):
    path = Path(".data", PID, "town.json")
    before = path.read_bytes()
    with FileLock(path.with_suffix(".lock"), timeout=0):
        with pytest.raises(AppError) as error:
            towns.save_town(PID, project.model_copy(update={"name": "Blocked replacement"}))
        assert error.value.status_code == 409
    assert path.read_bytes() == before

def test_project_locks_are_independent(project):
    write_json(metadata_path("proj_second"), {"name": "Second project"})
    with FileLock(Path(".data", PID, "town.lock"), timeout=0):
        towns.save_town("proj_second", project)
    assert towns.require_town("proj_second") == project

def test_failed_disk_write_preserves_the_file_and_releases_the_lock(project, monkeypatch):
    path = Path(".data", PID, "town.json")
    before = path.read_bytes()
    replacement = project.model_copy(update={"name": "Saved after retry"})
    def fail(*_args): raise OSError("Disk full")
    with monkeypatch.context() as patch:
        patch.setattr(towns, "write_json", fail)
        with pytest.raises(OSError, match="Disk full"):
            towns.save_town(PID, replacement)
    assert path.read_bytes() == before
    towns.save_town(PID, replacement)
    assert towns.require_town(PID) == replacement

def test_missing_project_is_not_created_as_a_side_effect(project):
    with pytest.raises(AppError) as error:
        towns.save_town("missing", project)
    assert error.value.status_code == 404
    assert not Path(".data", "missing").exists()


def test_storefront_api_returns_conflict_then_recovers_without_losing_the_new_venue(project, monkeypatch):
    from fastapi.testclient import TestClient
    from store_emulator.server.main import app
    calls = []
    def rating(_image):
        if not calls:
            towns.add_venue(PID, VenueCategory.CAFE, 200, 200, "Keep new cafe")
        calls.append(True)
        return APPEAL
    monkeypatch.setattr(vision_inputs, "classic_appeal", rating)
    with TestClient(app) as client:
        url = f"/api/projects/{PID}/town/venues/store/storefront"
        failed = client.post(url, files={"photo": ("front.png", photo(), "image/png")}, data={"model": "none"})
        assert failed.status_code == 409 and "Neighborhood changed" in failed.json()["detail"]
        current = client.get(f"/api/projects/{PID}/town").json()
        assert any(v["name"] == "Keep new cafe" for v in current["venues"])
        retry = client.post(url, files={"photo": ("front.png", photo(), "image/png")}, data={"model": "none"})
        assert retry.status_code == 200
        assert any(v["name"] == "Keep new cafe" for v in retry.json()["town"]["venues"])
        assert retry.json()["previous_attractiveness"] == 1
        assert client.get(f"/api/projects/{PID}/town").json() == retry.json()["town"]


def _hold_town_lock(path, ready, release):
    with FileLock(path, timeout=2):
        ready.set()
        release.wait(timeout=15)


def test_lock_blocks_a_writer_in_another_process(project):
    from multiprocessing import get_context
    context = get_context("spawn")
    ready, release = context.Event(), context.Event()
    path = Path(".data", PID, "town.lock").resolve()
    worker = context.Process(target=_hold_town_lock, args=(str(path), ready, release))
    worker.start()
    try:
        assert ready.wait(timeout=10)
        with pytest.raises(AppError) as error:
            towns.add_venue(PID, VenueCategory.CAFE, 100, 100, "Blocked cafe")
        assert error.value.status_code == 409
        assert towns.require_town(PID) == project
    finally:
        release.set()
        worker.join(timeout=10)
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
    assert worker.exitcode == 0
    towns.add_venue(PID, VenueCategory.CAFE, 100, 100, "Cafe after release")
    assert any(v.name == "Cafe after release" for v in towns.require_town(PID).venues)
