"""Category choices remain identical across previews, presets, saved floors and reuse."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    return TestClient(app)


def test_category_metadata_and_preview_save_reuse_agree(client, tmp_path):
    formats = client.get("/api/store-templates").json()
    categories = next(f["categories"] for f in formats if f["id"] == "urban_cvs")
    assert "beer_alcohol" in {category["id"] for category in categories}
    assert all(category["label"] and len(category["id"]) <= 80 for category in categories)
    options = {"template_id": "urban_cvs", "excluded_categories": ["beer_alcohol", "chips", "household"], "seed": 4}
    post_preview = client.post("/api/store-templates/preview", json=options)
    get_preview = client.get("/api/store-templates/urban_cvs/preview", params={"excluded_categories": options["excluded_categories"], "seed": 4})
    assert post_preview.status_code == get_preview.status_code == 200
    assert post_preview.json() == get_preview.json()
    assert not set(options["excluded_categories"]) & {rack["rack_desc"] for rack in post_preview.json()["racks"]}
    preset = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": options})
    assert preset.status_code == 200, preset.text
    assert preset.json()["layout"]["excluded_categories"] == options["excluded_categories"]
    assert list(tmp_path.iterdir()) == []

    write_json(tmp_path / ".data" / "proj_categories" / "metadata.json", {"currency": "USD", "name": "Custom assortment"})
    created = client.post("/api/projects/proj_categories/setups/generate", json=options)
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/proj_categories/setups/{created.json()['id']}").json()
    assert saved["store"]["racks"] == post_preview.json()["racks"]
    assert saved["generation"]["excluded_categories"] == options["excluded_categories"]
    reused = client.post("/api/projects/proj_categories/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200, reused.text
    detail = client.get(f"/api/projects/proj_categories/setups/{reused.json()['id']}").json()
    assert detail["store"]["racks"] == saved["store"]["racks"]
    assert detail["parentId"] == saved["id"]


@pytest.mark.parametrize("excluded", [["unknown"], [""], ["x" * 81], ["chips"] * 65, ["electronics"]])
def test_bad_or_empty_assortments_are_rejected_without_writes(client, tmp_path, excluded):
    options = {"template_id": "electronics_shop", "excluded_categories": excluded}
    post = client.post("/api/store-templates/preview", json=options)
    get = client.get("/api/store-templates/electronics_shop/preview", params={"excluded_categories": excluded})
    assert post.status_code == get.status_code == 422, (post.text, get.text)
    assert list(tmp_path.iterdir()) == []
