"""Portable generation settings validate without creating or linking layouts."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    return TestClient(app)


def preset(**options):
    return {"format": "twinstore-layout-options", "version": 1,
            "layout": {"template_id": "community_pharmacy", **options}}


def test_import_normalizes_options_without_writes_and_can_generate_in_another_project(client, tmp_path):
    body = preset(width="24", height=20, seed="7", currency="JPY", style="cross",
                  aisle_width=3, max_shelf_run=2, shelf_direction="vertical", design_theme="terracotta",
                  dining_tables=2, table_clearance=2, seating_zone="back", exit_position="right",
                  reserved_areas=[{"label": " Consultation ", "x": 2, "y": 2, "width": 3, "height": 3}],
                  requirements="Keep consultation signs readable.", source_setup_id="setup_other_project",
                  name="Old project floor", products_per_category=3)
    response = client.post("/api/store-templates/preset/validate", json=body)
    assert response.status_code == 200, response.text
    assert list(tmp_path.iterdir()) == []
    layout = response.json()["layout"]
    assert layout["width"] == 24
    assert layout["seed"] == 7
    assert layout["reserved_areas"][0]["label"] == "Consultation"
    assert layout["density"] == "balanced"
    assert layout["requirements"] == body["layout"]["requirements"]
    assert "source_setup_id" not in layout
    assert "name" not in layout
    preview = client.post("/api/store-templates/preview", json=layout)
    assert preview.status_code == 200, preview.text

    write_json(tmp_path / ".data" / "proj_destination" / "metadata.json", {"currency": "JPY", "name": "Destination"})
    created = client.post("/api/projects/proj_destination/setups/generate", json={**layout, "name": "Imported floor"})
    assert created.status_code == 200, created.text
    assert created.json()["parentId"] is None
    saved = client.get(f"/api/projects/proj_destination/setups/{created.json()['id']}").json()
    assert saved["store"]["racks"] == preview.json()["racks"]
    assert saved["store"]["currency"] == "JPY"
    assert saved["store"]["design_theme"] == "terracotta"
    assert saved["generation"]["reserved_areas"] == layout["reserved_areas"]
    assert saved["generation"]["requirements"] == layout["requirements"]
    assert saved["generation"]["products_per_category"] == layout["products_per_category"] == 3


@pytest.mark.parametrize("body,status", [
    ({**preset(), "version": 2}, 422),
    ({**preset(), "format": "unrelated-json"}, 422),
    ({**preset(), "building": {}}, 422),
    (preset(template_id="missing-format"), 404),
    (preset(width=7), 422),
    (preset(width=8, height=6, dining_tables=48), 422),
    (preset(reserved_areas=[{"label": "Outside", "x": 38, "y": 38, "width": 3, "height": 3}]), 422),
    (preset(unknown_option=True), 422),
])
def test_invalid_files_do_not_create_any_files(client, tmp_path, body, status):
    response = client.post("/api/store-templates/preset/validate", json=body)
    assert response.status_code == status, response.text
    assert list(tmp_path.iterdir()) == []


def test_building_file_keeps_floor_order_and_settings_without_source_links(client, tmp_path):
    floors = [
        {"label": " Ground · Pharmacy ", "layout": preset(currency="KRW", source_setup_id="old_pharmacy", excluded_categories=["wellness"], checkout_wall="left", products_per_category=2)["layout"]},
        {"label": "Upstairs · Tea", "layout": preset(template_id="tea_lounge", dining_tables=4, design_theme="coastal",
            requirements="Quiet seating by the windows.", name="Old tea floor", currency="JPY", products_per_category=6)["layout"]},
    ]
    response = client.post("/api/store-templates/building-preset/validate", json={
        "format": "twinstore-building-options", "version": 1, "floors": floors,
    })
    assert response.status_code == 200, response.text
    assert list(tmp_path.iterdir()) == []
    validated = response.json()["floors"]
    assert [f["label"] for f in validated] == ["Ground · Pharmacy", "Upstairs · Tea"]
    assert [f["layout"]["currency"] for f in validated] == ["KRW", "JPY"]
    assert validated[0]["layout"]["excluded_categories"] == ["wellness"]
    assert validated[0]["layout"]["checkout_wall"] == "left"
    assert all("source_setup_id" not in f["layout"] and "name" not in f["layout"] for f in validated)
    assert validated[1]["layout"]["requirements"] == "Quiet seating by the windows."
    write_json(tmp_path / ".data" / "proj_building" / "metadata.json", {"currency": "KRW", "name": "New building"})
    generated = client.post("/api/projects/proj_building/setups/generate-building", json={"name": "Imported building", "floors": validated})
    assert generated.status_code == 200, generated.text
    for index, summary in enumerate(generated.json()["setups"]):
        saved = client.get(f"/api/projects/proj_building/setups/{summary['id']}").json()
        assert saved["parentId"] is None
        assert saved["building"]["label"] == validated[index]["label"]
        assert saved["building"]["level"] == index + 1
        assert saved["store"]["currency"] == validated[index]["layout"]["currency"]
        assert saved["generation"]["excluded_categories"] == validated[index]["layout"]["excluded_categories"]
        assert saved["generation"]["checkout_wall"] == validated[index]["layout"]["checkout_wall"]
        assert saved["generation"]["products_per_category"] == validated[index]["layout"]["products_per_category"] == [2, 6][index]


@pytest.mark.parametrize("labels", [["One"], [str(i) for i in range(7)], ["Ground", " ground "], ["", "Tea"]])
def test_building_file_requires_two_to_six_uniquely_named_floors(client, tmp_path, labels):
    response = client.post("/api/store-templates/building-preset/validate", json={
        "format": "twinstore-building-options", "version": 1,
        "floors": [{"label": label, "layout": preset()["layout"]} for label in labels],
    })
    assert response.status_code == 422, response.text
    assert list(tmp_path.iterdir()) == []


def test_building_import_reports_which_floor_cannot_fit_without_writes(client, tmp_path):
    response = client.post("/api/store-templates/building-preset/validate", json={
        "format": "twinstore-building-options", "version": 1, "floors": [
            {"label": "Shop", "layout": preset()["layout"]},
            {"label": "Dining", "layout": preset(width=8, height=6, dining_tables=48)["layout"]},
        ],
    })
    assert response.status_code == 422, response.text
    assert "Floor 2 (Dining)" in response.json()["detail"]
    assert list(tmp_path.iterdir()) == []
