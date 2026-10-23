"""Shelf Lab registers one committed input snapshot before its project/capture can disappear."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock
from PIL import Image

from store_emulator.application import capture, projects, setups, shelf_lab
from store_emulator.application.async_executor import executor
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup
from store_emulator.domain.capture import CaptureItem, CaptureResult, CaptureStatus
from store_emulator.domain.config import LLMConfig
from store_emulator.server.main import app
from tests.server.test_simulation_setup_races import PID, SID, layout

CID = "cap_offline"


@pytest.fixture
def lab(layout, monkeypatch):
    root = metadata_path(PID).parent / "captures" / CID
    store = read_setup(PID, SID)["store"]
    rack = next(r for r in store["racks"] if any(s["items"] for s in r["slots"]))
    item = next(item for slot in rack["slots"] for item in slot["items"])
    write_json(root / "status.json", CaptureStatus(capture_id=CID, status="completed").model_dump(mode="json"))
    write_json(root / "result.json", CaptureResult(image_size=(160, 160), currency="USD", items=[CaptureItem(
        id="i1", band=0, level=1, order=0, sku=item["sku"], name=item["name"], price=item["price"], labeled=True,
    )]).model_dump(mode="json"))
    Image.new("RGB", (160, 160), "white").save(root / "image.jpg")
    monkeypatch.setattr(shelf_lab, "capture_llm_config", lambda *args: LLMConfig(model="offline"))
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    body = {"setup_id": SID, "rack_id": rack["id"], "panel": 20, "max_stockouts": 0}
    return TestClient(app), submit, body, root


def overlap(monkeypatch, module, method, first, second):
    ready, release = Event(), Event()
    original = getattr(module, method)

    def paused(*args, **kwargs):
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
                pass
        finally:
            release.set()
        return a.result(timeout=5), b.result(timeout=5)


@pytest.mark.parametrize("kind", ["audit", "sim2real"])
@pytest.mark.parametrize("deleted", ["project", "capture"])
@pytest.mark.parametrize("start_first", [False, True])
def test_start_and_deletion_cannot_create_orphaned_jobs(lab, monkeypatch, kind, deleted, start_first):
    client, submit, body, root = lab

    def start():
        return client.post(f"/api/projects/{PID}/captures/{CID}/{kind}", json=body if kind == "audit" else {})

    def delete():
        return client.delete(f"/api/projects/{PID}" + (f"/captures/{CID}" if deleted == "capture" else ""))

    if start_first:
        started, removed = overlap(monkeypatch, shelf_lab, "_new_job", start, delete)
    else:
        removed, started = overlap(monkeypatch, projects if deleted == "project" else capture, "remove_tree", delete, start)
    assert started.status_code == (200 if start_first else 404), started.text
    assert removed.status_code == (409 if start_first else (204 if deleted == "capture" else 200)), removed.text
    assert submit.call_count == (1 if start_first else 0)
    assert root.exists() is start_first
    assert len(shelf_lab.list_jobs(PID, CID)) == (1 if start_first else 0)


@pytest.mark.parametrize("kind", ["audit", "sim2real"])
def test_study_reads_customers_after_an_accepted_save(lab, monkeypatch, kind):
    client, submit, body, _ = lab
    people = [{**read_json(personas_path(PID))[0], "id": "edited_customer"}]
    seen = []
    original = shelf_lab._personas

    def observe(pid):
        people = original(pid)
        seen.append([p.id for p in people])
        return people

    monkeypatch.setattr(shelf_lab, "_personas", observe)
    saved, started = overlap(monkeypatch, projects, "write_json",
        lambda: client.put(f"/api/projects/{PID}/personas", json={"personas": people}),
        lambda: client.post(f"/api/projects/{PID}/captures/{CID}/{kind}", json=body if kind == "audit" else {}))
    assert saved.status_code == started.status_code == 200
    assert seen == [["edited_customer"]]
    submit.assert_called_once()


@pytest.mark.parametrize("later_estimate", [None, 900])
def test_audit_uses_traffic_from_its_starting_customer_snapshot(lab, monkeypatch, later_estimate):
    client, submit, body, _ = lab
    original = read_json(metadata_path(PID))
    write_json(metadata_path(PID), {**original, "estimated_daily_visitors": {"1": 100}})
    monkeypatch.setattr(shelf_lab, "match_field", lambda store, result: store)
    monkeypatch.setattr(shelf_lab, "diff_face", lambda *args: ([], []))

    async def price(*args, **kwargs):
        return SimpleNamespace(whole=None, losses={}), None

    monkeypatch.setattr(shelf_lab, "price_findings", price)
    started = client.post(f"/api/projects/{PID}/captures/{CID}/audit", json=body)
    assert started.status_code == 200, started.text
    write_json(metadata_path(PID), original if later_estimate is None else {**original, "estimated_daily_visitors": {"1": later_estimate}})
    submit.call_args.args[0]()
    view = shelf_lab.get_job(PID, CID, started.json()["job_id"])
    assert view.status.status == "completed", view.status.error
    assert view.audit.visitors_per_day == 100 and view.audit.simulated_visitors_per_day == 1


@pytest.mark.parametrize("kind", ["audit", "sim2real"])
@pytest.mark.parametrize("lock", ["tree", SID])
def test_busy_starts_return_retryable_errors_without_pending_jobs(lab, monkeypatch, kind, lock):
    client, submit, body, _ = lab
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    path = setups.setup_lock_path(PID, lock)
    if lock == "tree":
        path = path.with_name(".setup-tree.lock")
    with FileLock(path, timeout=0):
        response = client.post(f"/api/projects/{PID}/captures/{CID}/{kind}", json=body if kind == "audit" else {})
    assert response.status_code == 503, response.text
    submit.assert_not_called()
    assert shelf_lab.list_jobs(PID, CID) == []
