"""New pharmacy and dining floors preserve distinct defaults in portable buildings."""
import pytest
from fastapi.testclient import TestClient
PID = "proj_67916afd"
FORMATS = ["compact_pharmacy", "round_the_clock_pharmacy", "mediterranean_deli", "mexican_cantina"]

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client

@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_distinct_defaults_and_menus_survive_four_floor_preview_export_save_and_reuse(client, currency):
    catalog = {row["id"]: row for row in client.get("/api/store-templates").json()}
    assert [catalog[template]["default_style"] for template in FORMATS] == ["spine", "cross", "perimeter", "plaza"]
    assert catalog[FORMATS[1]]["open_hours"] == [0, 24] and catalog[FORMATS[0]]["closed_days"] == [7]
    assert "mediterranean_menu" in {category["id"] for category in catalog[FORMATS[2]]["categories"]}
    assert "mexican_menu" in {category["id"] for category in catalog[FORMATS[3]]["categories"]}
    floors = [{"label": template, "layout": {"template_id": template, "currency": currency, "seed": index, "requirements": f"Keep {template} identity"}} for index, template in enumerate(FORMATS)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Care and dining", "floors": portable.json()["floors"]})
    assert result.status_code == 200, result.text
    for index, setup in enumerate(result.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        preview = client.post("/api/store-templates/preview", json=floors[index]["layout"])
        assert preview.status_code == 200, preview.text
        assert saved["store"]["racks"] == preview.json()["racks"]
        assert [day["day"] for day in saved["store"]["weekly_schedule"] if not day["is_open"]] == [[7], [], [1], []][index]
        assert saved["store"]["grid_size"] == [[8, 8], [24, 18], [20, 18], [24, 20]][index]
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": setup["id"]})
        assert reused.status_code == 200, reused.text
        assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"] == saved["store"]


def test_small_upper_restaurant_capacity_error_leaves_existing_building_untouched_and_recovers(client):
    good = {"template_id": "compact_pharmacy"}
    assert client.post(f"/api/projects/{PID}/setups/generate", json=good).status_code == 200
    before = client.get(f"/api/projects/{PID}/setups").json()
    small = {"template_id": "mexican_cantina", "width": 8, "height": 6, "dining_tables": 8, "checkouts": 1}
    floors = [{"label": "Pharmacy", "layout": good}, {"label": "Small cantina", "layout": small}]
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Small building", "floors": floors})
    assert response.status_code == 422 and "Floor 2 (Small cantina)" in response.text, response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    small["dining_tables"] = 0
    recovered = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Small building", "floors": floors})
    assert recovered.status_code == 200 and len(recovered.json()["setups"]) == 2, recovered.text
