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
                   density="spacious", entrance="right", checkouts=3, fixture_design="c", design_theme="botanical")
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
    assert saved["store"]["design_theme"] == preview.json()["design_theme"] == "botanical"
    assert "Reserve a quiet corner" in saved["memo"]
    assert saved["generation"]["checkouts"] == 3


@pytest.mark.parametrize("patch", [
    {"width": 7}, {"width": 41}, {"height": 5}, {"height": 41}, {"checkouts": 0},
    {"checkouts": 5}, {"style": "unknown"}, {"density": "unknown"}, {"currency": "INVALID"},
    {"entrance": "roof"}, {"fixture_design": "unknown"}, {"design_theme": "unknown"},
])
def test_invalid_options_rejected_for_preview_and_save(client, patch):
    assert client.get("/api/store-templates/urban_cvs/preview", params=patch).status_code == 422
    assert client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "urban_cvs", **patch}).status_code == 422


def test_unknown_templates_do_not_create_layouts(client):
    assert client.get("/api/store-templates/not-a-format/preview").status_code == 404
    assert client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "not-a-format"}).status_code == 404


def _building():
    return {"name": "Market house", "floors": [
        {"label": "Ground shop", "layout": {"template_id": "fashion_boutique", "style": "free_flow"}},
        {"label": "Upstairs café", "layout": {"template_id": "specialty_cafe", "width": 16, "height": 12, "checkouts": 2}},
    ]}


def test_building_floors_are_linked_but_keep_independent_layouts(client):
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json=_building())
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["setups"]) == 2
    floors = [client.get(f"/api/projects/{PID}/setups/{s['id']}").json() for s in result["setups"]]
    assert floors[0]["building"]["id"] == floors[1]["building"]["id"]
    assert [f["building"]["level"] for f in floors] == [1, 2]
    assert [f["store"]["type"] for f in floors] == ["fashion", "cafe"]
    assert floors[1]["store"]["grid_size"] == [16, 12]
    assert client.get(f"/api/projects/{PID}").json()["state"]["activeSetupId"] == floors[0]["id"]
    assert "no travel between floors" in floors[0]["memo"]


def test_unknown_upper_floor_leaves_no_partial_building(client):
    before = client.get(f"/api/projects/{PID}").json()
    body = _building()
    body["floors"][1]["layout"]["template_id"] = "missing-format"
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json=body)
    assert response.status_code == 404
    after = client.get(f"/api/projects/{PID}").json()
    assert before["setups"] == after["setups"]
    assert before["state"] == after["state"]


@pytest.mark.parametrize("labels", [["Only floor"], ["Floor"] * 2, ["Ground", " ground "], ["", "Upper"], [str(i) for i in range(7)]])
def test_building_requires_two_to_six_uniquely_named_floors(client, labels):
    body = {"name": "Building", "floors": [{"label": label, "layout": {"template_id": "urban_cvs"}} for label in labels]}
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json=body).status_code == 422


def test_building_write_failure_rolls_back_new_floors(client, monkeypatch):
    from store_emulator.application import template_layouts
    from store_emulator.domain.layout_options import BuildingLayoutRequest
    before = client.get(f"/api/projects/{PID}").json()
    write = template_layouts.write_json
    count = 0

    def fail_second_write(path, data):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("disk full")
        write(path, data)

    monkeypatch.setattr(template_layouts, "write_json", fail_second_write)
    with pytest.raises(OSError, match="disk full"):
        template_layouts.create_building_layouts(PID, BuildingLayoutRequest.model_validate(_building()))
    after = client.get(f"/api/projects/{PID}").json()
    assert before["setups"] == after["setups"]
    assert before["state"] == after["state"]


def test_generators_require_project_metadata(client, tmp_path):
    (tmp_path / ".data" / "orphan").mkdir()
    assert client.post("/api/projects/orphan/setups/generate", json={"template_id": "urban_cvs"}).status_code == 404
    assert client.post("/api/projects/orphan/setups/generate-building", json=_building()).status_code == 404


def test_cloned_floor_keeps_its_building_identity(client):
    floors = client.post(f"/api/projects/{PID}/setups/generate-building", json=_building()).json()["setups"]
    copied = client.post(f"/api/projects/{PID}/setups", json={
        "mode": "racks_and_items", "source_setup_id": floors[1]["id"], "name": "Café alternative",
    })
    assert copied.status_code == 200, copied.text
    detail = client.get(f"/api/projects/{PID}/setups/{copied.json()['id']}").json()
    assert detail["building"] == floors[1]["building"]
    assert detail["parentId"] == floors[1]["id"]
    assert detail["generation"]["template_id"] == "specialty_cafe"


def test_long_building_and_floor_names_remain_valid_generation_requests(client):
    from store_emulator.domain.layout_options import TemplateLayoutRequest
    body = {"name": "B" * 160, "floors": [
        {"label": label * 80, "layout": {"template_id": "compact_cvs"}} for label in ("G", "U")
    ]}
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json=body)
    assert response.status_code == 200, response.text
    for floor in response.json()["setups"]:
        setup = client.get(f"/api/projects/{PID}/setups/{floor['id']}").json()
        assert TemplateLayoutRequest.model_validate(setup["generation"]).name == floor["name"]
