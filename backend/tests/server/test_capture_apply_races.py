"""Applying reviewed photos commits current metadata and capture links together."""

import pytest

from store_emulator.application import capture, capture_batch, setups
from store_emulator.application.storage.setups import metadata_path, read_setup, read_state, setup_path
from store_emulator.domain.operations import OperationsConfig
from tests.server.test_capture_batch import BASE, PID, ROOT, prepare_save, workflow
from tests.server.test_shelf_lab_start_snapshot import overlap


@pytest.mark.parametrize("mode", ["single", "multiple", "batch"])
@pytest.mark.parametrize("phase", ["prepared", "editor_first"])
@pytest.mark.parametrize("change", ["operations", "clear_operations", "store"])
def test_photo_drafts_inherit_serialized_operations_and_preserve_reviewed_products(workflow, monkeypatch, mode, phase, change):
    client, form, _ = workflow
    setups.save_layout_operations(PID, BASE, OperationsConfig(stock_per_facing=11))
    reviewed_name = read_setup(PID, BASE)["store"]["name"]
    if mode == "batch":
        body, url, module = prepare_save(client, form), ROOT + "/batch-save", capture_batch
    else:
        body = {"setup_id": BASE, "new_rack": True} if mode == "single" else form
        url = ROOT + f"/{form['capture_ids'][0]}/apply" if mode == "single" else ROOT + "/apply"
        module = capture
    operations = None if change == "clear_operations" else OperationsConfig(stock_per_facing=77, backroom_per_product=19)

    def update():
        if change != "store":
            return setups.save_layout_operations(PID, BASE, operations)
        store = read_setup(PID, BASE)["store"]
        store["name"] = "Independent source edit"
        return setups.save_setup_with_lock(PID, BASE, {"store": store})

    save = lambda: client.post(url, json=body)
    if phase == "prepared":
        response, _ = overlap(monkeypatch, module, "new_setup_data", save, update)
    else:
        _, response = overlap(monkeypatch, setups, "write_setup", update, save)
    assert response.status_code == 200, response.text
    child = read_setup(PID, response.json()["setup_id"])
    if change == "store":
        assert child["store"]["name"] == reviewed_name
        assert read_setup(PID, BASE)["store"]["name"] == "Independent source edit"
    else:
        assert child.get("operations") == (operations.model_dump(mode="json") if operations is not None else None)
    if mode == "batch":
        assert client.post(url, json=body).json() == response.json()


@pytest.mark.parametrize("mode", ["single", "multiple"])
@pytest.mark.parametrize("deleted", ["project", "capture"])
def test_final_capture_status_write_cannot_recreate_a_deleted_tree(workflow, monkeypatch, mode, deleted):
    client, form, _ = workflow
    cid = form["capture_ids"][0]
    url = ROOT + f"/{cid}/apply" if mode == "single" else ROOT + "/apply"
    body = {"setup_id": BASE, "new_rack": True} if mode == "single" else form
    root = metadata_path(PID).parent
    deleted_path = root if deleted == "project" else root / "captures" / cid
    saved, removed = overlap(monkeypatch, capture, "_write_status",
        lambda: client.post(url, json=body),
        lambda: client.delete(f"/api/projects/{PID}" if deleted == "project" else ROOT + f"/{cid}"))
    assert saved.status_code == 200, saved.text
    assert removed.status_code == (200 if deleted == "project" else 204), removed.text
    assert not deleted_path.exists()


@pytest.mark.parametrize("mode", ["single", "multiple"])
def test_capture_deleted_during_preparation_does_not_leave_an_unreported_layout(workflow, monkeypatch, mode):
    client, form, _ = workflow
    cid = form["capture_ids"][-1]
    url = ROOT + f"/{cid}/apply" if mode == "single" else ROOT + "/apply"
    body = {"setup_id": BASE, "new_rack": True} if mode == "single" else form
    before = set(setup_path(PID, BASE).parent.glob("*.json"))
    active = read_state(PID)
    saved, removed = overlap(monkeypatch, capture, "new_setup_data",
        lambda: client.post(url, json=body), lambda: client.delete(ROOT + f"/{cid}"))
    assert saved.status_code == 404, saved.text
    assert removed.status_code == 204, removed.text
    assert set(setup_path(PID, BASE).parent.glob("*.json")) == before and read_state(PID) == active


def test_concurrent_applications_keep_both_capture_links(workflow, monkeypatch):
    client, form, _ = workflow
    cid = form["capture_ids"][0]
    save = lambda: client.post(ROOT + f"/{cid}/apply", json={"setup_id": BASE, "new_rack": True})
    first, second = overlap(monkeypatch, capture, "_write_status", save, save)
    assert first.status_code == second.status_code == 200
    expected = {first.json()["setup_id"], second.json()["setup_id"]}
    assert len(expected) == 2
    assert set(capture.get_capture(PID, cid).status.applied_setup_ids) == expected


@pytest.mark.parametrize('mode', ['single', 'multiple'])
def test_simultaneously_prepared_photo_drafts_get_distinct_generated_names(workflow, monkeypatch, mode):
    client, form, _ = workflow
    cid = form['capture_ids'][0]
    url = ROOT + f'/{cid}/apply' if mode == 'single' else ROOT + '/apply'
    body = {'setup_id': BASE, 'new_rack': True} if mode == 'single' else form
    save = lambda: client.post(url, json=body)
    first, second = overlap(monkeypatch, capture, 'new_setup_data', save, save)
    assert first.status_code == second.status_code == 200
    names = [read_setup(PID, response.json()['setup_id'])['name'] for response in (first, second)]
    assert len(set(names)) == 2
