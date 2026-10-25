"""Reviewed branches retain their captured products and inherit current operating settings."""

import pytest

from store_emulator.application import layout_edit, library_photos, rack_copy, setups
from store_emulator.application.storage.setups import read_setup, setup_path
from store_emulator.application.storage.io import write_json
from store_emulator.domain.operations import OperationsConfig
from tests.server import test_layout_edit_api as edit, test_library_photos_api as photos, test_rack_copy_api as racks
from tests.server.test_layout_edit_api import client as edit_client
from tests.server.test_library_photos_api import workflow as photo_workflow
from tests.server.test_rack_copy_api import workflow as rack_workflow
from tests.server.test_shelf_lab_start_snapshot import overlap


@pytest.mark.parametrize("kind", ["rack", "photo", "edit"])
@pytest.mark.parametrize("change", ["store", "operations"])
@pytest.mark.parametrize("phase", ["prepared", "editor_first"])
def test_reviewed_save_preserves_the_snapshot_and_inherits_current_operations(request, monkeypatch, kind, change, phase):
    if kind == "rack":
        client, _ = request.getfixturevalue("rack_workflow")
        body, module, url = racks.request(client, request_id="a" * 32), rack_copy, racks.URL + "/save"
        pid, sid, prefix = racks.PID, racks.SID, "rackcopy"
    elif kind == "photo":
        client, _, _ = request.getfixturevalue("photo_workflow")
        body, module, url = photos.request(client, request_id="a" * 32), library_photos, photos.URL + "/save"
        pid, sid, prefix = photos.PID, photos.SID, "photos"
    else:
        client = request.getfixturevalue("edit_client")
        source = read_setup(edit.PID, edit.SETUP)
        source.update(runId=None, status="draft")
        write_json(setup_path(edit.PID, edit.SETUP), source)
        body, module, url = edit._save_body(), layout_edit, f"/api/projects/{edit.PID}/setups/{edit.SETUP}/edit"
        pid, sid, prefix = edit.PID, edit.SETUP, "edit"
    reviewed_name = read_setup(pid, sid)["store"]["name"]
    operations = OperationsConfig(stock_per_facing=77, backroom_per_product=19)

    def update():
        if change == "operations":
            return setups.save_layout_operations(pid, sid, operations)
        store = read_setup(pid, sid)["store"]
        store["name"] = "Changed source while saving"
        return setups.save_setup_with_lock(pid, sid, {"store": store})

    save = lambda: client.post(url, json=body)
    if phase == "prepared":
        method = "apply_layout_edit" if kind == "edit" else "new_setup_data"
        response, _ = overlap(monkeypatch, module, method, save, update)
    else:
        _, response = overlap(monkeypatch, setups, "write_setup", update, save)
    assert response.status_code == 200, response.text
    child = f"setup_{prefix}_{body['request_id']}"
    if change == "store":
        assert read_setup(pid, child)["store"]["name"] == reviewed_name
        assert read_setup(pid, sid)["store"]["name"] == "Changed source while saving"
    else:
        assert read_setup(pid, child)["operations"] == operations.model_dump(mode="json")
        assert client.post(url, json=body).json() == response.json()
