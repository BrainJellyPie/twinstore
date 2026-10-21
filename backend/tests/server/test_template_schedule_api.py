"""Preview, saved layouts and portable files keep the same operating schedule."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("open_hour,close_hour,closed", [(0, 24, []), (6, 15, [6, 7]), (23, 24, [1, 2, 3, 4, 5, 6])])
def test_get_post_save_reuse_and_file_share_the_schedule(client, open_hour, close_hour, closed):
    body = {"template_id": "office_lobby", "open_hour": open_hour, "close_hour": close_hour, "closed_days": closed}
    preview = client.get("/api/store-templates/office_lobby/preview", params={
        "open_hour": open_hour, "close_hour": close_hour, "closed_days": ",".join(map(str, closed))})
    assert preview.status_code == 200, preview.text
    post = client.post("/api/store-templates/preview", json=body)
    assert post.status_code == 200, post.text
    assert post.json() == preview.json()
    created = client.post(f"/api/projects/{PID}/setups/generate", json=body)
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/{PID}/setups/{created.json()['id']}").json()
    assert saved["store"]["weekly_schedule"] == post.json()["weekly_schedule"]
    assert all(saved["generation"][key] == value for key, value in body.items())
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200, reused.text
    layout = client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()
    assert layout["store"]["weekly_schedule"] == saved["store"]["weekly_schedule"]
    imported = client.post("/api/store-templates/preset/validate", json={
        "format": "twinstore-layout-options", "version": 1, "layout": layout["generation"]})
    assert imported.status_code == 200, imported.text
    assert all(imported.json()["layout"][key] == value for key, value in body.items())


@pytest.mark.parametrize("patch", [
    {"open_hour": -1}, {"open_hour": 24}, {"open_hour": 1.5}, {"open_hour": True},
    {"close_hour": 0}, {"close_hour": 25}, {"close_hour": 1.5}, {"close_hour": False},
    {"open_hour": 10, "close_hour": 10}, {"open_hour": 22, "close_hour": 6},
    {"open_hour": 22}, {"close_hour": 6}, {"closed_days": [0]}, {"closed_days": [8]},
    {"closed_days": [1, 1]}, {"closed_days": list(range(1, 8))}, {"closed_days": [True]},
])
def test_invalid_schedule_never_saves_or_imports(client, patch):
    body = {"template_id": "office_lobby", **patch}
    before = client.get(f"/api/projects/{PID}/setups").json()
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        response = client.post(endpoint, json=body)
        assert response.status_code == 422, response.text
    response = client.post("/api/store-templates/preset/validate", json={
        "format": "twinstore-layout-options", "version": 1, "layout": body})
    assert response.status_code == 422, response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before


@pytest.mark.parametrize("params", [
    {"open_hour": -1}, {"open_hour": 24}, {"close_hour": 0}, {"close_hour": 25},
    {"open_hour": 10, "close_hour": 10}, {"open_hour": 22}, {"close_hour": 6},
    {"closed_days": "0"}, {"closed_days": "8"}, {"closed_days": "1,1"},
    {"closed_days": "1,2,3,4,5,6,7"}, {"closed_days": "1,"}, {"closed_days": "1.5"},
])
def test_get_preview_rejects_invalid_effective_values_without_server_error(client, params):
    response = client.get("/api/store-templates/office_lobby/preview", params=params)
    assert response.status_code == 422, response.text


def test_building_floors_keep_independent_schedules_and_validation_is_atomic(client):
    floors = [
        {"label": "Ground", "layout": {"template_id": "community_pharmacy", "open_hour": 0, "close_hour": 24, "closed_days": []}},
        {"label": "Cafe", "layout": {"template_id": "specialty_cafe", "open_hour": 6, "close_hour": 14, "closed_days": [6, 7]}},
    ]
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Care and coffee", "floors": floors})
    assert response.status_code == 200, response.text
    for floor, summary in zip(floors, response.json()["setups"]):
        saved = client.get(f"/api/projects/{PID}/setups/{summary['id']}").json()
        assert all(saved["generation"][key] == value for key, value in floor["layout"].items())
    portable = {"format": "twinstore-building-options", "version": 1, "floors": floors}
    assert client.post("/api/store-templates/building-preset/validate", json=portable).status_code == 200
    before = client.get(f"/api/projects/{PID}/setups").json()
    floors[1]["layout"]["close_hour"] = 5
    assert client.post("/api/store-templates/building-preset/validate", json=portable).status_code == 422
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Invalid floor", "floors": floors}).status_code == 422
    assert client.get(f"/api/projects/{PID}/setups").json() == before


def test_catalog_exposes_closed_weekdays_and_old_options_keep_defaults(client):
    catalog = {item["id"]: item for item in client.get("/api/store-templates").json()}
    assert catalog["office_lobby"]["closed_days"] == [6, 7]
    assert catalog["urban_cvs"]["closed_days"] == []
    response = client.get("/api/store-templates/office_lobby/preview")
    assert [day["day"] for day in response.json()["weekly_schedule"] if not day["is_open"]] == [6, 7]
