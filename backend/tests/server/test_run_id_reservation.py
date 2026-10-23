"""Two layouts cannot publish into the same project's run directory."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import simulation
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.server.main import app
from store_emulator.server.routes import simulate
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("first_preview,second_preview", [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize("identity", ["explicit", "generated", "other_run", "other_project"])
@pytest.mark.parametrize("first_engine", ["rule_based", "vlm_glance"])
def test_concurrent_starts_reserve_project_run_identity(layout, monkeypatch, first_preview, second_preview, identity, first_engine):
    monkeypatch.setattr(simulate, "ensure_resolvable", lambda config: None)
    other_pid = "proj_other" if identity == "other_project" else PID
    other_sid = "setup_other"
    write_json(metadata_path(other_pid), read_json(metadata_path(PID)))
    write_json(personas_path(other_pid), read_json(personas_path(PID)))
    write_json(setup_path(other_pid, other_sid), {**read_setup(PID, SID), "id": other_sid})
    monkeypatch.setattr(simulation.uuid, "uuid4", lambda: uuid.UUID("12345600-0000-0000-0000-000000000000"))
    run_id = "run_123456" if identity == "generated" else "run_shared"
    other_run = "run_other" if identity == "other_run" else run_id
    same_record = other_pid == PID and other_run == run_id
    first_waiting, release, second_loaded, second_wrote = Event(), Event(), Event(), Event()
    original_write, original_load = simulation.write_status, simulation._load_simulation_inputs

    def paused_write(pid, rid, status, **extra):
        if pid == PID and extra.get("setup_id") == SID:
            first_waiting.set()
            assert release.wait(5), "the first run was not released"
        else:
            second_wrote.set()
        original_write(pid, rid, status, **extra)

    def observed_load(pid, setup, *args):
        result = original_load(pid, setup, *args)
        if setup["id"] == other_sid:
            second_loaded.set()
        return result

    monkeypatch.setattr(simulation, "write_status", paused_write)
    monkeypatch.setattr(simulation, "_load_simulation_inputs", observed_load)
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    first_body = {"setup_id": SID, "engine_type": first_engine, "preview": first_preview}
    second_body = {"setup_id": other_sid, "engine_type": "rule_based", "preview": second_preview}
    if identity != "generated":
        first_body["run_id"], second_body["run_id"] = run_id, other_run
    client = TestClient(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, f"/api/projects/{PID}/runs", json=first_body)
        try:
            assert first_waiting.wait(5)
            second = pool.submit(client.post, f"/api/projects/{other_pid}/runs", json=second_body)
            assert second_loaded.wait(5)
            if same_record:
                second_wrote.wait(0.3)
            else:
                # Unrelated run IDs and projects need not wait for this write.
                assert second.result(timeout=1).status_code == 200
        finally:
            release.set()
        first_response, second_response = first.result(timeout=5), second.result(timeout=5)
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == (409 if same_record else 200), second_response.text
    assert submit.call_count == (1 if same_record else 2)
    assert simulation.get_run_status(PID, run_id)["setup_id"] == SID
    assert read_setup(PID, SID)["status"] == ("draft" if first_preview else "running")
    assert read_setup(other_pid, other_sid)["status"] == ("draft" if same_record or second_preview else "running")
    if not same_record:
        assert simulation.get_run_status(other_pid, other_run)["setup_id"] == other_sid
