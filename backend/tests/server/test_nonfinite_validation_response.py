"""Malformed numeric requests should receive a usable validation response."""

import json

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.domain.persona import Persona


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    persona = Persona(id="p_test", identity="Student", age_group="20s", gender="Female",
                      description="Buys tea", intent="tea", purpose="tea")
    write_json(root / "personas.json", [persona.model_dump(mode="json")])
    write_json(root / "metadata.json", {"name": "Test", "updated_at": "original"})
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False), root, persona


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("field", ["category_rates", "budget_max"])
def test_nonfinite_values_return_validation_error_without_modifying_data(project, value, field):
    client, root, persona = project
    data = {**persona.model_dump(mode="json"), field: {"drinks": value} if field == "category_rates" else value}
    previous = (root / "personas.json").read_bytes()
    response = client.put("/api/projects/proj_test/personas", content=json.dumps({"personas": [data]}),
                          headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], list)
    assert isinstance(response.json()["detail"][0]["input"], str)
    assert (root / "personas.json").read_bytes() == previous


def test_overflowing_json_number_returns_validation_error(project):
    client, root, persona = project
    data = {**persona.model_dump(mode="json"), "category_rates": {"drinks": "RATE"}}
    previous = (root / "personas.json").read_bytes()
    body = json.dumps({"personas": [data]}).replace('"RATE"', "1e9999")
    response = client.put("/api/projects/proj_test/personas", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text
    assert (root / "personas.json").read_bytes() == previous


def test_finite_invalid_numbers_keep_the_normal_validation_shape(project):
    client, _, persona = project
    data = {**persona.model_dump(mode="json"), "category_rates": {"drinks": -0.01}}
    response = client.put("/api/projects/proj_test/personas", json={"personas": [data]})
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "personas", 0, "category_rates", "drinks"]
    assert error["input"] == -0.01


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e9999"])
def test_nonfinite_scenario_validation_uses_the_same_error_response(project, value):
    client, _, _ = project
    response = client.post("/api/scenarios/preview", content='{"hourly_traffic": {"10": ' + value + '}}',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "hourly_traffic", "10"]
    assert isinstance(error["input"], str)


def test_malformed_json_keeps_its_validation_error(project):
    client, _, _ = project
    response = client.post("/api/scenarios/preview", content='{"hourly_traffic":', headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "json_invalid"


@pytest.mark.parametrize("body", [b"\xff", b"\x80broken", b"valid UTF-8"])
def test_wrong_content_type_returns_readable_validation_error(project, body):
    client, _, _ = project
    response = client.post("/api/scenarios/preview", content=body, headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 422, response.text
    error = response.json()["detail"][0]
    assert error["loc"] == ["body"]
    assert error["input"] == body.decode("utf-8", errors="replace")


def test_half_an_emoji_returns_a_validation_error_instead_of_failing(project):
    client, _, _ = project
    # A name cut through an emoji's surrogate pair: JSON allows the escape, the response must still encode.
    response = client.post("/api/projects/proj_test/online/sites/site_x/copy", content='{"name": "Shop \\ud83d", "note": ""}',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "name"]
    assert error["input"] == "Shop ?"
