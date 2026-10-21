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
    assert templates["hypermarket"]["default_checkouts"] == 6
    assert templates["warehouse_club"]["default_checkouts"] == 8
    assert templates["food_hall"]["default_checkouts"] == 4
    assert templates["campus_dining_hall"]["default_dining_tables"] == 24
    assert templates["campus_dining_hall"]["grid"] == [32, 24]
    assert {"shoe_boutique", "baby_family_store", "travel_essentials"} <= templates.keys()
    assert templates["shoe_boutique"]["default_style"] == "showroom"
    assert templates["baby_family_store"]["default_design"] == "warm"
    assert templates["travel_essentials"]["default_checkout_placement"] == "near_entrance"
    assert templates["garden_center"]["default_style"] == templates["art_craft_store"]["default_style"] == "cross"
    assert templates["garden_center"]["default_checkouts"] == 4
    assert {"optical_shop", "jewelry_boutique", "music_store", "fashion_outlet"} <= templates.keys()
    assert templates["fashion_outlet"]["grid"] == [32, 24]
    assert templates["fashion_outlet"]["default_checkouts"] == 4
    assert templates["music_store"]["default_style"] == "free_flow"
    assert {"pizzeria", "sushi_shop", "noodle_bar", "juice_bar"} <= templates.keys()
    assert templates["pizzeria"]["default_dining_tables"] == 8
    assert templates["sushi_shop"]["default_style"] == "showroom"
    assert templates["noodle_bar"]["default_seating_zone"] == "left"
    assert templates["juice_bar"]["default_checkout_placement"] == "near_entrance"
    assert {"korean_restaurant", "burger_shop", "salad_cafe", "ice_cream_parlor"} <= templates.keys()
    assert templates["korean_restaurant"]["default_dining_tables"] == 12
    assert templates["burger_shop"]["default_checkouts"] == 3
    assert templates["salad_cafe"]["default_style"] == "free_flow"
    assert templates["ice_cream_parlor"]["default_design"] == "coastal"
    assert {"family_restaurant", "neighborhood_bistro", "takeaway_coffee", "tea_lounge", "artisan_bakery",
            "vintage_boutique", "hardware_store", "toy_hobby_store"} <= templates.keys()
    assert templates["family_restaurant"]["default_seating_zone"] == "center"
    assert templates["takeaway_coffee"]["default_checkout_placement"] == "near_entrance"
    assert templates["vintage_boutique"]["default_design"] == "warm"
    assert all(t["default_style"] and t["skus"] > 0 for t in templates.values())


@pytest.mark.parametrize("theme", ["botanical", "coastal", "terracotta"])
@pytest.mark.parametrize("wall", ["front", "back", "left", "right"])
def test_preview_matches_saved_custom_store(client, theme, wall):
    options = dict(seed=12, currency="JPY", style="spine", width=28, height=24,
                   density="spacious", aisle_width=4, max_shelf_run=8, entrance="right", exit_position="center", checkouts=3, checkout_placement="away_from_entrance",
                   fixture_design="c", design_theme=theme, dining_tables=7, table_clearance=2, seating_zone="center", shelf_direction="vertical", checkout_wall=wall, products_per_category=3, gate_wall="back", exit_wall=wall)
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
    assert saved["store"]["currency"] == preview.json()["currency"] == "JPY"
    assert saved["store"]["design_theme"] == preview.json()["design_theme"] == theme
    assert "Reserve a quiet corner" in saved["memo"]
    assert saved["generation"]["checkouts"] == 3
    assert saved["generation"]["dining_tables"] == 7
    assert saved["generation"]["table_clearance"] == 2
    assert saved["generation"]["seating_zone"] == "center"
    assert saved["generation"]["checkout_placement"] == "away_from_entrance"
    assert saved["generation"]["checkout_wall"] == wall
    assert saved["generation"]["shelf_direction"] == "vertical"
    assert saved["generation"]["aisle_width"] == 4
    assert saved["generation"]["max_shelf_run"] == 8
    assert saved["generation"]["products_per_category"] == 3
    assert saved["generation"]["gate_wall"] == "back"
    assert saved["generation"]["exit_wall"] == wall
    assert saved["generation"]["exit_position"] == "center"
    assert sum(r["type"] == "table" for r in saved["store"]["racks"]) == 7


