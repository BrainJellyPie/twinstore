"""One project's layout save must not lock an unrelated layout."""
import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import setups
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data


@pytest.mark.parametrize("target_pid,target_sid,expected", [
    ("proj_a_setup_b", "setup_c", 200),
    ("proj_other", "setup_other", 200),
    ("proj_a", "setup_b_setup_c", 503),
])
def test_layout_locks_only_block_the_same_resource(tmp_path, monkeypatch, target_pid, target_sid, expected):
    monkeypatch.chdir(tmp_path)
    first = ("proj_a", "setup_b_setup_c")
    for pid, sid in {first, (target_pid, target_sid)}:
        root = tmp_path / ".data" / pid
        write_json(root / "metadata.json", {"name": "Test", "currency": "USD"})
        setup = new_setup_data("Original", None, None)
        setup["id"] = sid
        write_json(root / "setups" / f"{sid}.json", setup)

    def immediate_lock(path, timeout):
        return FileLock(path, timeout=0)

    monkeypatch.setattr(setups, "FileLock", immediate_lock)
    from store_emulator.server.main import app
    client = TestClient(app, raise_server_exceptions=False)
    first_path = tmp_path / ".data" / first[0] / "setups" / f"{first[1]}.json"
    before = first_path.read_bytes()
    with FileLock(str(setups.setup_lock_path(*first)), timeout=0):
        response = client.put(f"/api/projects/{target_pid}/setups/{target_sid}", json={"setup": {"name": "Changed"}})
    assert response.status_code == expected, response.text
    assert first_path.read_bytes() == before
    if expected == 200:
        assert response.json()["setup"]["name"] == "Changed"
