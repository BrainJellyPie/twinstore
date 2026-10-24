"""Project deletion must serialize with every persisted field-pilot mutation."""

import pytest
from filelock import FileLock

from store_emulator.application import field_pilot, marketing, projects, setups
from store_emulator.application.errors import AppError
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.field_pilot import PilotRequest
from tests.server.test_field_pilot_api import (
    PID, ROOT, apply_import, client, create, preview_import, sheet, upload,
)
from tests.server.test_shelf_lab_start_snapshot import overlap


def mutation(client, operation):
    if operation == "create":
        return lambda: client.post(f"{ROOT}/staff-pitches/pit_test/pilots", json={
            "name": "Field tea", "eligibility": "First tea encounter", "outcome_window": "Same visit",
            "blocks": [{"staff_id": "staff1", "shift_id": "day1_am", "encounters": 40}], "seed": 5,
        })
    pilot_id = create(client)["pilot"]["pilot_id"]
    data = sheet(client, pilot_id, complete=True)
    if operation == "import":
        preview = preview_import(client, pilot_id, data).json()
        return lambda: apply_import(client, pilot_id, data, preview)
    assert upload(client, pilot_id, data).status_code == 200
    return lambda: client.post(f"{ROOT}/staff-pilots/{pilot_id}/close", json={"revision": 1})


@pytest.mark.parametrize("operation", ["create", "import", "close"])
@pytest.mark.parametrize("phase", ["read", "write", "delete_first"])
def test_project_delete_cannot_lose_or_resurrect_pilot_commits(client, monkeypatch, operation, phase):
    save = mutation(client, operation)
    delete = lambda: client.delete(ROOT)
    if phase == "delete_first":
        deleted, saved = overlap(monkeypatch, projects, "remove_tree", delete, save)
    else:
        method = "write_json" if phase == "write" else "get_pitch" if operation == "create" else "read_json"
        saved, deleted = overlap(monkeypatch, field_pilot, method, save, delete)
    assert deleted.status_code == 200, deleted.text
    assert saved.status_code == (404 if phase == "delete_first" else 200), saved.text
    assert not metadata_path(PID).parent.exists()


@pytest.mark.parametrize("operation", ["create", "import", "close"])
def test_busy_project_preserves_all_pilot_files(client, monkeypatch, operation):
    save = mutation(client, operation)
    root = metadata_path(PID).parent
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")}
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    lock = setups.setup_lock_path(PID, "tree").with_name(".setup-tree.lock")
    with FileLock(lock, timeout=0):
        response = save()
    assert response.status_code == 503, response.text
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*.json")} == before


@pytest.mark.parametrize("phase", ["read", "write", "delete_first"])
def test_source_study_deletion_keeps_the_committed_pilot_snapshot(client, monkeypatch, phase):
    save = mutation(client, "create")
    delete = lambda: client.delete(f"{ROOT}/staff-pitches/pit_test")
    if phase == "delete_first":
        deleted, saved = overlap(monkeypatch, marketing, "remove_tree", delete, save)
    else:
        method = "get_pitch" if phase == "read" else "write_json"
        saved, deleted = overlap(monkeypatch, field_pilot, method, save, delete)
    assert deleted.status_code == 204, deleted.text
    assert saved.status_code == (404 if phase == "delete_first" else 200), saved.text
    pilots = client.get(f"{ROOT}/staff-pilots").json()
    assert len(pilots) == (0 if phase == "delete_first" else 1)
    if pilots:
        pilot = client.get(f"{ROOT}/staff-pilots/{pilots[0]['pilot_id']}").json()["pilot"]
        assert pilot["variants"][0]["script"] == "Hello"
        assert pilot["product"]["price"] == 2000


@pytest.mark.parametrize("pid", ["bad.id", "bad id", "../project"])
def test_create_checks_project_id_before_constructing_the_lock(client, pid):
    request = PilotRequest(name="Field tea", eligibility="Each tea encounter", outcome_window="Same visit",
                           blocks=[{"staff_id": "staff1", "shift_id": "day1_am", "encounters": 40}])
    with pytest.raises(AppError) as error:
        field_pilot.create_pilot(pid, "pit_test", request)
    assert error.value.status_code == 400