@pytest.mark.parametrize("patch", [
    {"width": 7}, {"width": 41}, {"height": 5}, {"height": 41}, {"checkouts": 0},
    {"checkouts": 13}, {"style": "unknown"}, {"density": "unknown"}, {"currency": "INVALID"},
    {"entrance": "roof"}, {"exit_position": "roof"}, {"fixture_design": "unknown"}, {"design_theme": "unknown"},
    {"dining_tables": -1}, {"dining_tables": 49}, {"table_clearance": 0}, {"table_clearance": 4},
    {"seating_zone": "roof"}, {"checkout_placement": "outside"}, {"checkout_wall": "roof"}, {"shelf_direction": "diagonal"},
    {"aisle_width": 0}, {"aisle_width": 5}, {"aisle_width": 1.5},
    {"max_shelf_run": 0}, {"max_shelf_run": 9}, {"max_shelf_run": 1.5},
    {"products_per_category": 0}, {"products_per_category": 17}, {"products_per_category": 1.5},
    {"gate_wall": "roof"}, {"exit_wall": "roof"},
])
def test_invalid_options_rejected_for_preview_and_save(client, patch):
    assert client.get("/api/store-templates/urban_cvs/preview", params=patch).status_code == 422
    assert client.post("/api/store-templates/preview", json={"template_id": "urban_cvs", **patch}).status_code == 422
    assert client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "urban_cvs", **patch}).status_code == 422


def test_unknown_templates_do_not_create_layouts(client):
    assert client.get("/api/store-templates/not-a-format/preview").status_code == 404
    assert client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "not-a-format"}).status_code == 404


@pytest.mark.parametrize("template_id,store_type", [
    ("shoe_boutique", "fashion"), ("baby_family_store", "baby"), ("travel_essentials", "travel"),
    ("garden_center", "garden"), ("art_craft_store", "crafts"),
    ("optical_shop", "eyewear"), ("jewelry_boutique", "jewelry"), ("music_store", "music"), ("fashion_outlet", "fashion"),
    ("pizzeria", "restaurant"), ("sushi_shop", "restaurant"), ("noodle_bar", "restaurant"), ("juice_bar", "cafe"),
    ("korean_restaurant", "restaurant"), ("burger_shop", "restaurant"), ("salad_cafe", "cafe"), ("ice_cream_parlor", "cafe"),
])
def test_specialty_formats_preview_and_save_with_custom_space(client, template_id, store_type):
    options = {"template_id": template_id, "width": 18, "height": 14, "shelf_direction": "vertical",
               "reserved_areas": [{"label": "Customer assistance", "x": 4, "y": 4, "width": 3, "height": 3}]}
    preview = client.post("/api/store-templates/preview", json=options)
    assert preview.status_code == 200, preview.text
    generated = client.post(f"/api/projects/{PID}/setups/generate", json=options)
    assert generated.status_code == 200, generated.text
    saved = client.get(f"/api/projects/{PID}/setups/{generated.json()['id']}").json()
    assert saved["store"]["type"] == store_type
    assert saved["store"]["racks"] == preview.json()["racks"]
    assert saved["generation"]["reserved_areas"] == options["reserved_areas"]


