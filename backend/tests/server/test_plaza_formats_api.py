"""Default-plaza formats keep their identities and schedules in portable buildings."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def test_catalog_and_default_building_options_round_trip(client):
    catalog = {row["id"]: row for row in client.get("/api/store-templates").json()}
    formats = ["community_market_hall", "creative_design_hall"]
    assert all(catalog[template]["default_style"] == "plaza" for template in formats)
    assert catalog[formats[0]]["default_dining_tables"] == 4
    assert catalog[formats[1]]["closed_days"] == [2]
    floors = [{"label": template, "layout": {"template_id": template, "currency": "JPY", "seed": index,
               "requirements": f"Keep the {template} plaza"}} for index, template in enumerate(formats)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Market and design", "floors": portable.json()["floors"]})
    assert created.status_code == 200, created.text
    for index, setup in enumerate(created.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        preview = client.post("/api/store-templates/preview", json=floors[index]["layout"])
        assert preview.status_code == 200, preview.text
        assert saved["store"]["racks"] == preview.json()["racks"]
        assert saved["store"]["weekly_schedule"] == preview.json()["weekly_schedule"]
        assert [day["day"] for day in saved["store"]["weekly_schedule"] if not day["is_open"]] == [[], [2]][index]
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
        assert reused.status_code == 200, reused.text
        assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"]["racks"] == saved["store"]["racks"]


@pytest.mark.parametrize("width", [8, 40])
def test_shallow_floor_without_display_space_rejects_save_and_recovers_with_counter_spacing(client, width):
    layout = {"template_id": "creative_design_hall", "style": "cross", "width": width, "height": 6,
              "checkouts": 1, "checkout_wall": "right", "checkout_clearance": 0, "dining_tables": 0,
              "gate_wall": "back", "entrance": "center", "exit_wall": "left", "exit_position": "center"}
    created = client.post(f"/api/projects/{PID}/setups/generate", json=layout)
    assert created.status_code == 200, created.text
    before = client.get(f"/api/projects/{PID}/setups").json()
    layout["checkout_clearance"] = 3
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        response = client.post(endpoint, json=layout)
        assert response.status_code == 422, response.text
        assert "counter spacing" in response.text and "checkout wall" in response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    layout["checkout_clearance"] = 0
    assert client.post("/api/store-templates/preview", json=layout).status_code == 200
