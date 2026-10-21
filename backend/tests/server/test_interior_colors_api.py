"""Color overrides survive independent floors, portable options and source reuse."""
import pytest
from fastapi.testclient import TestClient
PID = "proj_67916afd"

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client

@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_six_floors_keep_partial_and_extreme_colors_through_save_file_and_reuse(client, currency):
    choices = [None, {}, {"wall": "#ABCDEF"}, {"floor": "#000000", "accent": "#FFFFFF"},
               {"counter": "#123456", "wall": None}, {"wall": "#FFFFFF", "floor": "#FEDCBA", "accent": "#000000", "counter": "#000000"}]
    floors = [{"label": f"Floor {i + 1}", "layout": {"template_id": "specialty_cafe", "currency": currency,
        "design_theme": "coastal" if i % 2 else "retro", "design_colors": colors, "seed": i, "requirements": f"Keep floor {i + 1}"}} for i, colors in enumerate(choices)]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    result = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Custom design", "floors": portable.json()["floors"]})
    assert result.status_code == 200, result.text
    for i, (floor, created) in enumerate(zip(portable.json()["floors"], result.json()["setups"])):
        layout = floor["layout"]
        original = choices[i]
        expected = None if original is None else {key: original.get(key).lower() if original.get(key) else None for key in ["wall", "floor", "accent", "counter"]}
        preview = client.post("/api/store-templates/preview", json=layout)
        assert preview.status_code == 200, preview.text
        saved = client.get(f"/api/projects/{PID}/setups/{created['id']}").json()
        assert saved["store"]["design_colors"] == saved["generation"]["design_colors"] == preview.json()["design_colors"] == expected
        assert saved["store"]["racks"] == preview.json()["racks"]
        exported = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": saved["generation"]})
        assert exported.status_code == 200, exported.text
        reused = client.post(f"/api/projects/{PID}/setups/generate", json={**exported.json()["layout"], "source_setup_id": created["id"], "name": saved["store"]["name"]})
        assert reused.status_code == 200, reused.text
        again = client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()
        assert again["store"] == saved["store"]
        assert again["generation"]["requirements"] == layout["requirements"]

@pytest.mark.parametrize("colors", [{"floor": "#fff"}, {"wall": "#123456\n"}, {"counter": 123456}, {"accent": True}, {"ceiling": "#ffffff"}, "red"])
def test_invalid_color_rejects_preview_import_and_entire_building_without_writes(client, colors):
    good = {"template_id": "urban_cvs"}
    assert client.post(f"/api/projects/{PID}/setups/generate", json=good).status_code == 200
    before = client.get(f"/api/projects/{PID}/setups").json()
    bad = {**good, "design_colors": colors}
    floors = [{"label": "Ground", "layout": good}, {"label": "Upper", "layout": bad}]
    for endpoint, payload in [
        ("/api/store-templates/preview", bad),
        (f"/api/projects/{PID}/setups/generate", bad),
        ("/api/store-templates/preset/validate", {"format": "twinstore-layout-options", "version": 1, "layout": bad}),
        ("/api/store-templates/building-preset/validate", {"format": "twinstore-building-options", "version": 1, "floors": floors}),
        (f"/api/projects/{PID}/setups/generate-building", {"name": "Invalid upper floor", "floors": floors}),
    ]:
        response = client.post(endpoint, json=payload)
        assert response.status_code == 422, response.text
        assert "design_colors" in response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
