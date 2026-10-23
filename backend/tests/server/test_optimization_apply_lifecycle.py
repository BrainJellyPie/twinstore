"""Applying a saved search result commits its layout and status before deletion."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import optimize, projects, setups
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, new_setup_data, setup_path
from store_emulator.domain.optimize import OptimizeResult, OptimizeSpec
from store_emulator.engine.layout_gen import generate_store
from store_emulator.server.main import app

PID, SID, JID = "proj_apply", "setup_source", "opt_saved"
URL = f"/api/projects/{PID}/optimizations/{JID}/apply"


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = generate_store("mini_mart")
    source = new_setup_data("Original", None, store.model_dump(mode="json"))
    source["id"] = SID
    write_json(metadata_path(PID), {"name": "Apply lifecycle", "currency": "USD"})
    write_json(setup_path(PID, SID), source)
    spec = OptimizeSpec(budget=1, eval_customers=10)
    status = optimize.OptimizationStatus(job_id=JID, setup_id=SID, status="completed", spec=spec)
    result = OptimizeResult(spec=spec, baseline_score=100, best_score=110, relative_improvement=.1,
        best_store=store, applied_moves=["Move tea"], history=[], evaluations=1, seconds=0)
    optimize._write_status(PID, status)
    write_json(optimize._dir(PID, JID) / "result.json", result.model_dump(mode="json"))
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("phase", ["layout", "status"])
@pytest.mark.parametrize("name", [None, "Chosen result"])
def test_deletion_waits_for_the_complete_apply_commit(saved, monkeypatch, phase, name):
    entered, release = Event(), Event()
    original = optimize.write_json

    def write(path, payload):
        target = path.parent.name == "setups" if phase == "layout" else path.name == "status.json"
        if target:
            entered.set()
            assert release.wait(5)
        return original(path, payload)

    monkeypatch.setattr(optimize, "write_json", write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        applied = pool.submit(saved.post, URL, json={"name": name})
        try:
            assert entered.wait(5)
            deleted = pool.submit(saved.delete, f"/api/projects/{PID}")
            try:
                deleted.result(timeout=.2)
            except TimeoutError:
                pass
        finally:
            release.set()
        response = applied.result(timeout=5)
        assert response.status_code == 200, response.text
        assert deleted.result(timeout=5).status_code == 200
    assert not metadata_path(PID).parent.exists(), "apply resurrected the deleted project"


@pytest.mark.parametrize("name", [None, "Chosen result"])
def test_deletion_that_started_first_prevents_apply(saved, monkeypatch, name):
    entered, release = Event(), Event()
    original = projects.remove_tree

    def remove(path):
        entered.set()
        assert release.wait(5)
        return original(path)

    monkeypatch.setattr(projects, "remove_tree", remove)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deleted = pool.submit(saved.delete, f"/api/projects/{PID}")
        try:
            assert entered.wait(5)
            applied = pool.submit(saved.post, URL, json={"name": name})
            with pytest.raises(TimeoutError):
                applied.result(timeout=.2)
        finally:
            release.set()
        assert deleted.result(timeout=5).status_code == 200
        response = applied.result(timeout=5)
        assert response.status_code == 404, response.text
    assert not metadata_path(PID).parent.exists()


def test_apply_tree_lock_timeout_preserves_all_existing_data(saved, monkeypatch):
    root = metadata_path(PID).parent
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")}
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    with FileLock(setups.setup_lock_path(PID, "tree").with_name(".setup-tree.lock"), timeout=0):
        response = saved.post(URL, json={})
    assert response.status_code == 503, response.text
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")} == before