def test_reserved_area_preview_save_and_reuse_keep_identical_geometry(client):
    options = {"template_id": "community_pharmacy", "width": 20, "height": 16, "seed": 3, "style": "cross", "shelf_direction": "vertical", "aisle_width": 4, "max_shelf_run": 1, "dining_tables": 2, "table_clearance": 2, "exit_position": "right", "exit_wall": "back",
               "reserved_areas": [{"label": "Consultation", "x": 2, "y": 2, "width": 4, "height": 3}]}
    before = client.get(f"/api/projects/{PID}").json()
    preview = client.post("/api/store-templates/preview", json=options)
    assert preview.status_code == 200, preview.text
    assert client.get(f"/api/projects/{PID}").json() == before  # Preview does not create a layout.
    generated = client.post(f"/api/projects/{PID}/setups/generate", json=options)
    assert generated.status_code == 200, generated.text
    saved = client.get(f"/api/projects/{PID}/setups/{generated.json()['id']}").json()
    assert saved["store"]["racks"] == preview.json()["racks"]
    assert saved["generation"]["reserved_areas"] == options["reserved_areas"]
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={
        **saved["generation"], "source_setup_id": saved["id"], "name": "Alternative",
    })
    assert reused.status_code == 200, reused.text
    alternative = client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()
    assert alternative["store"]["racks"] == saved["store"]["racks"]
    assert alternative["generation"]["reserved_areas"] == options["reserved_areas"]
    assert alternative["generation"]["shelf_direction"] == "vertical"
    assert alternative["generation"]["aisle_width"] == 4
    assert alternative["generation"]["max_shelf_run"] == 1
    assert alternative["generation"]["style"] == "cross"
    assert alternative["generation"]["table_clearance"] == 2
    assert alternative["generation"]["exit_position"] == "right"
    assert alternative["generation"]["exit_wall"] == "back"
    assert client.get(f"/api/projects/{PID}/setups/{saved['id']}").json() == saved


@pytest.mark.parametrize("patch", [
    {"x": 0}, {"y": -1}, {"width": 0}, {"height": 39}, {"label": " "},
    {"label": "A" * 81}, {"x": 30}, {"y": 30},
])
def test_invalid_reservations_reject_preview_and_leave_no_partial_building(client, patch):
    area = {"label": "Pickup", "x": 2, "y": 2, "width": 3, "height": 3, **patch}
    layout = {"template_id": "community_pharmacy", "reserved_areas": [area]}
    assert client.post("/api/store-templates/preview", json=layout).status_code == 422
    before = client.get(f"/api/projects/{PID}").json()
    body = _building()
    body["floors"][1]["layout"] = layout
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json=body).status_code == 422
    assert client.get(f"/api/projects/{PID}").json() == before


def test_reservation_count_is_bounded_and_post_preview_requires_a_known_template(client):
    options = {"template_id": "community_pharmacy", "reserved_areas": [
        {"label": "Pickup", "x": 2, "y": 2, "width": 1, "height": 1},
    ] * 9}
    assert client.post("/api/store-templates/preview", json=options).status_code == 422
    assert client.post(f"/api/projects/{PID}/setups/generate", json=options).status_code == 422
    assert client.post("/api/store-templates/preview", json={"template_id": "missing"}).status_code == 404


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


def test_garden_craft_and_cafe_building_keeps_each_floor_pattern_and_assortment(client):
    body = {"name": "Creative living", "floors": [
        {"label": "Garden", "layout": {"template_id": "garden_center", "aisle_width": 4, "max_shelf_run": 2}},
        {"label": "Crafts", "layout": {"template_id": "art_craft_store"}},
        {"label": "Café", "layout": {"template_id": "specialty_cafe"}},
    ]}
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json=body)
    assert response.status_code == 200, response.text
    for summary, requested in zip(response.json()["setups"], body["floors"], strict=True):
        saved = client.get(f"/api/projects/{PID}/setups/{summary['id']}").json()
        preview = client.post("/api/store-templates/preview", json=requested["layout"])
        assert preview.status_code == 200, preview.text
        assert saved["store"]["racks"] == preview.json()["racks"]
        assert saved["building"]["label"] == requested["label"]
        assert saved["generation"]["aisle_width"] == requested["layout"].get("aisle_width")
        assert saved["generation"]["max_shelf_run"] == requested["layout"].get("max_shelf_run")


