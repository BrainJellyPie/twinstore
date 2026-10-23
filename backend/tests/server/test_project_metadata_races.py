"""Accepted project edits survive overlapping saves and cannot undo deletion."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import generation_async, projects, setups
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.engine.generators.traffic_profile import TrafficProfile
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("other", ["edit", "personas", "summary", "traffic", "estimates"])
@pytest.mark.parametrize("edit_first", [False, True])
def test_overlapping_project_writes_preserve_every_accepted_change(layout, monkeypatch, other, edit_first):
    ready, release, second_written = Event(), Event(), Event()
    path = metadata_path(PID)
    original_write = projects.write_json
    client = TestClient(app)
    profile = TrafficProfile(weights={1: {9: 1.0}}, source="uploaded visits")

    async def summary(*args):
        return "Uploaded customer evidence" if other == "summary" else ""

    async def generate(**kwargs):
        if other == "estimates":
            kwargs["estimates"].update({1: 300, 2: 450})
        return []

    monkeypatch.setattr(generation_async, "assistive_client", lambda *a, **k: Mock(max_parallel=None))
    monkeypatch.setattr(generation_async, "summarize_supplemental", summary)
    monkeypatch.setattr(generation_async, "traffic_from_supplemental", lambda *a: profile if other == "traffic" else None)
    monkeypatch.setattr(generation_async, "neighborhood_text", lambda *a: "")
    monkeypatch.setattr(generation_async, "_generate_personas_impl", generate)

    def observed_write(destination, data):
        if destination == path and not ready.is_set():
            ready.set()
            assert release.wait(5)
            original_write(destination, data)
        else:
            original_write(destination, data)
            if destination == path:
                second_written.set()

    monkeypatch.setattr(projects, "write_json", observed_write)
    monkeypatch.setattr(generation_async, "write_json", observed_write)

    def edit():
        response = client.put(f"/api/projects/{PID}/metadata", json={
            "name": "Renamed", "address": "New address", "customer_profile": "New audience",
        })
        assert response.status_code == 200, response.text

    def other_save():
        if other == "edit":
            response = client.put(f"/api/projects/{PID}/metadata", json={"description": "New description"})
            assert response.status_code == 200, response.text
        elif other == "personas":
            response = client.put(f"/api/projects/{PID}/personas", json={"personas": []})
            assert response.status_code == 200, response.text
        else:
            asyncio.run(generation_async._run_async_pipeline(
                config=SimulationConfig(), project_id=PID, meta=read_json(path), schedules=[],
                custom_instruction="", supplemental_bytes=b"offline", supplemental_filename="visits.csv",
            ))

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(edit if edit_first else other_save)
        try:
            assert ready.wait(5)
            second = pool.submit(other_save if edit_first else edit)
            second_written.wait(0.2)
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    saved = read_json(path)
    assert saved["name"] == "Renamed"
    assert saved["address"] == "New address"
    assert saved["customer_profile"] == "New audience"
    assert saved["currency"] == "USD"
    assert saved["updated_at"]
    if other == "edit":
        assert saved["description"] == "New description"
    elif other == "personas":
        assert read_json(personas_path(PID)) == []
    elif other == "summary":
        assert saved["supplemental_summary"] == "Uploaded customer evidence"
    elif other == "traffic":
        assert saved["traffic_profile"] == profile.model_dump(mode="json")
    else:
        assert saved["estimated_daily_visitors"] == {"1": 300, "2": 450}


@pytest.mark.parametrize("delete_first", [False, True])
def test_metadata_save_cannot_resurrect_a_deleted_project(layout, monkeypatch, delete_first):
    ready, release, second_finished = Event(), Event(), Event()
    original_write, original_remove = projects.write_json, projects.remove_tree

    def observed_write(path, data):
        if not delete_first:
            ready.set()
            assert release.wait(5)
        original_write(path, data)
        if delete_first:
            second_finished.set()

    def observed_remove(path):
        if delete_first:
            ready.set()
            assert release.wait(5)
        original_remove(path)
        if not delete_first:
            second_finished.set()

    monkeypatch.setattr(projects, "write_json", observed_write)
    monkeypatch.setattr(projects, "remove_tree", observed_remove)
    client = TestClient(app)

    def edit():
        return client.put(f"/api/projects/{PID}/metadata", json={"name": "Too late"})

    def delete():
        return client.delete(f"/api/projects/{PID}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(delete if delete_first else edit)
        try:
            assert ready.wait(5)
            second = pool.submit(edit if delete_first else delete)
            second_finished.wait(0.2)
        finally:
            release.set()
        results = first.result(timeout=5), second.result(timeout=5)
    deleted, edited = results if delete_first else results[::-1]
    assert deleted.status_code == 200, deleted.text
    assert edited.status_code == (404 if delete_first else 200), edited.text
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("locked", ["tree", "layout", "other_project"])
def test_metadata_save_busy_tree_is_retryable_but_layout_locks_do_not_block_it(layout, monkeypatch, locked):
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    path = setups.setup_lock_path(PID if locked != "other_project" else "proj_other", SID)
    if locked != "layout":
        path = path.with_name(".setup-tree.lock")
    before = read_json(metadata_path(PID))
    with FileLock(path, timeout=0):
        response = TestClient(app).put(f"/api/projects/{PID}/metadata", json={"name": ""})
    assert response.status_code == (503 if locked == "tree" else 200), response.text
    saved = read_json(metadata_path(PID))
    if locked == "tree":
        assert saved == before
    else:
        assert saved["name"] == ""
        assert saved["currency"] == before["currency"]


def test_metadata_edit_of_missing_project_does_not_create_any_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(metadata_path("proj_other"), {"name": "Other"})
    before = set(tmp_path.rglob("*"))
    response = TestClient(app).put(f"/api/projects/{PID}/metadata", json={"name": "Missing"})
    assert response.status_code == 404, response.text
    assert set(tmp_path.rglob("*")) == before
