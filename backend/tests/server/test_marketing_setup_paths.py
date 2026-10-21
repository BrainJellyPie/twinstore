"""Marketing and shelf analyses resolve named layouts only inside their project."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing, shelf_lab
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import write_json


@pytest.mark.parametrize("value", ["../outside", "/tmp/outside", "..\\outside"])
@pytest.mark.parametrize("module,method,endpoint,body", [
    (marketing, "start_experiment", "experiments", {"variants": [{"name": "Promo", "changes": [{"kind": "promo", "sku": "tea", "promo": "NEW"}]}]}),
    (marketing, "start_shelf_test", "shelf-tests", {"rack_id": "rack", "target_sku": "tea", "changes": [{"kind": "promo", "sku": "tea", "promo": "NEW"}]}),
    (marketing, "preview_shelf", "shelf-tests/preview", {"rack_id": "rack"}),
    (shelf_lab, "start_audit", "captures/cap_test/audit", {"rack_id": "rack"}),
    (shelf_lab, "compare_rival_capture", "captures/cap_test/rival", {}),
])
def test_setup_references_reject_paths_before_application(monkeypatch, module, method, endpoint, body, value):
    from store_emulator.server.main import app
    call = Mock(side_effect=AppError("invalid reference reached the application", 418))
    monkeypatch.setattr(module, method, call)
    response = TestClient(app).post(f"/api/projects/proj_test/{endpoint}", json={**body, "setup_id": value})
    assert response.status_code == 422, response.text
    call.assert_not_called()


def test_preview_cannot_render_a_json_file_outside_setups(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    pid = "proj_67916afd"
    with TestClient(app) as client:
        source = client.get(f"/api/projects/{pid}/setups/setup_7d6d").json()
        write_json(tmp_path / ".data" / pid / "outside.json", source)
        response = client.post(f"/api/projects/{pid}/shelf-tests/preview", json={
            "setup_id": "../outside", "rack_id": "r_801fadeb", "target_sku": "A0017",
        })
        assert response.status_code == 422


@pytest.mark.parametrize("pid,sid", [("../outside", "setup_test"), ("proj_test", "../outside")])
def test_store_loader_rejects_paths_before_reading(monkeypatch, pid, sid):
    read = Mock()
    monkeypatch.setattr(shelf_lab, "read_setup", read)
    with pytest.raises(AppError) as error:
        shelf_lab._load_store(pid, sid)
    assert error.value.status_code == 400
    read.assert_not_called()


def test_store_loader_keeps_valid_uppercase_and_hyphenated_ids(monkeypatch):
    read = Mock(return_value={"store": {"id": "store", "name": "Test", "type": "cafe", "grid_size": [8, 6]}})
    monkeypatch.setattr(shelf_lab, "read_setup", read)
    assert shelf_lab._load_store("Project-1", "Layout-A").id == "store"
    read.assert_called_once_with("Project-1", "Layout-A")