def test_campus_building_can_save_and_reuse_a_48_table_dining_floor(client):
    layout = {"template_id": "campus_dining_hall", "width": 40, "height": 40,
              "dining_tables": 48, "table_clearance": 3}
    preview = client.post("/api/store-templates/preview", json=layout)
    assert preview.status_code == 200, preview.text
    body = {"name": "Campus hub", "floors": [
        {"label": "Store", "layout": {"template_id": "campus_cvs"}},
        {"label": "Books", "layout": {"template_id": "bookstore"}},
        {"label": "Dining", "layout": layout},
    ]}
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json=body)
    assert response.status_code == 200, response.text
    floor = response.json()["setups"][2]
    source = client.get(f"/api/projects/{PID}/setups/{floor['id']}").json()
    assert source["store"]["racks"] == preview.json()["racks"]
    assert sum(r["type"] == "table" for r in source["store"]["racks"]) == 48
    alternative = client.post(f"/api/projects/{PID}/setups/generate", json={
        **source["generation"], "source_setup_id": floor["id"], "name": "Dining alternative",
    })
    assert alternative.status_code == 200, alternative.text
    saved = client.get(f"/api/projects/{PID}/setups/{alternative.json()['id']}").json()
    assert saved["store"]["racks"] == source["store"]["racks"]
    assert saved["building"] == source["building"]


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


def test_oversized_seating_rejects_preview_and_entire_building(client):
    options = {"template_id": "specialty_cafe", "width": 8, "height": 6, "dining_tables": 2}
    preview = client.get("/api/store-templates/specialty_cafe/preview", params=options)
    assert preview.status_code == 422 and "at most 1" in preview.json()["detail"]
    before = client.get(f"/api/projects/{PID}").json()
    body = _building()
    body["floors"][1]["layout"] = options
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json=body).status_code == 422
    assert client.get(f"/api/projects/{PID}").json() == before


def test_checkout_capacity_rejects_preview_and_entire_building(client):
    options = {"template_id": "warehouse_club", "width": 8, "height": 6,
               "entrance": "center", "exit_position": "right", "checkouts": 5}
    preview = client.post("/api/store-templates/preview", json=options)
    assert preview.status_code == 422 and "at most 4 checkout counters" in preview.json()["detail"]
    before = client.get(f"/api/projects/{PID}").json()
    body = _building()
    body["floors"][1]["layout"] = options
    assert client.post(f"/api/projects/{PID}/setups/generate-building", json=body).status_code == 422
    assert client.get(f"/api/projects/{PID}").json() == before


@pytest.mark.parametrize("count", [None, 1, 12])
def test_large_checkout_defaults_and_explicit_counts_match_preview_save_and_reuse(client, count):
    options = {"template_id": "hypermarket", "checkouts": count}
    preview = client.post("/api/store-templates/preview", json=options)
    assert preview.status_code == 200, preview.text
    original = client.post(f"/api/projects/{PID}/setups/generate", json=options).json()
    source = client.get(f"/api/projects/{PID}/setups/{original['id']}").json()
    assert source["store"]["racks"] == preview.json()["racks"]
    assert sum(r["type"] == "counter" for r in source["store"]["racks"]) == (6 if count is None else count)
    reused = client.post(f"/api/projects/{PID}/setups/generate", json={
        **source["generation"], "source_setup_id": original["id"], "name": "Checkout alternative",
    })
    assert reused.status_code == 200, reused.text
    saved = client.get(f"/api/projects/{PID}/setups/{reused.json()['id']}").json()
    assert saved["store"]["racks"] == source["store"]["racks"]
    assert saved["generation"]["checkouts"] == count


def test_dining_tables_can_be_edited_and_saved_without_product_faces(client):
    result = client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "specialty_cafe"}).json()
    url = f"/api/projects/{PID}/setups/{result['id']}"
    detail = client.get(url).json()
    store = detail["store"]
    # Use the existing floor-edit unlock flow before changing any fixture.
    for rack in store["racks"]:
        for slot in rack["slots"]:
            slot["items"] = []
    unlocked = client.put(url, json={"setup": {"store": store}})
    assert unlocked.status_code == 200, unlocked.text
    table = next(r for r in store["racks"] if r["type"] == "table")
    assert not any(face["rack_id"] == table["id"] for face in detail["blocked_faces"])
    table["rack_name"] = "Window table"
    table["rotation"] = 90
    response = client.put(url, json={"setup": {"store": store}})
    assert response.status_code == 200, response.text
    assert response.json()["issues"] == []
    saved = client.get(url).json()["store"]
    assert next(r for r in saved["racks"] if r["id"] == table["id"])["rack_name"] == "Window table"


