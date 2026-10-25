"""Reviewed layout operations cannot recreate a project after deletion wins."""

import pytest

from store_emulator.application import capture_batch, layout_edit, library_photos, rack_copy
from store_emulator.application.storage.setups import metadata_path
from tests.server import test_capture_batch as batch, test_layout_edit_api as edit, test_library_photos_api as photos, test_rack_copy_api as racks
from tests.server.test_capture_batch import workflow as batch_workflow
from tests.server.test_layout_edit_api import client as edit_client
from tests.server.test_library_photos_api import workflow as photo_workflow
from tests.server.test_rack_copy_api import workflow as rack_workflow
from tests.server.test_shelf_lab_start_snapshot import overlap


@pytest.mark.parametrize("kind,phase", [("rack", "setup_path"), ("rack", "FileLock"), ("photo", "setup_path"),
                                       ("photo", "FileLock"), ("edit", "setup_path"), ("edit", "FileLock"), ("batch", "setup_path")])
def test_deleted_projects_stay_deleted_during_reviewed_save(request, monkeypatch, kind, phase):
    if kind == "rack":
        client, _ = request.getfixturevalue("rack_workflow")
        body, module, url, pid = racks.request(client, request_id="a" * 32), rack_copy, racks.URL + "/save", racks.PID
    elif kind == "photo":
        client, _, _ = request.getfixturevalue("photo_workflow")
        body, module, url, pid = photos.request(client, request_id="a" * 32), library_photos, photos.URL + "/save", photos.PID
    elif kind == "edit":
        client = request.getfixturevalue("edit_client")
        body, module, url, pid = edit._save_body(), layout_edit, f"/api/projects/{edit.PID}/setups/{edit.SETUP}/edit", edit.PID
    else:
        client, form, _ = request.getfixturevalue("batch_workflow")
        body, module, url, pid = batch.prepare_save(client, form), capture_batch, batch.ROOT + "/batch-save", batch.PID
    root = metadata_path(pid).parent
    saved, deleted = overlap(monkeypatch, module, phase,
                             lambda: client.post(url, json=body), lambda: client.delete(f"/api/projects/{pid}"))
    assert deleted.status_code == 200, deleted.text
    assert saved.status_code == 404, saved.text
    assert not root.exists()


def test_deleted_project_is_not_recreated_by_a_late_photo_preview(photo_workflow, monkeypatch):
    client, _, _ = photo_workflow
    body = photos.request(client)
    root = metadata_path(photos.PID).parent
    preview, deleted = overlap(monkeypatch, library_photos, "_snapshot",
                               lambda: client.post(photos.URL + "/preview", json=body),
                               lambda: client.delete(f"/api/projects/{photos.PID}"))
    assert deleted.status_code == 200, deleted.text
    assert preview.status_code == 404, preview.text
    assert not root.exists()
