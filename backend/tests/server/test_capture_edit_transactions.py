"""Capture corrections and counterfactual photos commit against a live, consistent source."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import capture, projects, shelf_lab
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import CID, PID, lab, layout, overlap


@pytest.fixture
def editing(lab):
    _, submit, body, root = lab
    result = read_json(root / "result.json")
    result["items"][0]["boxes"] = [{"x1": 20, "y1": 20, "x2": 80, "y2": 120}]
    write_json(root / "result.json", result)
    return TestClient(app, raise_server_exceptions=False), submit, body, root


def correct(client, **changes):
    return client.put(f"/api/projects/{PID}/captures/{CID}",
                      json={"items": [{"id": "i1", "name": "Corrected", **changes}]})


def create(client):
    return client.post(f"/api/projects/{PID}/captures/{CID}/edits",
                       json={"edits": [{"kind": "promo", "item_id": "i1", "promo": "NEW"}]})


def test_concurrent_capture_corrections_keep_result_and_overlay_together(editing, monkeypatch):
    client, _, _, root = editing
    ready, release = Event(), Event()

    def overlay(photo, result):
        item = result.items[0]
        if item.name == "First":
            ready.set()
            assert release.wait(5)
        return f"{item.name}:{item.price}".encode()

    monkeypatch.setattr(capture, "render_overlay", overlay)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(correct, client, name="First", price=100)
        try:
            assert ready.wait(5)
            second = pool.submit(correct, client, name="Second", price=200)
            try:
                second.result(timeout=.2)
            except TimeoutError:
                pass
        finally:
            release.set()
        assert first.result(timeout=5).status_code == second.result(timeout=5).status_code == 200
    item = read_json(root / "result.json")["items"][0]
    assert (root / "overlay.png").read_bytes() == f"{item['name']}:{item['price']}".encode()


@pytest.mark.parametrize("operation", ["correction", "photo"])
@pytest.mark.parametrize("deleted", ["capture", "project"])
@pytest.mark.parametrize("edit_first", [False, True])
def test_edits_and_deletion_cannot_recreate_deleted_capture_paths(editing, monkeypatch, operation, deleted, edit_first):
    client, _, _, root = editing
    edit = (lambda: correct(client, name="Corrected")) if operation == "correction" else lambda: create(client)
    delete = lambda: client.delete(f"/api/projects/{PID}" + (f"/captures/{CID}" if deleted == "capture" else ""))
    if edit_first:
        edited, removed = overlap(monkeypatch, capture if operation == "correction" else shelf_lab,
                                  "apply_edits", edit, delete)
    else:
        removed, edited = overlap(monkeypatch, capture if deleted == "capture" else projects,
                                  "remove_tree", delete, edit)
    assert edited.status_code == (200 if edit_first and operation == "correction" else 404), edited.text
    assert removed.status_code == (204 if deleted == "capture" else 200), removed.text
    assert not root.exists()


def test_study_snapshot_waits_for_accepted_capture_correction(editing, monkeypatch):
    client, submit, _, _ = editing
    observed = []
    original = shelf_lab._photo_and_result

    def read(*args):
        photo, result = original(*args)
        observed.append(result.items[0].price)
        return photo, result

    monkeypatch.setattr(shelf_lab, "_photo_and_result", read)
    edited, started = overlap(monkeypatch, capture, "write_json", lambda: correct(client, price=12345),
        lambda: client.post(f"/api/projects/{PID}/captures/{CID}/sim2real", json={}))
    assert edited.status_code == started.status_code == 200
    assert observed == [12345]
    submit.assert_called_once()


@pytest.mark.parametrize("start_first", [False, True])
def test_edit_deletion_and_study_image_snapshot_do_not_interleave(editing, monkeypatch, start_first):
    client, submit, _, root = editing
    created = create(client)
    assert created.status_code == 200, created.text
    eid = created.json()["edit_id"]
    delete = lambda: client.delete(f"/api/projects/{PID}/captures/{CID}/edits/{eid}")
    start = lambda: client.post(f"/api/projects/{PID}/captures/{CID}/sim2real", json={"edit_id": eid})
    if start_first:
        started, removed = overlap(monkeypatch, shelf_lab, "get_edit", start, delete)
    else:
        removed, started = overlap(monkeypatch, shelf_lab, "remove_tree", delete, start)
    assert removed.status_code == 204, removed.text
    assert started.status_code == (200 if start_first else 404), started.text
    assert submit.call_count == (1 if start_first else 0)
    assert not (root / "lab" / "edits" / eid).exists()


def test_photo_edit_rejects_a_capture_corrected_during_image_processing(editing, monkeypatch):
    client, _, _, root = editing
    original = shelf_lab.apply_edits

    def edit_and_correct(*args, **kwargs):
        result = original(*args, **kwargs)
        assert correct(client, name="New correction", price=12345).status_code == 200
        return result

    monkeypatch.setattr(shelf_lab, "apply_edits", edit_and_correct)
    response = create(client)
    assert response.status_code == 409, response.text
    assert read_json(root / "result.json")["items"][0]["price"] == 12345
    assert not list((root / "lab" / "edits").glob("*/edit.json"))


def test_photo_commit_finishes_before_capture_deletion(editing, monkeypatch):
    client, _, _, root = editing
    edited, removed = overlap(monkeypatch, shelf_lab, "_mask", lambda: create(client),
                              lambda: client.delete(f"/api/projects/{PID}/captures/{CID}"))
    assert edited.status_code == 200 and removed.status_code == 204
    assert not root.exists()


@pytest.mark.parametrize("failure", ["image", "render"])
def test_failed_overlay_preparation_does_not_save_a_partial_correction(editing, monkeypatch, failure):
    client, _, _, root = editing
    before = {name: (root / name).read_bytes() for name in ("result.json", "status.json")}
    if failure == "image":
        (root / "image.jpg").write_bytes(b"broken image")
    else:
        def fail(*args):
            raise ValueError("cannot render overlay")
        monkeypatch.setattr(capture, "render_overlay", fail)
    response = correct(client, name="Must not be saved", price=12345)
    assert response.status_code >= 400
    assert {name: (root / name).read_bytes() for name in before} == before