def test_reused_generation_creates_a_linked_alternative_without_changing_source(client):
    original = client.post(f"/api/projects/{PID}/setups/generate", json={
        "template_id": "book_cafe", "width": 18, "height": 14, "design_theme": "warm", "dining_tables": 3,
        "requirements": "Quiet reading corner", "seed": 7,
    }).json()
    source_url = f"/api/projects/{PID}/setups/{original['id']}"
    before = client.get(source_url).json()
    summaries = client.get(f"/api/projects/{PID}/setups").json()
    settings = next(s for s in summaries if s["id"] == original["id"])["generation"]
    assert settings == before["generation"]
    result = client.post(f"/api/projects/{PID}/setups/generate", json={
        **settings, "source_setup_id": original["id"], "name": "More seating", "dining_tables": 5,
    })
    assert result.status_code == 200, result.text
    assert result.json()["parentId"] == original["id"]
    assert client.get(source_url).json() == before
    alternative = client.get(f"/api/projects/{PID}/setups/{result.json()['id']}").json()
    assert alternative["generation"]["requirements"] == "Quiet reading corner"
    assert alternative["store"]["design_theme"] == "warm"
    assert sum(r["type"] == "table" for r in alternative["store"]["racks"]) == 5


def test_generated_floor_alternative_keeps_building_identity(client):
    source = client.post(f"/api/projects/{PID}/setups/generate-building", json=_building()).json()["setups"][1]
    result = client.post(f"/api/projects/{PID}/setups/generate", json={
        **source["generation"], "source_setup_id": source["id"], "name": "More open upstairs", "density": "spacious",
    })
    assert result.status_code == 200, result.text
    assert result.json()["parentId"] == source["id"]
    assert result.json()["building"] == source["building"]


@pytest.mark.parametrize("source,status", [("setup_missing", 404), ("../outside", 422), ("", 422)])
def test_invalid_generation_source_writes_nothing(client, source, status):
    before = client.get(f"/api/projects/{PID}").json()
    result = client.post(f"/api/projects/{PID}/setups/generate", json={
        "template_id": "specialty_cafe", "source_setup_id": source,
    })
    assert result.status_code == status
    assert client.get(f"/api/projects/{PID}").json() == before


def test_reused_building_can_reorder_and_duplicate_floors_without_changing_sources(client):
    original = client.post(f"/api/projects/{PID}/setups/generate-building", json=_building()).json()["setups"]
    before = [client.get(f"/api/projects/{PID}/setups/{floor['id']}").json() for floor in original]
    sources = [original[1], original[0], original[1]]
    body = {"name": "Market alternative", "floors": [
        {"label": label, "layout": {**source["generation"], "source_setup_id": source["id"]}}
        for label, source in zip(["Café downstairs", "Shop upstairs", "Extra café"], sources)
    ]}
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json=body)
    assert response.status_code == 200, response.text
    floors = response.json()["setups"]
    assert [floor["parentId"] for floor in floors] == [source["id"] for source in sources]
    assert len({floor["building"]["id"] for floor in floors}) == 1
    assert floors[0]["building"]["id"] != original[0]["building"]["id"]
    assert [floor["building"]["level"] for floor in floors] == [1, 2, 3]
    assert all(floor["building"]["floor_count"] == 3 for floor in floors)
    assert [client.get(f"/api/projects/{PID}/setups/{floor['id']}").json() for floor in original] == before


def test_missing_source_in_reused_building_leaves_no_partial_floors(client):
    body = _building()
    body["floors"][1]["layout"]["source_setup_id"] = "setup_missing"
    before = client.get(f"/api/projects/{PID}").json()
    response = client.post(f"/api/projects/{PID}/setups/generate-building", json=body)
    assert response.status_code == 404
    assert client.get(f"/api/projects/{PID}").json() == before
