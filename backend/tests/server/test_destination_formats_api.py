"""New destinations retain independent schedules through portable building settings."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def test_catalog_default_schedules_preview_and_building_round_trip(client):
    catalog = {row["id"]: row for row in client.get("/api/store-templates").json()}
    assert catalog["weekend_farmers_market"]["closed_days"] == [1, 2, 3, 4, 5]
    assert catalog["station_food_market"]["open_hours"] == [5, 24]
    assert catalog["cinema_snack_shop"]["default_dining_tables"] == 0
    assert catalog["office_cafeteria"]["default_dining_tables"] == 16
    assert catalog["office_cafeteria"]["closed_days"] == [6, 7]
    formats = ["weekend_farmers_market", "station_food_market", "cinema_snack_shop", "office_cafeteria"]
    floors = [{"label": template, "layout": {"template_id": template, "currency": "JPY", "seed": index,
               "products_per_category": 2, "requirements": f"Keep the {template} opening days"}}
              for index, template in enumerate(formats)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Destination floors", "floors": portable.json()["floors"]})
    assert created.status_code == 200, created.text
    for index, setup in enumerate(created.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        preview = client.post("/api/store-templates/preview", json=floors[index]["layout"])
        assert preview.status_code == 200, preview.text
        assert saved["store"]["racks"] == preview.json()["racks"]
        assert saved["store"]["weekly_schedule"] == preview.json()["weekly_schedule"]
        assert [day["day"] for day in saved["store"]["weekly_schedule"] if not day["is_open"]] == catalog[formats[index]]["closed_days"]
        assert saved["generation"]["requirements"] == floors[index]["layout"]["requirements"]
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
        assert reused.status_code == 200, reused.text
        copy = client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()
        assert copy["store"]["racks"] == saved["store"]["racks"]
        assert copy["store"]["weekly_schedule"] == saved["store"]["weekly_schedule"]
