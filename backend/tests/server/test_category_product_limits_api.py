"""Category limits survive portable options and atomic multi-floor generation."""
import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def sku_counts(store):
    return {category: len({item["sku"] for rack in store["racks"] if rack["rack_desc"] == category
                          for slot in rack["slots"] for item in slot["items"]})
            for category in {rack["rack_desc"] for rack in store["racks"] if rack["slots"]}}


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_preview_options_files_save_and_reuse_preserve_independent_floor_limits(client, currency):
    choices = [
        {"template_id": "mexican_cantina", "category_product_limits": {"mexican_menu": 12, "soft_drinks": 3}, "products_per_category": 1},
        {"template_id": "community_pharmacy", "category_product_limits": {"wellness": 4, "pharmacy_care": 1}, "products_per_category": 2},
    ]
    floors = [{"label": f"Floor {i + 1}", "layout": {**choice, "currency": currency, "seed": 24}} for i, choice in enumerate(choices)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Distinct assortments", "floors": portable.json()["floors"]})
    assert result.status_code == 200, result.text
    for index, setup in enumerate(result.json()["setups"]):
        expected = choices[index]["category_product_limits"]
        preview = client.post("/api/store-templates/preview", json=floors[index]["layout"])
        assert preview.status_code == 200, preview.text
        counts = sku_counts(preview.json())
        assert all(counts[category] == count for category, count in expected.items())
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert saved["generation"]["category_product_limits"] == expected
        assert saved["store"]["racks"] == preview.json()["racks"]
        preset = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": saved["generation"]})
        assert preset.status_code == 200 and preset.json()["layout"]["category_product_limits"] == expected
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": setup["id"]})
        assert reused.status_code == 200, reused.text
        assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"] == saved["store"]


@pytest.mark.parametrize("limits", [{"soft_drinks": value} for value in [0, -1, 17, 1.5, True, "3", None]] + [{"unknown": 2}, {"": 2}, {"x" * 81: 2}])
def test_bad_limits_reject_preview_import_and_building_without_partial_writes(client, limits):
    good = {"template_id": "compact_pharmacy"}
    assert client.post(f"/api/projects/{PID}/setups/generate", json=good).status_code == 200
    before = client.get(f"/api/projects/{PID}/setups").json()
    bad = {"template_id": "mexican_cantina", "category_product_limits": limits}
    assert client.post("/api/store-templates/preview", json=bad).status_code == 422
    assert client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": bad}).status_code == 422
    floors = [{"label": "Care", "layout": good}, {"label": "Dining", "layout": bad}]
    assert client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors}).status_code == 422
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Rejected limits", "floors": floors})
    assert response.status_code == 422, response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    bad["category_product_limits"] = {"mexican_menu": 4}
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Fixed limits", "floors": floors}).status_code == 200
