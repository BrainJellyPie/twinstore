"""Deleting a layout tree must serialize with saves and simulation transitions."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import setups
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import (
    metadata_path, read_setup, setup_path, state_path,
)
from store_emulator.domain.operations import OperationsConfig


PID, ROOT, PARENT, CHILD = "proj_delete", "setup_root", "setup_parent", "setup_child"


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(metadata_path(PID), {"name": "Deletion race"})
    for sid, parent in [(ROOT, None), (PARENT, ROOT), (CHILD, PARENT)]:
        write_json(setup_path(PID, sid), {
            "id": sid, "name": sid, "status": "draft", "parentId": parent, "store": None,
        })
    write_json(state_path(PID), {"activeSetupId": CHILD})


@pytest.mark.parametrize("sid", [PARENT, CHILD])
@pytest.mark.parametrize("operations", [False, True])
def test_pending_save_cannot_resurrect_deleted_layout(tree, monkeypatch, sid, operations):
    ready, release, deleting = Event(), Event(), Event()
    original_write, original_delete = setups.write_setup, setups.delete_setup

    def paused_write(pid, setup_id, data):
        ready.set()
        assert release.wait(5)
        original_write(pid, setup_id, data)

    def observed_delete(pid, setup_id):
        deleting.set()
        original_delete(pid, setup_id)

    monkeypatch.setattr(setups, "write_setup", paused_write)
    monkeypatch.setattr(setups, "delete_setup", observed_delete)
    with ThreadPoolExecutor(max_workers=2) as pool:
        if operations:
            save = pool.submit(setups.save_layout_operations, PID, sid, OperationsConfig())
        else:
            save = pool.submit(setups.save_setup_with_lock, PID, sid, {"name": "Saved later"})
        try:
            assert ready.wait(5)
            removal = pool.submit(setups.delete_setup_with_descendants, PID, PARENT)
            if deleting.wait(0.3):
                removal.result(timeout=5)
        finally:
            release.set()
        save.result(timeout=5)
        assert set(removal.result(timeout=5)) == {PARENT, CHILD}
    assert not setup_path(PID, PARENT).exists()
    assert not setup_path(PID, CHILD).exists()
    assert setup_path(PID, ROOT).exists()
    assert read_json(state_path(PID))["activeSetupId"] == ROOT


@pytest.mark.parametrize("locked", [PARENT, CHILD, "setup_unrelated"])
def test_delete_waits_for_every_affected_layout_without_partial_deletion(tree, monkeypatch, locked):
    def immediate_lock(path, timeout):
        return FileLock(path, timeout=0)

    monkeypatch.setattr(setups, "FileLock", immediate_lock)
    from store_emulator.server.main import app
    client = TestClient(app, raise_server_exceptions=False)
    paths = [setup_path(PID, sid) for sid in [ROOT, PARENT, CHILD]] + [state_path(PID)]
    before = [path.read_bytes() for path in paths]
    with FileLock(str(setups.setup_lock_path(PID, locked)), timeout=0):
        response = client.delete(f"/api/projects/{PID}/setups/{PARENT}")
    if locked == "setup_unrelated":
        assert response.status_code == 200, response.text
        assert set(response.json()["deleted"]) == {PARENT, CHILD}
        assert read_json(state_path(PID))["activeSetupId"] == ROOT
    else:
        assert response.status_code == 503, response.text
        assert [path.read_bytes() for path in paths] == before
        for sid in [PARENT, CHILD]:
            with FileLock(str(setups.setup_lock_path(PID, sid)), timeout=0):
                pass


@pytest.mark.parametrize("sid", [PARENT, CHILD])
def test_running_status_is_rechecked_after_waiting_for_saves(tree, monkeypatch, sid):
    attempted_delete, release = Event(), Event()
    original_delete = setups.delete_setup

    def paused_delete(pid, setup_id):
        attempted_delete.set()
        assert release.wait(5)
        original_delete(pid, setup_id)

    monkeypatch.setattr(setups, "delete_setup", paused_delete)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with FileLock(str(setups.setup_lock_path(PID, sid)), timeout=0):
            removal = pool.submit(setups.delete_setup_with_descendants, PID, PARENT)
            try:
                attempted_delete.wait(0.3)
                data = read_setup(PID, sid)
                data["status"] = "running"
                write_json(setup_path(PID, sid), data)
            finally:
                release.set()
        with pytest.raises(AppError) as error:
            removal.result(timeout=5)
    assert error.value.status_code == 409
    assert all(setup_path(PID, item).exists() for item in [ROOT, PARENT, CHILD])
    assert read_json(state_path(PID))["activeSetupId"] == CHILD


def test_a_top_level_layout_can_go_while_another_stays(tree):
    write_json(setup_path(PID, "setup_other"), {"id": "setup_other", "name": "Other", "status": "draft", "parentId": None, "store": None})
    deleted = setups.delete_setup_with_descendants(PID, ROOT)
    assert sorted(deleted) == sorted([ROOT, PARENT, CHILD])
    assert read_json(state_path(PID))["activeSetupId"] == "setup_other"


def test_the_last_layout_of_a_store_stays(tree):
    with pytest.raises(AppError) as refused:
        setups.delete_setup_with_descendants(PID, ROOT)  # the root and its branches are every layout of the store
    assert refused.value.status_code == 409
    assert read_setup(PID, ROOT)["id"] == ROOT
