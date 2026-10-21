"""Entrance-based seating remains exact through previews, files and saved buildings."""
import pytest
from fastapi.testclient import TestClient
PID = "proj_67916afd"

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client

@pytest.mark.parametrize("zone", ["near_entrance", "away_from_entrance"])
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
def test_seating_zone_roundtrips_get_post_options_save_and_reuse(client, zone, wall):
    body = {"template_id": "thai_kitchen", "width": 28, "height": 24, "seating_zone": zone, "gate_wall": wall,
            "entrance": "right", "exit_wall": "back", "exit_position": "center", "dining_tables": 3,
            "dining_seats": 6, "table_rotation": 90, "table_clearance_x": 1, "table_clearance_y": 4}
    post = client.post("/api/store-templates/preview", json=body)
    get = client.get("/api/store-templates/thai_kitchen/preview", params={k: v for k, v in body.items() if k != "template_id"})
    assert post.status_code == get.status_code == 200, (post.text, get.text)
    assert post.json() == get.json()
    portable = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body})
    assert portable.status_code == 200 and portable.json()["layout"]["seating_zone"] == zone
    result = client.post(f"/api/projects/{PID}/setups/generate", json=portable.json()["layout"])
    assert result.status_code == 200, result.text
    saved = client.get(f"/api/projects/{PID}/setups/{result.json()['id']}").json()
    assert saved["generation"]["seating_zone"] == zone and saved["store"]["racks"] == post.json()["racks"]
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200
    assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"] == saved["store"]

@pytest.mark.parametrize("zone", ["near", "far", "NEAR_ENTRANCE"])
def test_invalid_zone_rejects_file_preview_and_save_without_changes(client, zone):
    body = {"template_id": "specialty_cafe", "seating_zone": zone}
    before = client.get(f"/api/projects/{PID}/setups").json()
    assert client.get("/api/store-templates/specialty_cafe/preview", params={"seating_zone": zone}).status_code == 422
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        assert client.post(endpoint, json=body).status_code == 422
    assert client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body}).status_code == 422
    assert client.get(f"/api/projects/{PID}/setups").json() == before


def test_building_preserves_each_entrance_zone_and_recovers_from_atomic_capacity_error(client):
    near = {"template_id": "specialty_cafe", "width": 28, "height": 24, "seating_zone": "near_entrance", "gate_wall": "right",
            "entrance": "center", "table_mix": {"two_seat": 1, "four_seat": 1, "six_seat": 1}}
    far = {"template_id": "turkish_cafe", "width": 8, "height": 6, "seating_zone": "away_from_entrance", "gate_wall": "left",
           "entrance": "right", "dining_tables": 48, "table_clearance_x": 4, "table_clearance_y": 4, "checkouts": 1}
    floors = [{"label": "Near entrance", "layout": near}, {"label": "Quiet corner", "layout": far}]
    before = client.get(f"/api/projects/{PID}/setups").json()
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Entrance seating", "floors": floors})
    assert result.status_code == 422 and "Floor 2 (Quiet corner)" in result.text and "dining tables" in result.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    far.update(width=28, height=24, dining_tables=3, table_clearance_y=1)
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Entrance seating", "floors": portable.json()["floors"]})
    assert result.status_code == 200, result.text
    for floor, setup in zip(floors, result.json()["setups"], strict=True):
        detail = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert detail["generation"]["seating_zone"] == floor["layout"]["seating_zone"]
        expected = client.post("/api/store-templates/preview", json=floor["layout"])
        assert expected.status_code == 200 and expected.json()["racks"] == detail["store"]["racks"]
