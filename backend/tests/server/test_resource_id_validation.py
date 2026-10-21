"""Directory-backed identifiers in request bodies and queries are names, not paths."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import capture, setups, simulation, vision_inputs
from store_emulator.application.errors import AppError


@pytest.fixture
def client():
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.mark.parametrize("field", ["setup_id", "run_id"])
@pytest.mark.parametrize("value", ["../outside", "/tmp/outside", "..\\outside", "..", ""])
def test_simulation_ids_are_validated_before_preparing_files(client, monkeypatch, field, value):
    prepare = Mock(side_effect=AppError("unsafe request reached the application", 418))
    monkeypatch.setattr(simulation, "prepare_simulation", prepare)
    body = {"setup_id": "setup_test", "engine_type": "rule_based", field: value}
    response = client.post("/api/projects/proj_test/runs", json=body)
    assert response.status_code == 422
    prepare.assert_not_called()


def test_cloning_cannot_read_a_setup_outside_the_project(client, monkeypatch):
    create = Mock(side_effect=AppError("unsafe request reached the application", 418))
    monkeypatch.setattr(setups, "create_setup_from_source", create)
    response = client.post("/api/projects/proj_test/setups", json={
        "mode": "racks", "source_setup_id": "../../outside",
    })
    assert response.status_code == 422
    create.assert_not_called()


def test_comparison_cannot_read_runs_outside_the_project(client, monkeypatch):
    compare = Mock(side_effect=FileNotFoundError("unsafe request reached the application"))
    monkeypatch.setattr(simulation, "compare_project_runs", compare)
    response = client.get("/api/projects/proj_test/compare", params={"a": "../../../outside", "b": "run_b"})
    assert response.status_code == 422
    compare.assert_not_called()


def test_run_path_parameter_is_validated(client, monkeypatch):
    read = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(simulation, "get_run_status", read)
    response = client.get("/api/projects/proj_test/runs/%2e%2e/status")
    assert response.status_code == 400
    read.assert_not_called()


@pytest.mark.parametrize("path, body", [
    ("/api/projects/proj_test/captures/cap_test/apply", {"setup_id": "../../outside"}),
    ("/api/projects/proj_test/captures/apply", {"setup_id": "../../outside", "capture_ids": ["cap_test"]}),
])
def test_capture_application_rejects_external_setup_paths(client, monkeypatch, path, body):
    apply = Mock(side_effect=AppError("unsafe request reached the application", 418))
    monkeypatch.setattr(capture, "apply_captures", apply)
    response = client.post(path, json=body)
    assert response.status_code == 422
    apply.assert_not_called()


@pytest.mark.parametrize("field", ["setup_id", "run_id"])
def test_receipt_form_rejects_external_resource_paths(client, monkeypatch, field):
    read = Mock(side_effect=AppError("unsafe request reached the application", 418))
    monkeypatch.setattr(vision_inputs, "read_receipts", read)
    response = client.post("/api/projects/proj_test/receipts", data={field: "../../outside"},
                           files={"photos": ("receipt.png", b"test", "image/png")})
    assert response.status_code == 422
    read.assert_not_called()
