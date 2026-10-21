"""New palettes retain their identity in catalogs, files and multi-floor layouts."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def test_design_building_defaults_and_swapped_overrides_survive_files_and_save(client):
    catalog = {row["id"]: row for row in client.get("/api/store-templates").json()}
    assert catalog["nordic_lifestyle"]["default_design"] == "nordic"
    assert catalog["retro_diner"]["default_design"] == "retro"
    assert catalog["retro_diner"]["default_dining_tables"] == 6
    floors = [{"label": "Shop", "layout": {"template_id": "nordic_lifestyle", "design_theme": "retro"}},
              {"label": "Diner", "layout": {"template_id": "retro_diner", "design_theme": "nordic", "dining_seats": 2, "table_rotation": 90}}]
    preset = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert preset.status_code == 200, preset.text
    assert [floor["layout"]["design_theme"] for floor in preset.json()["floors"]] == ["retro", "nordic"]
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Design & dining", "floors": preset.json()["floors"]})
    assert created.status_code == 200, created.text
    for setup, theme in zip(created.json()["setups"], ["retro", "nordic"], strict=True):
        saved = client.get(f"/api/projects/{PID}/setups/{setup['id']}").json()
        assert saved["store"]["design_theme"] == saved["generation"]["design_theme"] == theme
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
        assert reused.status_code == 200, reused.text
        assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"]["design_theme"] == theme
