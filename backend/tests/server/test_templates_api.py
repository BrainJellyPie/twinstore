"""Preview and save apply the same requirements, with bounded input sizes."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def test_catalog_contains_specialty_formats_and_defaults(client):
    response = client.get("/api/store-templates")
    assert response.status_code == 200
    templates = {t["id"]: t for t in response.json()}
    assert {"hypermarket", "community_pharmacy", "specialty_cafe", "quick_service", "design_showroom"} <= templates.keys()
    assert templates["hypermarket"]["grid"] == [32, 26]
    assert all(t["default_style"] and t["skus"] > 0 for t in templates.values())


def test_preview_matches_saved_custom_store(client):
    options = dict(seed=12, currency="JPY", style="spine", width=28, height=24,
                   density="spacious", entrance="right", checkouts=3, fixture_design="c")
    preview = client.get("/api/store-templates/food_hall/preview", params=options)
    assert preview.status_code == 200, preview.text
    response = client.post(f"/api/projects/{PID}/setups/generate", json={
        **options, "template_id": "food_hall", "name": "Lunch hall", "requirements": "Reserve a quiet corner",
    })
    assert response.status_code == 200, response.text
    saved = client.get(f"/api/projects/{PID}/setups/{response.json()['id']}").json()
    assert saved["store"]["racks"] == preview.json()["racks"]
    assert saved["store"]["grid_size"] == [28, 24]
    assert saved["store"]["name"] == "Lunch hall"
    assert "Reserve a quiet corner" in saved["memo"]
    assert saved["generation"]["checkouts"] == 3


@pytest.mark.parametrize("patch", [
    {"width": 7}, {"width": 41}, {"height": 5}, {"height": 41}, {"checkouts": 0},
    {"checkouts": 5}, {"style": "unknown"}, {"density": "unknown"}, {"currency": "INVALID"},
    {"entrance": "roof"}, {"fixture_design": "unknown"},
])
def test_invalid_options_rejected_for_preview_and_save(client, patch):
    assert client.get("/api/store-templates/urban_cvs/preview", params=patch).status_code == 422
    assert client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "urban_cvs", **patch}).status_code == 422


def test_unknown_templates_do_not_create_layouts(client):
    assert client.get("/api/store-templates/not-a-format/preview").status_code == 404
    assert client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "not-a-format"}).status_code == 404
