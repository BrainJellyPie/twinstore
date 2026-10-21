"""Checkout spacing survives every layout API and rejects invalid saves atomically."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
@pytest.mark.parametrize("clearance", [0, 1, 2, 3])
def test_spacing_get_post_save_reuse_and_options_file(client, wall, clearance):
    body = {"template_id": "hypermarket", "checkouts": 3, "checkout_wall": wall, "checkout_clearance": clearance}
    preview = client.post("/api/store-templates/preview", json=body)
    assert preview.status_code == 200, preview.text
    query = client.get("/api/store-templates/hypermarket/preview", params={key: value for key, value in body.items() if key != "template_id"})
    assert query.status_code == 200 and query.json() == preview.json()
    created = client.post(f"/api/projects/{PID}/setups/generate", json=body)
    assert created.status_code == 200, created.text
    saved = client.get(f"/api/projects/{PID}/setups/{created.json()['id']}").json()
    assert saved["generation"]["checkout_clearance"] == clearance
    assert saved["store"]["racks"] == preview.json()["racks"]
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={**saved["generation"], "source_setup_id": saved["id"]})
    assert reused.status_code == 200, reused.text
    assert client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()["store"]["racks"] == saved["store"]["racks"]
    imported = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body})
    assert imported.status_code == 200 and imported.json()["layout"]["checkout_clearance"] == clearance


@pytest.mark.parametrize("patch", [{"checkout_clearance": -1}, {"checkout_clearance": 4}, {"checkout_clearance": True},
    {"checkout_clearance": 1.5}, {"checkout_clearance": "2"}, {"checkout_clearance": None},
    {"width": 8, "height": 6, "checkout_clearance": 3, "checkouts": 12}])
def test_bad_spacing_or_capacity_does_not_save_or_import(client, patch):
    body = {"template_id": "warehouse_club", **patch}
    before = client.get(f"/api/projects/{PID}/setups").json()
    for endpoint in ["/api/store-templates/preview", f"/api/projects/{PID}/setups/generate"]:
        response = client.post(endpoint, json=body)
        assert response.status_code == 422, response.text
    imported = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": body})
    assert imported.status_code == 422, imported.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before


def test_spacing_building_floors_remain_independent_and_capacity_errors_leave_no_partial_building(client):
    floors = [{"label": "Grocery", "layout": {"template_id": "hypermarket", "checkout_clearance": 3}},
              {"label": "Cafe", "layout": {"template_id": "specialty_cafe", "checkout_clearance": 0}}]
    portable = client.post("/api/store-templates/building-preset/validate", json={"format": "twinstore-building-options", "version": 1, "floors": floors})
    assert portable.status_code == 200, portable.text
    created = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Separate service points", "floors": portable.json()["floors"]})
    assert created.status_code == 200, created.text
    saved = [client.get(f"/api/projects/{PID}/setups/{setup['id']}").json() for setup in created.json()["setups"]]
    assert [setup["generation"]["checkout_clearance"] for setup in saved] == [3, 0]
    before = client.get(f"/api/projects/{PID}/setups").json()
    floors[1]["layout"].update({"width": 8, "height": 6, "checkouts": 12, "checkout_clearance": 3})
    bad = client.post(f"/api/projects/{PID}/setups/generate-building", json={"name": "Invalid service points", "floors": floors})
    assert bad.status_code == 422, bad.text
    assert "Floor 2 (Cafe)" in bad.text and "spacing" in bad.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before
