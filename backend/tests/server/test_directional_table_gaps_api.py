"""Directional gaps remain consistent through previews, options files and saved floors."""
import pytest
from fastapi.testclient import TestClient
PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("gap_x,gap_y", [(1, 4), (4, 1), (2, None)])
@pytest.mark.parametrize("rotation", [0, 90])
def test_gaps_survive_get_post_options_save_and_reuse(client, gap_x, gap_y, rotation):
    body = {"template_id": "specialty_cafe", "width": 28, "height": 24, "dining_tables": 3, "dining_seats": 6,
            "table_rotation": rotation, "table_clearance": 3, "table_clearance_x": gap_x, "table_clearance_y": gap_y}
    get = client.get("/api/store-templates/specialty_cafe/preview", params={k: v for k, v in body.items() if k != "template_id" and v is not None})
    post = client.post("/api/store-templates/preview", json=body)
    assert get.status_code == post.status_code == 200, (get.text, post.text)
    assert get.json() == post.json()
    preset = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body})
    assert preset.status_code == 200, preset.text
    assert preset.json()["layout"].get("table_clearance_x") == gap_x and preset.json()["layout"].get("table_clearance_y") == gap_y
    created = client.post(f"/api/projects/{PID}/setups/generate", json=body)
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/{PID}/setups/{created.json()['id']}").json()
    assert saved["store"]["racks"] == post.json()["racks"]
    assert saved["generation"]["table_clearance_x"] == gap_x and saved["generation"]["table_clearance_y"] == gap_y
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200, reused.text
    assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"] == saved["store"]


@pytest.mark.parametrize("axis", ["table_clearance_x", "table_clearance_y"])
@pytest.mark.parametrize("value", [0, -1, 5, 1.0, 1.5, True, "2"])
def test_invalid_overrides_fail_preview_import_and_save_without_writes(client, axis, value):
    body = {"template_id": "specialty_cafe", axis: value}
    before = client.get(f"/api/projects/{PID}/setups").json()
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        assert client.post(endpoint, json=body).status_code == 422
    assert client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body}).status_code == 422
    assert client.get(f"/api/projects/{PID}/setups").json() == before


@pytest.mark.parametrize("axis", ["table_clearance_x", "table_clearance_y"])
@pytest.mark.parametrize("value", ["0", "-1", "5", "1.5", "true"])
def test_get_rejects_out_of_range_or_noninteger_gaps(client, axis, value):
    assert client.get("/api/store-templates/specialty_cafe/preview", params={axis: value}).status_code == 422


def test_building_keeps_independent_gaps_and_mixed_capacity_failure_is_atomic(client):
    floors = [{"label": "Across", "layout": {"template_id": "specialty_cafe", "width": 28, "height": 24, "table_clearance_x": 4, "table_clearance_y": 1,
               "table_mix": {"two_seat": 1, "four_seat": 1, "six_seat": 1}, "table_rotation": 90}},
              {"label": "Along", "layout": {"template_id": "indian_curry_house", "width": 28, "height": 24, "dining_tables": 3,
               "table_clearance_x": 1, "table_clearance_y": 4}}]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Directional gaps", "floors": portable.json()["floors"]})
    assert result.status_code == 200, result.text
    for index, setup in enumerate(result.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert (saved["generation"]["table_clearance_x"], saved["generation"]["table_clearance_y"]) == [(4, 1), (1, 4)][index]
    before = client.get(f"/api/projects/{PID}/setups").json()
    floors[0]["layout"].update(width=8, height=6)
    bad = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Too small", "floors": floors})
    assert bad.status_code == 422 and "Floor 1 (Across)" in bad.text and "4-cell left-right and 1-cell back-front" in bad.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
    floors[0]["layout"].update(table_mix={"two_seat": 0, "four_seat": 0, "six_seat": 0})
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "No seating downstairs", "floors": floors}).status_code == 200
