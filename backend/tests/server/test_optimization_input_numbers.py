"""Invalid optimization thresholds must fail before a background job is created."""

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import optimize
from store_emulator.application.storage.io import write_json
from store_emulator.domain.persona import Persona
from store_emulator.engine.layout_gen import generate_store


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"currency": "USD"})
    write_json(root / "setups" / "setup_test.json", {
        "id": "setup_test", "store": generate_store("mini_mart").model_dump(mode="json"),
    })
    persona = Persona(id="p1", identity="Shopper", age_group="20s", gender="Female",
                      description="Tea", intent="tea", purpose="tea")
    write_json(root / "personas.json", [persona.model_dump(mode="json")])
    executor = Mock()
    monkeypatch.setattr(optimize, "executor", executor)
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False), root, executor


@pytest.mark.parametrize("value", [
    "Infinity", "1e9999", "NaN", "-Infinity", float("inf"), float("-inf"), float("nan"), -0.01, None,
])
def test_invalid_threshold_does_not_create_a_job(project, value):
    client, root, executor = project
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")}
    response = client.post(
        "/api/projects/proj_test/setups/setup_test/optimize",
        content=json.dumps({"spec": {"constraints": {"min_improvement": value}}}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text
    assert not (root / "optimizations").exists()
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")} == before
    executor.submit.assert_not_called()


@pytest.mark.parametrize("value", [0, 0.05, 2.0])
def test_finite_threshold_round_trips_through_job_status(project, value):
    client, _, executor = project
    response = client.post("/api/projects/proj_test/setups/setup_test/optimize",
                           json={"spec": {"constraints": {"min_improvement": value}}})
    assert response.status_code == 200, response.text
    job = response.json()["job_id"]
    status = client.get(f"/api/projects/proj_test/optimizations/{job}")
    assert status.status_code == 200, status.text
    assert status.json()["status"]["spec"]["constraints"]["min_improvement"] == value
    executor.submit.assert_called_once()
