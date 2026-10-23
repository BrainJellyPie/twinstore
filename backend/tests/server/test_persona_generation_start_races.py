"""Reserve a project's next customer generation before competing work can start."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import generation_async, projects, setups, simulation
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.generations import list_generations
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def requests(layout, monkeypatch):
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    write_json(setup_path(PID, "setup_other"), {**read_setup(PID, SID), "id": "setup_other"})
    return TestClient(app), submit


def _overlap(monkeypatch, module, method, first, second):
    ready, release = Event(), Event()
    original = getattr(module, method)

    def paused(*args, **kwargs):
        if not ready.is_set():
            ready.set()
            assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, method, paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        try:
            assert ready.wait(5)
            b = pool.submit(second)
            try:
                b.result(timeout=0.2)
            except TimeoutError:
                pass  # the protected request waits for the first operation to commit
        finally:
            release.set()
        return a.result(timeout=5), b.result(timeout=5)


@pytest.mark.parametrize("same_layout", [False, True])
@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("generation_first", [False, True])
def test_generation_and_run_capture_cannot_bypass_each_others_population_guards(
    requests, monkeypatch, same_layout, preview, generation_first,
):
    client, submit = requests

    def generate():
        return client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")

    def start():
        return client.post(f"/api/projects/{PID}/runs", json={
            "setup_id": SID if same_layout else "setup_other", "run_id": "run_population",
            "engine_type": "rule_based", "preview": preview,
        })

    if generation_first:
        generated, run = _overlap(monkeypatch, generation_async, "init_generation", generate, start)
    else:
        run, generated = _overlap(monkeypatch, simulation, "_load_simulation_inputs", start, generate)
    assert run.status_code == (409 if generation_first else 200), run.text
    assert generated.status_code == (200 if generation_first or preview else 409), generated.text
    assert submit.call_count == (2 if preview and not generation_first else 1)
    if generated.status_code == 200:
        jobs = list_generations(PID)
        assert len(jobs) == 1
        assert jobs[0]["status"] == "pending"
    else:
        assert list_generations(PID) == []
    if run.status_code == 200:
        assert simulation.get_run_status(PID, "run_population")["status"] == "pending"


@pytest.mark.parametrize("same_layout", [False, True])
def test_only_one_overlapping_generation_is_submitted_for_shared_customers(requests, monkeypatch, same_layout):
    client, submit = requests
    first, second = _overlap(monkeypatch, generation_async, "init_generation",
        lambda: client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona"),
        lambda: client.post(f"/api/projects/{PID}/setups/{SID if same_layout else 'setup_other'}/regenerate-persona"),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    submit.assert_called_once()
    assert len(list_generations(PID)) == 1


@pytest.mark.parametrize("delete_project", [False, True])
@pytest.mark.parametrize("generation_first", [False, True])
def test_generation_registration_respects_deletion_order(requests, monkeypatch, delete_project, generation_first):
    client, submit = requests

    def generate():
        return client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")

    def delete():
        return client.delete(f"/api/projects/{PID}" + ("" if delete_project else f"/setups/{SID}"))

    if generation_first:
        generated, deleted = _overlap(monkeypatch, generation_async, "init_generation", generate, delete)
    else:
        deleted, generated = _overlap(monkeypatch,
            projects if delete_project else setups, "remove_tree" if delete_project else "delete_setup",
            delete, generate,
        )
    assert generated.status_code == (200 if generation_first else 404), generated.text
    # A registered generation uses project metadata, so removing just its old
    # source layout remains safe; deleting the project must wait for completion.
    assert deleted.status_code == (409 if generation_first and delete_project else 200), deleted.text
    assert submit.call_count == (1 if generation_first else 0)
    assert setup_path(PID, SID).is_file() is (generation_first and delete_project)
    assert len(list_generations(PID)) == (1 if generation_first else 0)
    if delete_project and not generation_first:
        assert not metadata_path(PID).parent.exists()


def test_pending_generation_prevents_customer_edits_before_the_worker_starts(requests, monkeypatch):
    client, submit = requests
    before = read_json(personas_path(PID))
    generated, edited = _overlap(monkeypatch, generation_async, "init_generation",
        lambda: client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona"),
        lambda: client.put(f"/api/projects/{PID}/personas", json={"personas": []}),
    )
    assert generated.status_code == 200, generated.text
    assert edited.status_code == 409, edited.text
    assert read_json(personas_path(PID)) == before
    submit.assert_called_once()


@pytest.mark.parametrize("locked", ["tree", SID, "setup_other", "unrelated"])
def test_busy_project_returns_retryable_error_without_registering_generation(requests, monkeypatch, locked):
    client, submit = requests
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    path = setups.setup_lock_path(PID, locked)
    if locked == "tree":
        path = path.with_name(".setup-tree.lock")
    with FileLock(path, timeout=0):
        response = client.post(f"/api/projects/{PID}/setups/{SID}/regenerate-persona")
    expected = 200 if locked == "unrelated" else 503
    assert response.status_code == expected, response.text
    assert len(list_generations(PID)) == (1 if expected == 200 else 0)
    assert submit.call_count == (1 if expected == 200 else 0)
