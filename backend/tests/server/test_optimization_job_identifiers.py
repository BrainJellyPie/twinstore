"""Optimizer IDs and failed registration must never overwrite another job."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import optimize
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout  # noqa: F401


@pytest.fixture
def jobs(layout, monkeypatch):
    submit = Mock()
    monkeypatch.setattr(optimize.executor, "submit", submit)
    return TestClient(app, raise_server_exceptions=False), submit


def start(client):
    return client.post(f"/api/projects/{PID}/setups/{SID}/optimize", json={})


def test_distinct_uuids_with_the_same_short_prefix_keep_both_jobs(jobs, monkeypatch):
    client, submit = jobs
    ids = iter([UUID("abcdef00-0000-4000-8000-000000000001"), UUID("abcdef00-0000-4000-8000-000000000002")])
    monkeypatch.setattr(optimize, "uuid", SimpleNamespace(uuid4=lambda: next(ids)))
    first = start(client)
    assert first.status_code == 200, first.text
    root = metadata_path(PID).parent / "optimizations"
    old = root / first.json()["job_id"]
    original = {**first.json(), "status": "completed", "evaluations": 42}
    write_json(old / "status.json", original)
    write_json(old / "result.json", {"saved_result": "must survive"})
    before = {path.name: path.read_bytes() for path in old.iterdir()}

    second = start(client)
    assert second.status_code == 200, second.text
    assert {path.name: path.read_bytes() for path in old.iterdir()} == before
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(optimize.list_optimizations(PID)) == 2
    assert submit.call_count == 2


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("fail_registration", [False, True])
def test_existing_job_survives_identifier_reuse_and_registration_failure(jobs, monkeypatch, legacy, fail_registration):
    client, submit = jobs
    identifier = UUID("abcdef00-0000-4000-8000-000000000001")
    monkeypatch.setattr(optimize, "uuid", SimpleNamespace(uuid4=lambda: identifier))
    root = metadata_path(PID).parent / "optimizations"
    old = root / ("opt_abcdef" if legacy else f"opt_{identifier.hex}")
    write_json(old / "status.json", {"status": "completed", "preserved": True})
    write_json(old / "result.json", {"saved_result": "must survive"})
    before = {path.name: path.read_bytes() for path in old.iterdir()}
    if fail_registration:
        monkeypatch.setattr(optimize, "_write_status", Mock(side_effect=OSError("offline disk-full failure")))

    response = start(client)
    assert old.exists(), "A failed registration deleted an existing optimizer result"
    assert {path.name: path.read_bytes() for path in old.iterdir()} == before
    assert response.status_code == (409 if not legacy else 500 if fail_registration else 200), response.text
    assert submit.call_count == int(legacy and not fail_registration)
    assert len(list(root.iterdir())) == (2 if legacy and not fail_registration else 1)


def test_legacy_short_job_ids_remain_readable(jobs):
    client, _ = jobs
    response = start(client)
    assert response.status_code == 200, response.text
    original = response.json()
    root = metadata_path(PID).parent / "optimizations"
    source = root / original["job_id"]
    legacy = root / "opt_123abc"
    source.rename(legacy)
    write_json(legacy / "status.json", {**original, "job_id": legacy.name})
    saved = optimize.get_optimization(PID, legacy.name)
    assert saved.status.job_id == legacy.name
    assert read_json(legacy / "status.json")["setup_id"] == SID
