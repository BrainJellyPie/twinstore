"""Event windows must contain valid hours within the simulated day."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.mark.parametrize("start,end", [(24, 24), (0, 0), (18, 18), (21, 18), (22, 2)])
def test_empty_or_reversed_event_windows_are_rejected(client, start, end):
    response = client.post("/api/scenarios/preview", json={"events": [{
        "kind": "sports_match", "intensity": 1, "start_hour": start, "end_hour": end,
    }]})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("start,end", [(0, 24), (0, 1), (23, 24), (18, 21)])
def test_boundary_hours_affect_exactly_the_selected_range(client, start, end):
    response = client.post("/api/scenarios/preview", json={"events": [{
        "kind": "sports_match", "intensity": 1, "start_hour": start, "end_hour": end,
    }]})
    assert response.status_code == 200, response.text
    effects = response.json()
    affected = [hour for hour in range(24)
                if effects["traffic"] * effects["traffic_by_hour"].get(str(hour), 1) > 1]
    assert affected == list(range(start, end))
