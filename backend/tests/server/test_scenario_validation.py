"""Reject malformed traffic schedules before they reach a simulation."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.mark.parametrize("scenario", [
    {"hourly_traffic": {"10": -0.1}},
    {"hourly_traffic": {"10": "Infinity"}},
    {"hourly_traffic": {"10": "-Infinity"}},
    {"hourly_traffic": {"10": "NaN"}},
    {"hourly_traffic": {"-1": 1.0}},
    {"hourly_traffic": {"24": 1.0}},
    {"only_days": [0]},
    {"only_days": [8]},
    {"only_days": [1, -1, 7]},
])
def test_invalid_schedule_returns_validation_error(client, scenario):
    response = client.post("/api/scenarios/preview", json=scenario)
    assert response.status_code == 422


def test_boundary_hours_days_and_zero_traffic_are_valid(client):
    response = client.post("/api/scenarios/preview", json={
        "only_days": [1, 7], "hourly_traffic": {"0": 0, "23": 1.5},
    })
    assert response.status_code == 200
    assert response.json()["traffic_by_hour"] == {"0": 0.0, "23": 1.5}


def test_all_presets_still_validate(client):
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    assert len(response.json()) >= 15
