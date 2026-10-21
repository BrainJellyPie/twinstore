"""Bulk dimensions persist independently and invalid upper floors never save partially."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("floor_count", [2, 6])
@pytest.mark.parametrize("width,height", [(8, 6), (8, 40), (40, 6), (40, 40)])
def test_shared_size_keeps_per_floor_settings_through_files_and_save(client, floor_count, width, height):
    floors = [{"label": f"Floor {index + 1}", "layout": {"template_id": "museum_gift_shop" if index % 2 else "hospital_convenience",
              "width": width, "height": height, "seed": index, "currency": "KRW", "dining_tables": 0, "checkouts": 1,
              "requirements": f"Keep floor {index + 1} independent", "open_hour": 6 + index, "close_hour": 20,
              "closed_days": [index + 1], "products_per_category": 1}} for index in range(floor_count)]
    imported = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert imported.status_code == 200, imported.text
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Shared footprint", "floors": imported.json()["floors"]})
    assert created.status_code == 200, created.text
    assert len(created.json()["setups"]) == floor_count
    for index, setup in enumerate(created.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert saved["store"]["grid_size"] == [width, height]
        assert saved["generation"]["seed"] == index
        assert saved["generation"]["requirements"] == f"Keep floor {index + 1} independent"
        assert saved["generation"]["currency"] == "KRW"
        assert saved["generation"]["open_hour"] == 6 + index
        assert saved["generation"]["closed_days"] == [index + 1]


@pytest.mark.parametrize("patch", [
    {"dining_tables": 12},
    {"reserved_areas": [{"label": "Kitchen", "x": 24, "y": 20, "width": 3, "height": 2}]},
    {"checkouts": 12, "checkout_clearance": 3},
    {"table_mix": {"two_seat": 1, "six_seat": 1}, "table_rotation": 90},
])
def test_resizing_cannot_drop_explicit_requirements_or_save_half_a_building(client, patch):
    before = client.get(f"/api/projects/{PID}/setups").json()
    floors = [{"label": "Shop", "layout": {"template_id": "hospital_convenience", "width": 8, "height": 6}},
              {"label": "Dining", "layout": {"template_id": "evening_food_court", "width": 8, "height": 6, **patch}}]
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Too small", "floors": floors})
    assert response.status_code == 422, response.text
    assert "Floor 2 (Dining)" in response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    imported = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert imported.status_code == 422, imported.text


def test_even_the_largest_shared_floor_can_need_a_counter_spacing_adjustment(client):
    floors = [{"label": "Shop", "layout": {"template_id": "hospital_convenience", "width": 40, "height": 40}},
              {"label": "Dining", "layout": {"template_id": "evening_food_court", "width": 40, "height": 40, "checkouts": 12, "checkout_clearance": 3}}]
    before = client.get(f"/api/projects/{PID}/setups").json()
    bad = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Largest floor", "floors": floors})
    assert bad.status_code == 422 and "spacing" in bad.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    floors[1]["layout"]["checkout_clearance"] = 2
    recovered = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Adjusted spacing", "floors": floors})
    assert recovered.status_code == 200, recovered.text
    saved = client.get(f"/api/projects/{PID}/setups/{recovered.json()['setups'][1]['id']}").json()
    assert sum(rack["type"] == "counter" for rack in saved["store"]["racks"]) == 12
