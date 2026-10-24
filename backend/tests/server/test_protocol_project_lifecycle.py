"""Research protocol history must not outlive deletion through a late commit."""

import pytest
from filelock import FileLock

from store_emulator.application import projects, protocols, setups
from store_emulator.application.storage.setups import metadata_path
from tests.server.test_protocols_api import CREATE, PID, ROOT, amend_request, client, create
from tests.server.test_shelf_lab_start_snapshot import overlap


def mutation(client, operation):
    if operation == "create":
        return lambda: client.post(ROOT, json=CREATE)
    first = create(client)
    protocol_id = first["ledger"]["protocol_id"]
    if operation == "retry":
        return lambda: client.post(ROOT, json=CREATE)
    return lambda: client.post(f"{ROOT}/{protocol_id}/amendments", json=amend_request(first))


@pytest.mark.parametrize("operation", ["create", "amend"])
@pytest.mark.parametrize("phase", ["revision", "write", "delete_first"])
def test_project_delete_serializes_protocol_creation_and_amendment(client, monkeypatch, operation, phase):
    save = mutation(client, operation)
    delete = lambda: client.delete(f"/api/projects/{PID}")
    if phase == "delete_first":
        deleted, saved = overlap(monkeypatch, projects, "remove_tree", delete, save)
    else:
        saved, deleted = overlap(monkeypatch, protocols, "record_revision" if phase == "revision" else "write_json", save, delete)
    assert deleted.status_code == 200, deleted.text
    assert saved.status_code == (404 if phase == "delete_first" else 200), saved.text
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("operation", ["create", "amend", "retry"])
def test_busy_project_keeps_protocol_history_and_directory_unchanged(client, monkeypatch, operation):
    save = mutation(client, operation)
    root = metadata_path(PID).parent
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")}
    existed = (root / "marketing" / "protocols").exists()
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    lock = setups.setup_lock_path(PID, "tree").with_name(".setup-tree.lock")
    with FileLock(lock, timeout=0):
        response = save()
    assert response.status_code == 503, response.text
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")} == before
    assert (root / "marketing" / "protocols").exists() is existed


def test_retry_waiting_for_project_deletion_does_not_acknowledge_a_removed_plan(client, monkeypatch):
    retry = mutation(client, "retry")
    deleted, response = overlap(monkeypatch, projects, "remove_tree", lambda: client.delete(f"/api/projects/{PID}"), retry)
    assert deleted.status_code == 200
    assert response.status_code == 404
    assert not metadata_path(PID).parent.exists()
