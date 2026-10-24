"""Playback loading must leave unrelated requests responsive during reads and encoding."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Event

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from store_emulator.application import simulation
from store_emulator.application.storage.io import write_json
from store_emulator.server.main import app

URL = "/api/projects/project/runs/run/timeline"


@pytest.fixture
def recorded_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    @asynccontextmanager
    async def no_startup(_app):
        yield

    monkeypatch.setattr(app.router, "lifespan_context", no_startup)
    path = tmp_path / ".data/project/runs/run/output/timeline.json"
    records = [{"persona_id": "고객/001 😀", "day": 1, "total_spent": 0,
                "timeline": [{"action": "exit", "elapsed_sec": 0, "description": "줄바꿈\n\"quote\"", "face": None}]}]
    write_json(path, records)
    return path, records


@pytest.mark.parametrize("stage", ["read", "encode"])
def test_playback_loading_does_not_block_health(recorded_run, monkeypatch, stage):
    _, records = recorded_run
    started, release = Event(), Event()
    original_read, original_dump = simulation.get_run_output, TypeAdapter.dump_json

    def pause():
        started.set()
        assert release.wait(5)

    def delayed_read(*args):
        pause()
        return original_read(*args)

    def delayed_dump(self, content, *args, **kwargs):
        if content == records:
            pause()
        return original_dump(self, content, *args, **kwargs)

    if stage == "read":
        monkeypatch.setattr(simulation, "get_run_output", delayed_read)
    else:
        monkeypatch.setattr(TypeAdapter, "dump_json", delayed_dump)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.get, URL)
        try:
            assert started.wait(5)
            assert pool.submit(client.get, "/api/health").result(timeout=1).json() == {"status": "ok"}
            assert not pending.done()
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert response.status_code == 200 and response.json() == records
    assert response.headers["content-type"] == "application/json"
    assert int(response.headers["content-length"]) == len(response.content)


@pytest.mark.parametrize("saved", [[], None, [{"persona_id": "001", "total_spent": 9007199254740993}], {"legacy": []}])
def test_saved_json_values_remain_exact(recorded_run, saved):
    path, _ = recorded_run
    write_json(path, saved)
    response = TestClient(app).get(URL)
    assert response.status_code == 200 and response.json() == saved


def test_missing_timeline_remains_an_empty_array(recorded_run):
    path, _ = recorded_run
    path.unlink()
    response = TestClient(app).get(URL)
    assert response.status_code == 200 and response.json() == []


def test_legacy_nonfinite_values_keep_json_null_encoding(recorded_run):
    path, _ = recorded_run
    write_json(path, [{"a": float("nan"), "b": float("inf"), "c": float("-inf")}])
    response = TestClient(app).get(URL)
    assert response.status_code == 200 and response.json() == [{"a": None, "b": None, "c": None}]


def test_damaged_timeline_keeps_its_named_error(recorded_run):
    path, _ = recorded_run
    path.write_text('[{"persona_id":', encoding="utf-8")
    response = TestClient(app).get(URL)
    assert response.status_code == 500
    assert "damaged" in response.json()["detail"] and "timeline.json" in response.json()["detail"]


@pytest.mark.parametrize("pid, rid", [("%2e%2e", "run"), ("project", "%2e%2e")])
def test_invalid_resource_ids_never_reach_storage(recorded_run, monkeypatch, pid, rid):
    def unexpected(*args):
        pytest.fail("invalid path reached the storage reader")

    monkeypatch.setattr(simulation, "get_run_output", unexpected)
    assert TestClient(app).get(f"/api/projects/{pid}/runs/{rid}/timeline").status_code == 400
