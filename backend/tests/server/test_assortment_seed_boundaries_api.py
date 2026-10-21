"""Seed extremes survive portable files and saved or duplicated building floors exactly."""
import pytest
from fastapi.testclient import TestClient
PID = "proj_67916afd"

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client

@pytest.mark.parametrize("seed", [-9007199254740991, -42, -1, 0, 9007199254740990, 9007199254740991])
def test_seed_roundtrips_get_post_portable_save_and_reuse(client, seed):
    layout = {"template_id": "thai_kitchen", "seed": seed, "products_per_category": 3,
              "category_product_limits": {"thai_menu": 5}, "currency": "KRW"}
    post = client.post("/api/store-templates/preview", json=layout)
    get = client.get("/api/store-templates/thai_kitchen/preview", params={"seed": seed, "products_per_category": 3, "currency": "KRW"})
    assert post.status_code == get.status_code == 200
    plain_post = client.post("/api/store-templates/preview", json={**layout, "category_product_limits": {}})
    assert get.json() == plain_post.json()
    portable = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": layout})
    assert portable.status_code == 200 and portable.json()["layout"]["seed"] == seed
    created = client.post(f"/api/projects/{PID}/setups/generate", json=portable.json()["layout"])
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/{PID}/setups/{created.json()['id']}").json()
    assert saved["generation"]["seed"] == seed and saved["store"]["racks"] == post.json()["racks"]
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200
    assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"] == saved["store"]


def test_building_preserves_independent_signed_seed_extremes(client):
    seeds = [-9007199254740991, 9007199254740991, -42, 0]
    floors = [{"label": f"Floor {index + 1}", "layout": {"template_id": "pet_superstore", "seed": seed, "products_per_category": 2}} for index, seed in enumerate(seeds)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Signed seeds", "floors": portable.json()["floors"]})
    assert result.status_code == 200, result.text
    for seed, setup in zip(seeds, result.json()["setups"], strict=True):
        detail = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert detail["generation"]["seed"] == seed
        expected = client.post("/api/store-templates/preview", json=detail["generation"])
        assert expected.status_code == 200 and detail["store"]["racks"] == expected.json()["racks"]
