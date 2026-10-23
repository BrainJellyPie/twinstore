"""Excel imports and editor saves must keep each other's changes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, local

import pytest
from filelock import FileLock

from store_emulator.application import setups
from store_emulator.application.storage.setups import read_setup, setup_path
from store_emulator.domain.operations import OperationsConfig
from tests.server.test_atomic_floor_save import PID, SID, URL, floor


ROWS = [{"rack_id": "shelf", "block": 0, "face": "S", "level": 1,
         "sku": "imported", "name": "Imported", "price": 225, "promo": ""}]


@pytest.mark.parametrize("field", ["name", "memo", "operations"])
@pytest.mark.parametrize("first", ["editor", "import"])
def test_slot_import_and_editor_save_preserve_both_changes(floor, monkeypatch, field, first):
    ready, release, second_write = Event(), Event(), Event()
    worker = local()
    original_write = setups.write_setup

    def gated_write(pid, sid, data):
        if worker.kind == first:
            ready.set()
            assert release.wait(5)
        else:
            second_write.set()
        original_write(pid, sid, data)

    def edit():
        worker.kind = "editor"
        if field == "operations":
            setups.save_layout_operations(PID, SID, OperationsConfig(stock_per_facing=1))
        else:
            setups.save_setup_with_lock(PID, SID, {field: "Edited"})

    def import_slots():
        worker.kind = "import"
        return setups.replace_slots(PID, SID, ROWS)

    monkeypatch.setattr(setups, "write_setup", gated_write)
    first_job, second_job = (edit, import_slots) if first == "editor" else (import_slots, edit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(first_job)
        try:
            assert ready.wait(5)
            other = pool.submit(second_job)
            if second_write.wait(0.3):
                other.result(timeout=5)
        finally:
            release.set()
        pending.result(timeout=5)
        other.result(timeout=5)
    saved = read_setup(PID, SID)
    assert [item["sku"] for rack in saved["store"]["racks"] for slot in rack["slots"] for item in slot["items"]] == ["imported"]
    if field == "operations":
        assert saved["operations"]["stock_per_facing"] == 1
    else:
        assert saved[field] == "Edited"


@pytest.mark.parametrize("locked", [SID, "setup_unrelated"])
def test_slot_import_obeys_only_its_layout_lock(floor, monkeypatch, locked):
    client, _, _ = floor
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    before = setup_path(PID, SID).read_bytes()
    with FileLock(str(setups.setup_lock_path(PID, locked)), timeout=0):
        response = client.put(URL + "/slots", json={"slots": ROWS})
    assert response.status_code == (503 if locked == SID else 200), response.text
    if locked == SID:
        assert setup_path(PID, SID).read_bytes() == before
    else:
        assert response.json()["count"] == 1
