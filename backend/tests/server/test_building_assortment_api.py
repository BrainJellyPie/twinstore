"""Shared assortment settings remain independent across heterogeneous building floors."""
import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("currency", ["USD", "JPY", "KRW"])
def test_shared_assortment_round_trips_six_different_floors_without_replacing_other_settings(client, currency):
    templates = ["urban_cvs", "community_pharmacy", "indian_curry_house", "vietnamese_cafe", "beauty_outlet", "art_supply_warehouse"]
    shared = {"seed": 26, "products_per_category": 2,
              "category_product_limits": {"soft_drinks": 3, "wellness": 1, "indian_menu": 4, "vietnamese_menu": 5, "fragrances": 6, "art_craft": 7},
              "excluded_categories": ["beer_alcohol"]}
    floors = [{"label": f"Level {i + 1}", "layout": {**shared, "template_id": template, "currency": currency,
               "open_hour": 6 + i, "close_hour": 18 + i, "closed_days": [i + 1],
               "requirements": f"Keep design {i}", "design_colors": {"accent": ["#123456", "#abcdef"][i % 2]}}}
              for i, template in enumerate(templates)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Shared assortment", "floors": portable.json()["floors"]})
    assert result.status_code == 200 and len(result.json()["setups"]) == 6, result.text
    for i, setup in enumerate(result.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        for key, expected in floors[i]["layout"].items():
            if key == "design_colors":
                assert all(saved["generation"][key][channel] == color for channel, color in expected.items())
            else:
                assert saved["generation"][key] == expected
        assert saved["store"]["currency"] == currency
        assert [day["day"] for day in saved["store"]["weekly_schedule"] if not day["is_open"]] == [i + 1]
        assert {(day["open_hour"], day["close_hour"]) for day in saved["store"]["weekly_schedule"] if day["is_open"]} == {(6 + i, 18 + i)}
        racks = [rack for rack in saved["store"]["racks"] if rack["slots"]]
        assert not any(rack["rack_desc"] == "beer_alcohol" for rack in racks)
        for category in {rack["rack_desc"] for rack in racks}:
            count = len({item["sku"] for rack in racks if rack["rack_desc"] == category for slot in rack["slots"] for item in slot["items"]})
            assert count == shared["category_product_limits"].get(category, 2)
        preview = client.post("/api/store-templates/preview", json=floors[i]["layout"])
        assert preview.status_code == 200 and preview.json()["racks"] == saved["store"]["racks"]


def test_a_target_with_no_remaining_category_blocks_partial_save_and_recovers_independently(client):
    excluded = ["electronics", "digital_accessories", "computer_peripherals", "photography_accessories", "home_lighting"]
    shared = {"seed": 26, "excluded_categories": excluded, "products_per_category": 2, "category_product_limits": {"electronics": 6}}
    good = {**shared, "template_id": "urban_cvs"}
    assert client.post(f"/api/projects/{PID}/setups/generate", json=good).status_code == 200
    before = client.get(f"/api/projects/{PID}/setups").json()
    floors = [{"label": "Groceries", "layout": good}, {"label": "Electronics", "layout": {**shared, "template_id": "electronics_shop"}}]
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Copied exclusions", "floors": floors})
    assert response.status_code == 422 and "Floor 2 (Electronics)" in response.text and "at least one product category" in response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    floors[1]["layout"]["excluded_categories"] = []
    fixed = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Fixed exclusions", "floors": floors})
    assert fixed.status_code == 200, fixed.text
    saved = [client.get(f"/api/projects/{PID}/setups/{setup['id']}").json() for setup in fixed.json()["setups"]]
    assert [setup["generation"]["excluded_categories"] for setup in saved] == [excluded, []]
    assert [setup["generation"]["category_product_limits"] for setup in saved] == [{"electronics": 6}, {"electronics": 6}]
