"""Mixed counts persist atomically and malformed or impossible plans never save."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("rotation", [0, 90])
def test_preview_save_reuse_and_file_keep_mixed_counts(client, rotation):
    mix = {"two_seat": 3, "four_seat": 2, "six_seat": 1}
    body = {"template_id": "retro_diner", "dining_tables": 6, "table_mix": mix, "table_rotation": rotation}
    preview = client.post("/api/store-templates/preview", json=body)
    assert preview.status_code == 200, preview.text
    tables = [rack for rack in preview.json()["racks"] if rack["type"] == "table"]
    assert sorted(sum(map(sum, rack["shape"])) for rack in tables) == [2, 2, 2, 4, 4, 6]
    assert all(rack["rotation"] == rotation for rack in tables)
    created = client.post(f"/api/projects/{PID}/setups/generate", json=body)
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/{PID}/setups/{created.json()['id']}").json()
    assert saved["generation"]["table_mix"] == mix
    assert saved["store"]["racks"] == preview.json()["racks"]
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200, reused.text
    assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"]["racks"] == saved["store"]["racks"]
    preset = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body})
    assert preset.status_code == 200, preset.text
    assert preset.json()["layout"]["table_mix"] == mix


@pytest.mark.parametrize("patch", [
    {"table_mix": {"two_seat": -1}}, {"table_mix": {"four_seat": 49}}, {"table_mix": {"six_seat": True}},
    {"table_mix": {"two_seat": 1.5}}, {"table_mix": {"four_seat": "2"}}, {"table_mix": {"six_seat": None}},
    {"table_mix": {"two_seat": 24, "four_seat": 24, "six_seat": 1}}, {"table_mix": {"eight_seat": 1}},
    {"table_mix": {"two_seat": 2}, "dining_tables": 3}, {"table_mix": []}, {"table_mix": "mixed"},
    {"width": 8, "height": 6, "table_rotation": 90, "table_mix": {"two_seat": 1, "six_seat": 1}},
])
def test_invalid_mixes_never_save_or_import(client, patch):
    body = {"template_id": "retro_diner", **patch}
    before = client.get(f"/api/projects/{PID}/setups").json()
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        result = client.post(endpoint, json=body)
        assert result.status_code == 422, result.text
    assert client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body}).status_code == 422
    assert client.get(f"/api/projects/{PID}/setups").json() == before


def test_building_keeps_independent_mixes_and_rejects_overflow_before_any_floor_is_saved(client):
    floors = [{"label": "Mixed", "layout": {"template_id": "retro_diner", "table_mix": {"two_seat": 2, "four_seat": 1, "six_seat": 1}}},
              {"label": "No seats", "layout": {"template_id": "retro_diner", "table_mix": {}}}]
    preset = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert preset.status_code == 200, preset.text
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Mixed floors", "floors": preset.json()["floors"]})
    assert created.status_code == 200, created.text
    counts = []
    for setup in created.json()["setups"]:
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        counts.append(sum(rack["type"] == "table" for rack in saved["store"]["racks"]))
    assert counts == [4, 0]
    before = client.get(f"/api/projects/{PID}/setups").json()
    floors[1]["layout"] = {"template_id": "retro_diner", "width": 8, "height": 6, "table_rotation": 90, "table_mix": {"six_seat": 1}}
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Bad mix", "floors": floors})
    assert result.status_code == 422, result.text
    assert "No seats" in result.text and "6-seat" in result.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
