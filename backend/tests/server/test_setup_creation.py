"""Creating a layout requires an existing project, including when no source is copied."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    return TestClient(app)


def test_empty_layout_cannot_create_an_orphan_project(client, tmp_path):
    response = client.post("/api/projects/proj_missing/setups", json={"mode": "empty"})
    assert response.status_code == 404
    assert not (tmp_path / ".data" / "proj_missing").exists()


def test_empty_layout_can_be_added_to_an_existing_project(client, tmp_path):
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test"})
    response = client.post("/api/projects/proj_test/setups", json={"mode": "empty", "name": "Empty layout"})
    assert response.status_code == 200
    layout = response.json()
    assert layout["name"] == "Empty layout" and layout["parentId"] is None
    assert (tmp_path / ".data" / "proj_test" / "setups" / f"{layout['id']}.json").exists()


@pytest.mark.parametrize("mode", ["empty", "racks", "racks_and_items"])
@pytest.mark.parametrize("removed", ["parent", "project"])
def test_deleted_source_or_project_cannot_receive_a_prepared_child(client, monkeypatch, mode, removed):
    from store_emulator.application import setups
    from store_emulator.application.storage.setups import metadata_path, new_setup_data, setup_path

    pid, root, parent = "proj_test", "setup_root", "setup_parent"
    write_json(metadata_path(pid), {"name": "Test"})
    for sid, ancestor in [(root, None), (parent, root)]:
        write_json(setup_path(pid, sid), {**new_setup_data(sid, ancestor, None), "id": sid})
    original = setups.new_setup_data
    created = []

    def delete_after_preparing(*args, **kwargs):
        draft = original(*args, **kwargs)
        created.append(draft["id"])
        url = f"/api/projects/{pid}" + (f"/setups/{parent}" if removed == "parent" else "")
        response = client.delete(url)
        assert response.status_code == 200, response.text
        return draft

    monkeypatch.setattr(setups, "new_setup_data", delete_after_preparing)
    response = client.post(f"/api/projects/{pid}/setups", json={"mode": mode, "source_setup_id": parent})
    assert response.status_code == 404, response.text
    assert len(created) == 1
    assert not setup_path(pid, created[0]).exists()
    if removed == "project":
        assert not metadata_path(pid).parent.exists()
    else:
        assert setup_path(pid, root).exists()


def test_busy_tree_does_not_block_another_project(client, monkeypatch):
    from filelock import FileLock
    from store_emulator.application import setups
    from store_emulator.application.storage.setups import metadata_path

    for pid in ["proj_test", "proj_other"]:
        write_json(metadata_path(pid), {"name": pid})
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    with FileLock(setups.setup_lock_path("proj_test", "tree").with_name(".setup-tree.lock")):
        blocked = client.post("/api/projects/proj_test/setups", json={"mode": "empty"})
        assert blocked.status_code == 503, blocked.text
        other = client.post("/api/projects/proj_other/setups", json={"mode": "empty"})
        assert other.status_code == 200, other.text
    assert client.post("/api/projects/proj_test/setups", json={"mode": "empty"}).status_code == 200
