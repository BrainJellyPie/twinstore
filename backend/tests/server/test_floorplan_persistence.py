"""Failed plan imports preserve existing layouts and cannot revive a deleted project."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from store_emulator.application import floorplan, projects
from store_emulator.application.storage import io as storage_io
from store_emulator.application.storage.setups import metadata_path
from store_emulator.server.main import app
from tests.server.test_floorplan_api import PID, _png, client  # noqa: F401


def snapshot():
    root = metadata_path(PID).parent
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("stage", ["directory", "image", "image_write", "setup", "active"])
def test_failed_floorplan_import_preserves_the_previous_layouts(client, monkeypatch, stage):
    payload = _png()
    before = snapshot()
    original_mkdir, original_save, original_json = Path.mkdir, Image.Image.save, floorplan.write_json
    original_bytes, original_replace = Path.write_bytes, storage_io.replace_file

    def mkdir(path, *args, **kwargs):
        if stage == "directory" and path.name == "floorplans":
            raise OSError("Offline plan directory failure")
        return original_mkdir(path, *args, **kwargs)

    def save(image, *args, **kwargs):
        if stage == "image":
            raise OSError("Offline plan image failure")
        return original_save(image, *args, **kwargs)

    def write(path, data):
        if stage == "setup" and path.parent.name == "setups":
            raise OSError("Offline plan layout failure")
        return original_json(path, data)

    def write_bytes(path, data):
        if stage == "image_write" and path.parent.name == "floorplans":
            original_bytes(path, data[:20])
            raise OSError("Offline partial image write failure")
        return original_bytes(path, data)

    def replace(source, destination):
        if stage == "active" and destination.name == "state.json":
            raise OSError("Offline active layout replacement failure")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Image.Image, "save", save)
    monkeypatch.setattr(floorplan, "write_json", write)
    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    monkeypatch.setattr(storage_io, "replace_file", replace)
    response = TestClient(app, raise_server_exceptions=False).post(
        f"/api/projects/{PID}/floorplan", files={"plan": ("plan.png", payload, "image/png")},
        data={"reader": "classic", "model": "none"},
    )
    assert response.status_code == 500, response.text
    assert snapshot() == before


def test_project_deletion_cannot_race_the_retained_plan_image(client, monkeypatch):
    payload = _png()
    ready, release, removed = Event(), Event(), Event()
    original_mkdir, original_remove = Path.mkdir, projects.remove_tree

    def mkdir(path, *args, **kwargs):
        if path.name == "floorplans":
            ready.set()
            assert release.wait(5)
        return original_mkdir(path, *args, **kwargs)

    def remove(path):
        original_remove(path)
        removed.set()

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(projects, "remove_tree", remove)
    with ThreadPoolExecutor(max_workers=2) as pool:
        importing = pool.submit(client.post, f"/api/projects/{PID}/floorplan",
                                files={"plan": ("plan.png", payload, "image/png")},
                                data={"reader": "classic", "model": "none"})
        try:
            assert ready.wait(5)
            deleting = pool.submit(client.delete, f"/api/projects/{PID}")
            removed.wait(.2)
        finally:
            release.set()
        imported, deleted = importing.result(timeout=5), deleting.result(timeout=5)
    assert imported.status_code == deleted.status_code == 200
    assert not metadata_path(PID).parent.exists()


def test_project_deleted_during_plan_reading_returns_not_found(client, monkeypatch):
    original = floorplan.read_plan

    def read(*args):
        result = original(*args)
        projects.delete_project(PID)
        return result

    monkeypatch.setattr(floorplan, "read_plan", read)
    response = TestClient(app, raise_server_exceptions=False).post(
        f"/api/projects/{PID}/floorplan", files={"plan": ("plan.png", _png(), "image/png")},
        data={"reader": "classic", "model": "none"},
    )
    assert response.status_code == 404, response.text
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("occupied", ["layout", "image"])
def test_import_collision_cannot_overwrite_existing_files(client, monkeypatch, occupied):
    original = floorplan.new_setup_data
    sid = "setup_eaf5" if occupied == "layout" else "setup_plan_collision"
    if occupied == "image":
        path = metadata_path(PID).parent / "floorplans" / f"{sid}.png"
        path.parent.mkdir()
        path.write_bytes(b"Retained image")
    before = snapshot()

    def same_identifier(*args, **kwargs):
        setup = original(*args, **kwargs)
        setup["id"] = sid
        return setup

    monkeypatch.setattr(floorplan, "new_setup_data", same_identifier)
    response = client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("plan.png", _png(), "image/png")},
                           data={"reader": "classic", "model": "none"})
    assert response.status_code == 409, response.text
    assert snapshot() == before
