"""Table sizes survive every preview, persistence and options-file boundary."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("seats", [2, 4, 6])
@pytest.mark.parametrize("rotation", [0, 90])
def test_size_survives_get_post_save_reuse_and_options(client, seats, rotation):
    body = {"template_id": "specialty_cafe", "dining_tables": 2, "dining_seats": seats, "table_rotation": rotation}
    preview = client.get("/api/store-templates/specialty_cafe/preview", params={"dining_tables": 2, "dining_seats": seats, "table_rotation": rotation})
    post = client.post("/api/store-templates/preview", json=body)
    assert preview.status_code == post.status_code == 200
    assert preview.json() == post.json()
    tables = [rack for rack in post.json()["racks"] if rack["type"] == "table"]
    assert len(tables) == 2
    assert all(rack["rotation"] == rotation for rack in tables)
    assert all(rack["shape"] == [[1] * (seats // 2)] * 2 for rack in tables)
    created = client.post(f"/api/projects/{PID}/setups/generate", json=body)
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/{PID}/setups/{created.json()['id']}").json()
    assert saved["generation"]["dining_seats"] == seats
    assert saved["generation"]["table_rotation"] == rotation
    assert saved["store"]["racks"] == post.json()["racks"]
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200, reused.text
    imported = client.post("/api/store-templates/preset/validate", json={
        "format": "twinstore-layout-options", "version": 1, "layout": saved["generation"]})
    assert imported.status_code == 200, imported.text
    assert imported.json()["layout"]["dining_seats"] == seats
    assert imported.json()["layout"]["table_rotation"] == rotation


@pytest.mark.parametrize("seats", [0, 1, 3, 5, 7, -2, 2.0, 2.5, True, "2", None])
def test_bad_sizes_cannot_preview_save_or_import(client, seats):
    body = {"template_id": "specialty_cafe", "dining_seats": seats}
    before = client.get(f"/api/projects/{PID}/setups").json()
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        response = client.post(endpoint, json=body)
        assert response.status_code == 422, response.text
    response = client.post("/api/store-templates/preset/validate", json={
        "format": "twinstore-layout-options", "version": 1, "layout": body})
    assert response.status_code == 422, response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before


@pytest.mark.parametrize("rotation", [-90, 45, 180, 270, 360, 0.0, 90.0, False, True, "90", None])
def test_bad_rotations_cannot_preview_save_or_import(client, rotation):
    body = {"template_id": "specialty_cafe", "table_rotation": rotation}
    before = client.get(f"/api/projects/{PID}/setups").json()
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        assert client.post(endpoint, json=body).status_code == 422
    assert client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body}).status_code == 422
    assert client.get(f"/api/projects/{PID}/setups").json() == before


@pytest.mark.parametrize("rotation", [-90, 45, 180, "no", "90.5"])
def test_get_preview_rejects_bad_rotation(client, rotation):
    assert client.get("/api/store-templates/specialty_cafe/preview", params={"table_rotation": rotation}).status_code == 422


def test_building_keeps_distinct_sizes_and_rejects_invalid_floor_atomically(client):
    floors = [{"label": f"Floor {seats}", "layout": {"template_id": "specialty_cafe", "dining_tables": 1, "dining_seats": seats, "table_rotation": 0 if seats == 4 else 90}} for seats in [2, 4, 6]]
    response = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert response.status_code == 200, response.text
    assert [floor["layout"]["dining_seats"] for floor in response.json()["floors"]] == [2, 4, 6]
    assert [floor["layout"]["table_rotation"] for floor in response.json()["floors"]] == [90, 0, 90]
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Seating", "floors": floors})
    assert result.status_code == 200, result.text
    for setup, seats in zip(result.json()["setups"], [2, 4, 6], strict=True):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert saved["generation"]["dining_seats"] == seats
        assert saved["generation"]["table_rotation"] == (0 if seats == 4 else 90)
    before = client.get(f"/api/projects/{PID}/setups").json()
    floors[1]["layout"]["dining_seats"] = 3
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Invalid", "floors": floors}).status_code == 422
    assert client.get(f"/api/projects/{PID}/setups").json() == before
