"""Visitor presets remain editable and portable as independent building floors."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def test_catalog_and_four_floor_options_round_trip(client):
    catalog = {row["id"]: row for row in client.get("/api/store-templates").json()}
    assert catalog["museum_gift_shop"]["closed_days"] == [1]
    assert catalog["evening_food_court"]["open_hours"] == [16, 24]
    assert catalog["evening_food_court"]["default_dining_tables"] == 12
    assert catalog["airport_shopping_gallery"]["default_checkouts"] == 4
    assert catalog["hospital_convenience"]["open_hours"] == [0, 24]
    formats = ["airport_shopping_gallery", "hospital_convenience", "museum_gift_shop", "evening_food_court"]
    floors = [{"label": template, "layout": {"template_id": template, "currency": "JPY", "seed": index, "checkout_clearance": index % 2,
               "open_hour": 6, "close_hour": 23, "closed_days": [7], "products_per_category": 2}}
              for index, template in enumerate(formats)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Visitor floors", "floors": portable.json()["floors"]})
    assert created.status_code == 200, created.text
    for index, setup in enumerate(created.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert saved["generation"]["template_id"] == formats[index]
        assert saved["generation"]["checkout_clearance"] == index % 2
        assert saved["store"]["currency"] == "JPY"
        assert all(day["open_hour"] == 6 and day["close_hour"] == 23 for day in saved["store"]["weekly_schedule"] if day["is_open"])
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
        assert reused.status_code == 200, reused.text
        assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"]["racks"] == saved["store"]["racks"]
