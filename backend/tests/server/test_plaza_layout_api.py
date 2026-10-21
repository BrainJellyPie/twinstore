"""Central-plaza requirements survive preview, portable files, save and reuse."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("template", ["community_pharmacy", "hypermarket", "specialty_cafe", "office_cafeteria"])
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
def test_preview_methods_files_and_saved_reuse_preserve_the_plaza(client, template, wall):
    options = {"style": "plaza", "width": 32, "height": 28, "currency": "JPY", "seed": 7,
               "dining_tables": 3, "dining_seats": 6, "table_rotation": 90, "table_clearance": 2,
               "checkouts": 3, "checkout_clearance": 2, "checkout_wall": wall, "gate_wall": wall,
               "aisle_width": 4, "max_shelf_run": 3, "shelf_direction": "vertical"}
    get = client.get(f"/api/store-templates/{template}/preview", params=options)
    body = {"template_id": template, **options, "requirements": "Keep the central gathering space"}
    post = client.post("/api/store-templates/preview", json=body)
    assert get.status_code == post.status_code == 200, (get.text, post.text)
    assert get.json()["racks"] == post.json()["racks"]
    portable = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body})
    assert portable.status_code == 200, portable.text
    assert portable.json()["layout"]["style"] == "plaza"
    created = client.post(f"/api/projects/{PID}/setups/generate", json=portable.json()["layout"])
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/{PID}/setups/{created.json()['id']}").json()
    assert saved["generation"]["style"] == "plaza"
    assert saved["store"]["racks"] == post.json()["racks"]
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200, reused.text
    assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"]["racks"] == saved["store"]["racks"]


def test_building_capacity_error_preserves_existing_layouts_then_recovers(client):
    floor = {"template_id": "office_cafeteria", "style": "plaza", "width": 32, "height": 28,
             "table_mix": {"two_seat": 1, "four_seat": 1, "six_seat": 1}, "table_rotation": 90}
    created = client.post(f"/api/projects/{PID}/setups/generate", json=floor)
    assert created.status_code == 200, created.text
    before = client.get(f"/api/projects/{PID}/setups").json()
    building = {"name": "Plaza floors", "floors": [{"label": "Shopping", "layout": floor},
                {"label": "Dining", "layout": {"template_id": "specialty_cafe", "style": "plaza", "width": 8, "height": 6, "dining_tables": 48}}]}
    failed = client.post(f"/api/projects/{PID}/setups/generate-building", json=building)
    assert failed.status_code == 422 and "Floor 2 (Dining)" in failed.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    building["floors"][1]["layout"]["dining_tables"] = 0
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": building["floors"]})
    assert portable.status_code == 200, portable.text
    building["floors"] = portable.json()["floors"]
    saved = client.post(f"/api/projects/{PID}/setups/generate-building", json=building)
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["setups"]) == 2
