"""Large specialty and Asian dining floors preserve distinct defaults and category limits."""
import pytest
from fastapi.testclient import TestClient
PID = "proj_67916afd"
FORMATS = ["art_supply_warehouse", "beauty_outlet", "indian_curry_house", "vietnamese_cafe"]

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client

@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_distinct_defaults_and_menus_survive_four_floor_preview_export_save_and_reuse(client, currency):
    catalog = {row["id"]: row for row in client.get("/api/store-templates").json()}
    assert [catalog[template]["default_style"] for template in FORMATS] == ["aisles", "cross", "perimeter", "loop"]
    assert catalog[FORMATS[0]]["default_checkouts"] == 5 and catalog[FORMATS[3]]["closed_days"] == [1]
    assert "indian_menu" in {category["id"] for category in catalog[FORMATS[2]]["categories"]}
    assert "vietnamese_menu" in {category["id"] for category in catalog[FORMATS[3]]["categories"]}
    floors = [{"label": template, "layout": {"template_id": template, "currency": currency, "seed": index, "requirements": f"Keep {template} identity", "products_per_category": 2, "category_product_limits": {["art_craft", "fragrances", "indian_menu", "vietnamese_menu"][index]: 4}}} for index, template in enumerate(FORMATS)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Specialty and dining", "floors": portable.json()["floors"]})
    assert result.status_code == 200, result.text
    for index, setup in enumerate(result.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        preview = client.post("/api/store-templates/preview", json=floors[index]["layout"])
        assert preview.status_code == 200, preview.text
        assert saved["store"]["racks"] == preview.json()["racks"]
        assert saved["generation"]["category_product_limits"] == floors[index]["layout"]["category_product_limits"]
        category = ["art_craft", "fragrances", "indian_menu", "vietnamese_menu"][index]
        assert len({item["sku"] for rack in saved["store"]["racks"] if rack["rack_desc"] == category for slot in rack["slots"] for item in slot["items"]}) == 4
        assert [day["day"] for day in saved["store"]["weekly_schedule"] if not day["is_open"]] == [[], [], [2], [1]][index]
        assert saved["store"]["grid_size"] == [[36, 28], [32, 24], [24, 20], [22, 18]][index]
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": setup["id"]})
        assert reused.status_code == 200, reused.text
        assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"] == saved["store"]


def test_small_upper_restaurant_capacity_error_leaves_existing_building_untouched_and_recovers(client):
    good = {"template_id": "art_supply_warehouse"}
    assert client.post(f"/api/projects/{PID}/setups/generate", json=good).status_code == 200
    before = client.get(f"/api/projects/{PID}/setups").json()
    small = {"template_id": "indian_curry_house", "width": 8, "height": 6, "dining_tables": 8, "checkouts": 1}
    floors = [{"label": "Art supplies", "layout": good}, {"label": "Small curry house", "layout": small}]
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Small building", "floors": floors})
    assert response.status_code == 422 and "Floor 2 (Small curry house)" in response.text, response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    small["dining_tables"] = 0
    recovered = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Small building", "floors": floors})
    assert recovered.status_code == 200 and len(recovered.json()["setups"]) == 2, recovered.text
