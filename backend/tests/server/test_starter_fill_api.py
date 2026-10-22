"""Starter fill from the real HTTP boundary through stored child layouts."""
import pytest
from fastapi.testclient import TestClient
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.rack import BlockFace, Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item

PID, SID = "proj_67916afd", "setup_starter_fixture"
URL = f"/api/projects/{PID}/setups/{SID}/starter-fill"


def mock_auto_model(monkeypatch, during=None):
    from store_emulator.application import starter_fill
    from store_emulator.engine.starter_selection import CategorySelection
    class Model:
        calls = 0
        async def generate_structured_async(self, schema, system, user, **kwargs):
            import json
            self.calls += 1
            data = json.loads(user)
            if during:
                during(self.calls)
            if schema is CategorySelection:
                return schema.model_validate({"groups": [{"category": "home_coffee_tea", "rack_ids": [r["id"] for r in data["racks"]]}]})
            return schema.model_validate({"groups": [{"category": "home_coffee_tea", "skus": [p["sku"] for p in data["categories"]["home_coffee_tea"][:2]]}]})
    model = Model()
    monkeypatch.setattr(starter_fill, "assistive_client", lambda *args: model)
    return model


def automatic_request(client, **patch):
    catalog = client.get(URL).json()
    return {"source_sha256": catalog["source_sha256"], "currency": catalog["currency"], "requirements": "Coffee and tea, no alcohol", "products_per_slot": 2, **patch}


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_auto_selected_products_keep_images_and_roundtrip_without_second_model_call(workflow, monkeypatch, currency):
    client, source = workflow
    source["store"]["currency"] = currency
    write_json(setup_path(PID, SID), source)
    model = mock_auto_model(monkeypatch)
    result = client.post(URL + "/auto-select", json=automatic_request(client))
    assert result.status_code == 200, result.text
    body = result.json()
    assert len(body["assignments"]) == 2 and all(len(r["skus"]) == 2 for r in body["assignments"])
    report = client.post(URL + "/preview", json=body)
    assert report.status_code == 200
    assert all(p["image_url"].startswith("/api/catalog-images/") for r in report.json()["racks"] for p in r["products"])
    saved = client.post(URL + "/save", json={**body, "request_id": "8" * 32})
    assert saved.status_code == 200, saved.text
    assert client.post(URL + "/save", json={**body, "request_id": "8" * 32}).json() == saved.json()
    assert model.calls == 2 and read_setup(PID, SID) == source


@pytest.mark.parametrize("patch", [{"source_sha256": "bad"}, {"currency": "usd"}, {"requirements": "x" * 2001},
    {"model": "x" * 201}, {"products_per_slot": 0}, {"products_per_slot": 5}, {"products_per_slot": True},
    {"products_per_slot": 1.5}, {"products_per_slot": "2"}, {"unknown": 1}])
def test_auto_invalid_input_is_rejected_without_model_call(workflow, monkeypatch, patch):
    client, source = workflow
    model = mock_auto_model(monkeypatch)
    assert client.post(URL + "/auto-select", json=automatic_request(client, **patch)).status_code == 422
    assert model.calls == 0 and read_setup(PID, SID) == source


@pytest.mark.parametrize("when", [0, 1, 2])
def test_auto_rejects_stale_layout_before_or_during_selection(workflow, monkeypatch, when):
    client, source = workflow
    body = automatic_request(client)
    def change(call):
        if call == when:
            source["store"]["name"] = "Changed while choosing"
            write_json(setup_path(PID, SID), source)
    model = mock_auto_model(monkeypatch, change)
    if when == 0:
        change(0)
    response = client.post(URL + "/auto-select", json=body)
    assert response.status_code == 409, response.text
    assert model.calls == (0 if when == 0 else 2)
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("skus", [[], ["missing"], ["a"] * 17, ["a", "a"], [None], "a", [True]])
def test_selected_sku_boundaries_reject_preview_and_save_without_writes(workflow, skus):
    client, source = workflow
    body = request(client, assignments=[{"rack_id": "empty", "category": "home_coffee_tea", "skus": skus}])
    assert client.post(URL + "/preview", json=body).status_code == 422
    assert client.post(URL + "/save", json={**body, "request_id": "9" * 32}).status_code == 422
    assert read_setup(PID, SID) == source
    assert not setup_path(PID, "setup_starter_" + "9" * 32).exists()


def test_auto_model_failure_can_retry_and_does_not_write(workflow, monkeypatch):
    client, source = workflow
    def fail(call):
        raise TimeoutError("model timeout")
    mock_auto_model(monkeypatch, fail)
    response = client.post(URL + "/auto-select", json=automatic_request(client))
    assert response.status_code == 502 and "took too long" in response.text
    assert read_setup(PID, SID) == source
    mock_auto_model(monkeypatch)
    assert client.post(URL + "/auto-select", json=automatic_request(client)).status_code == 200


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client:
        existing = catalog_slot_item(CATALOG["water_sports"][0], "USD")
        existing.name, existing.price, existing.promo, existing.image_url = "My water", 231, "Local", "/photo.png"
        store = Store(id="store", name="Starter fixture", type="convenience", currency="USD", grid_size=(8, 8), racks=[
            Rack(id="in", type="entrance", shape=[[1]], position=(0, 7)),
            Rack(id="out", type="exit", shape=[[1]], position=(7, 7)),
            Rack(id="counter", type="counter", shape=[[1]], position=(7, 0)),
            Rack(id="empty", rack_name="Empty shelf", rack_desc="water_sports", type="shelf", shape=[[1]], position=(3, 3),
                 locked_faces=[BlockFace(block=0, face="N")], slots=[Slot(block=0, face="S", level=1, items=[])]),
            Rack(id="stocked", rack_name="Keep this", type="shelf", shape=[[1]], position=(4, 3),
                 slots=[Slot(block=0, face="S", level=1, items=[existing])]),
            Rack(id="fridge", type="fridge", shape=[[1]], position=(2, 0)),
            Rack(id="table", type="table", shape=[[1]], position=(5, 5)),
        ])
        source = new_setup_data("Source", None, store.model_dump(mode="json")); source["id"] = SID
        write_json(setup_path(PID, SID), source)
        yield client, source


def request(client, **patch):
    response = client.get(URL)
    assert response.status_code == 200, response.text
    data = response.json()
    return {"source_sha256": data["source_sha256"], "currency": data["currency"],
            "assignments": [{"rack_id": "empty", "category": "water_sports"}], "products_per_slot": 2, **patch}


def test_preview_save_open_preserves_stocked_racks_geometry_and_sku_values(workflow):
    client, source = workflow
    catalog = client.get(URL).json()
    assert {r["id"] for r in catalog["racks"]} == {"empty", "stocked", "fridge"}
    assert next(r for r in catalog["racks"] if r["id"] == "stocked")["reason"]
    body = request(client)
    response = client.post(URL + "/preview", json=body)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["placements_added"] == 16 and report["reused_skus"] == 1
    assert report["new_skus"] == 7
    saved = client.post(URL + "/save", json={**body, "request_id": "a" * 32})
    assert saved.status_code == 200, saved.text
    draft = read_setup(PID, saved.json()["setup_id"])
    assert draft["parentId"] == SID and draft["status"] == "draft"
    assert read_setup(PID, SID) == source
    for old, new in zip(source["store"]["racks"], draft["store"]["racks"], strict=True):
        if old["id"] != "empty":
            assert old == new
        else:
            assert {k: v for k, v in old.items() if k != "slots"} == {k: v for k, v in new.items() if k != "slots"}
            assert {s["face"] for s in new["slots"]} == {"S", "W"}
            products = [p for slot in new["slots"] for p in slot["items"]]
            assert len(products) == 16
            local = [p for p in products if p["name"] == "My water"]
            assert local and all(p["price"] == 231 and p["image_url"] == "/photo.png" and p["promo"] == "Local" for p in local)
    assert client.get(f"/api/projects/{PID}/setups/{draft['id']}").status_code == 200


@pytest.mark.parametrize("patch", [
    {"assignments": []}, {"assignments": [{"rack_id": "empty", "category": "water_sports"}] * 2},
    {"assignments": [{"rack_id": str(n), "category": "water_sports"} for n in range(101)]},
    {"assignments": [{"rack_id": "empty", "category": "unknown"}]},
    {"assignments": [{"rack_id": "missing", "category": "water_sports"}]},
    {"assignments": [{"rack_id": "counter", "category": "water_sports"}]},
    {"assignments": [{"rack_id": "stocked", "category": "water_sports"}]},
    *[{"products_per_slot": value} for value in (0, -1, 5, 1.5, True, "2", None)],
    {"currency": "usd"}, {"source_sha256": "bad"}, {"overwrite": True},
])
def test_invalid_or_unsafe_choices_never_change_the_source(workflow, patch):
    client, source = workflow
    response = client.post(URL + "/preview", json=request(client, **patch))
    assert response.status_code == 422, response.text
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("count,expected", [(1, 8), (4, 32)])
def test_density_limits_do_not_duplicate_skus_inside_a_section(workflow, count, expected):
    client, _ = workflow
    body = {**request(client, products_per_slot=count), "request_id": "b" * 32}
    saved = client.post(URL + "/save", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["placements_added"] == expected
    rack = next(r for r in read_setup(PID, saved.json()["setup_id"])["store"]["racks"] if r["id"] == "empty")
    assert all(len(s["items"]) == len({p["sku"] for p in s["items"]}) for s in rack["slots"])


@pytest.mark.parametrize("change", ["stock", "currency", "move", "catalog"])
def test_old_preview_rejects_changed_inputs(workflow, monkeypatch, change):
    client, source = workflow
    body = {**request(client), "request_id": "c" * 32}
    if change == "catalog":
        monkeypatch.setitem(CATALOG, "water_sports", list(reversed(CATALOG["water_sports"])))
    else:
        if change == "stock": source["store"]["racks"][3]["slots"][0]["items"] = [SlotItem(sku="new", name="New", price=0).model_dump()]
        if change == "currency": source["store"]["currency"] = "KRW"
        if change == "move": source["store"]["racks"][3]["position"] = [1, 1]
        write_json(setup_path(PID, SID), source)
    assert client.post(URL + "/preview", json=body | {}).status_code == 422  # save-only ID is not a preview field
    response = client.post(URL + "/save", json=body)
    assert response.status_code == 409, response.text
    assert not setup_path(PID, "setup_starter_" + "c" * 32).exists()


@pytest.mark.parametrize("currency", ["KRW", "JPY"])
def test_reference_currencies_are_explicit_and_rounded(workflow, currency):
    client, source = workflow
    source["store"]["currency"] = currency
    # Keep no existing SKU so this test inspects only catalog reference values.
    source["store"]["racks"][4]["slots"] = []
    write_json(setup_path(PID, SID), source)
    report = client.post(URL + "/preview", json=request(client)).json()
    assert all(p["price"] > 0 and p["price"] % (100 if currency == "KRW" else 10) == 0 for p in report["racks"][0]["products"])


def test_unsupported_currency_and_missing_entrance_are_actionable(workflow):
    client, source = workflow
    source["store"]["currency"] = "EUR"; write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 409
    source["store"]["currency"] = "USD"; source["store"]["racks"] = source["store"]["racks"][1:]
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 422


def test_mixed_existing_sku_values_block_reuse_without_overwriting(workflow):
    client, source = workflow
    slots = source["store"]["racks"][4]["slots"]
    copy = {**slots[0]["items"][0], "price": 999}
    slots.append({"block": 0, "face": "S", "level": 2, "items": [copy]})
    write_json(setup_path(PID, SID), source)
    response = client.post(URL + "/preview", json=request(client))
    assert response.status_code == 422 and "mixed existing values" in response.text
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("kind", ["outside", "overlap"])
def test_invalid_geometry_cannot_receive_starter_products(workflow, kind):
    client, source = workflow
    source["store"]["racks"][3]["position"] = [-1, 3] if kind == "outside" else [4, 3]
    write_json(setup_path(PID, SID), source)
    result = client.get(URL)
    assert result.status_code == 422, result.text[:300]


def test_replay_preserves_newer_saved_edits_and_never_resurrects(workflow):
    client, source = workflow
    body = {**request(client), "request_id": "d" * 32}
    first = client.post(URL + "/save", json=body); assert first.status_code == 200
    path = setup_path(PID, first.json()["setup_id"])
    draft = read_setup(PID, first.json()["setup_id"]); draft["name"] = "A later operator edit"; write_json(path, draft)
    assert client.post(URL + "/save", json=body).json() == first.json()
    assert read_setup(PID, first.json()["setup_id"])["name"] == "A later operator edit"
    assert client.post(URL + "/save", json={**body, "products_per_slot": 3}).status_code == 409
    path.unlink()
    assert client.post(URL + "/save", json=body).status_code == 409 and not path.exists()
    assert read_setup(PID, SID) == source


def test_rotated_multicell_rack_uses_only_exposed_reachable_faces(workflow):
    client, source = workflow
    rack = source["store"]["racks"][3]
    rack.update(shape=[[1, 1]], rotation=90, locked_faces=[], slots=[], rack_name="茶 café", id="棚_한글")
    write_json(setup_path(PID, SID), source)
    body = request(client, assignments=[{"rack_id": "棚_한글", "category": "water_sports"}])
    result = client.post(URL + "/save", json={**body, "request_id": "1" * 32})
    assert result.status_code == 200, result.text
    saved = next(r for r in read_setup(PID, result.json()["setup_id"])["store"]["racks"] if r["id"] == "棚_한글")
    assert saved["rotation"] == 90 and saved["rack_name"] == "茶 café"
    assert not any((slot["block"], slot["face"]) in {(0, "S"), (1, "N"), (0, "E")} for slot in saved["slots"])


def test_fully_locked_and_disconnected_racks_are_not_fillable(workflow):
    client, source = workflow
    source["store"]["racks"][3]["locked_faces"] = [{"block": 0, "face": face} for face in "NSEW"]
    write_json(setup_path(PID, SID), source)
    assert next(r for r in client.get(URL).json()["racks"] if r["id"] == "empty")["available_slots"] == 0
    assert client.post(URL + "/preview", json=request(client)).status_code == 422
    # Wall separates the back half from the entrance without overlapping any fixture.
    source["store"]["racks"][3]["locked_faces"] = []
    source["store"]["racks"].append(Rack(id="wall", type="shelf", shape=[[1] * 8], position=(0, 5)).model_dump(mode="json"))
    source["store"]["racks"] = [r for r in source["store"]["racks"] if r["id"] != "table"]
    write_json(setup_path(PID, SID), source)
    assert next(r for r in client.get(URL).json()["racks"] if r["id"] == "empty")["available_slots"] == 0


def test_same_name_with_a_different_sku_is_not_merged(workflow):
    client, source = workflow
    item = source["store"]["racks"][4]["slots"][0]["items"][0]
    item.update(sku="user-water", name=CATALOG["water_sports"][0].en)
    write_json(setup_path(PID, SID), source)
    report = client.post(URL + "/preview", json=request(client)).json()
    assert report["reused_skus"] == 0 and report["new_skus"] == 8
    assert all(p["sku"] != "user-water" for p in report["racks"][0]["products"])


def test_one_hundred_racks_and_grid_limits(workflow):
    client, source = workflow
    source["store"]["grid_size"] = [256, 256]
    source["store"]["racks"] = source["store"]["racks"][:3] + [
        Rack(id=f"empty_{n}", type="shelf", shape=[[1]], position=(2 + n % 10 * 3, 2 + n // 10 * 3)).model_dump(mode="json")
        for n in range(100)]
    write_json(setup_path(PID, SID), source)
    body = request(client, assignments=[{"rack_id": f"empty_{n}", "category": "water_sports"} for n in range(100)])
    response = client.post(URL + "/preview", json=body)
    assert response.status_code == 200, response.text[:300]
    assert len(response.json()["racks"]) == 100 and response.json()["new_skus"] == 8
    source["store"]["grid_size"] = [257, 256]; write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 422


def test_small_category_avoids_duplicate_products_per_section(workflow, monkeypatch):
    client, _ = workflow
    monkeypatch.setitem(CATALOG, "one", [CATALOG["water_sports"][0]] * 2)
    body = request(client, assignments=[{"rack_id": "empty", "category": "one"}], products_per_slot=4)
    report = client.post(URL + "/preview", json=body).json()
    assert report["placements_added"] == 8 and report["reused_skus"] == 1


def test_building_context_and_replay_after_source_removal(workflow):
    client, source = workflow
    source["building"] = {"id": "building_1", "name": "Mall", "level": 2, "label": "Upper", "floor_count": 2}
    write_json(setup_path(PID, SID), source)
    body = {**request(client), "request_id": "2" * 32}
    first = client.post(URL + "/save", json=body); assert first.status_code == 200, first.text
    assert read_setup(PID, first.json()["setup_id"])["building"] == source["building"]
    setup_path(PID, SID).unlink()
    assert client.post(URL + "/save", json=body).json() == first.json()


def test_active_generation_and_corrupt_source_do_not_save(workflow, monkeypatch):
    from store_emulator.application import product_sources
    client, _ = workflow
    body = {**request(client), "request_id": "3" * 32}
    monkeypatch.setattr(product_sources, "find_active_generation", lambda *args: {"running": True})
    assert client.post(URL + "/save", json=body).status_code == 409
    monkeypatch.setattr(product_sources, "find_active_generation", lambda *args: None)
    setup_path(PID, SID).write_text("{broken")
    assert client.get(URL).status_code == 409
    assert setup_path(PID, SID).read_text() == "{broken"


def test_capacity_rejects_before_constructing_a_large_result(workflow, monkeypatch):
    from store_emulator.engine import starter_fill
    from store_emulator.domain.types import Face
    client, _ = workflow
    body = request(client)
    # Isolate capacity preflight from geometric reachability, which has separate tests above.
    monkeypatch.setattr(starter_fill, "available_faces", lambda store: {"empty": [(i, Face.N) for i in range(7000)]})
    def unexpected_copy(*args, **kwargs): raise AssertionError("large result must not be allocated")
    monkeypatch.setattr(Store, "model_copy", unexpected_copy)
    response = client.post(URL + "/preview", json=body)
    assert response.status_code == 422 and "50,000" in response.text


@pytest.mark.parametrize("size", [1001, 10001])
def test_oversized_rack_counts_and_occupied_cells_are_bounded(workflow, size):
    client, source = workflow
    if size == 1001:
        source["store"]["racks"] += [Rack(id=f"extra_{n}", type="shelf", shape=[[1]], position=(1, 1)).model_dump(mode="json") for n in range(size)]
    else:
        source["store"]["racks"][3]["shape"] = [[1] * size]
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 422


def test_concurrent_retries_create_one_child(workflow):
    from concurrent.futures import ThreadPoolExecutor
    client, _ = workflow
    body = {**request(client), "request_id": "e" * 32}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(URL + "/save", json=body), range(2)))
    assert all(r.status_code in {200, 409} for r in responses)
    assert any(r.status_code == 200 for r in responses)
    assert client.post(URL + "/save", json=body).status_code == 200
    assert len(list(setup_path(PID, SID).parent.glob("setup_starter_" + "e" * 32 + ".json"))) == 1


def test_interrupted_write_keeps_original_and_requires_deliberate_new_preview(workflow, monkeypatch):
    from store_emulator.application import starter_fill
    client, source = workflow
    body = {**request(client), "request_id": "f" * 32}
    real_write = starter_fill.write_json
    def fail_layout(path, data):
        if path.name.startswith("setup_starter_"): raise OSError("Disk full")
        real_write(path, data)
    monkeypatch.setattr(starter_fill, "write_json", fail_layout)
    assert client.post(URL + "/save", json=body).status_code == 500
    monkeypatch.setattr(starter_fill, "write_json", real_write)
    assert client.post(URL + "/save", json=body).status_code == 409
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize('existing_count', [4992, 4993, 5000])
def test_filled_child_stays_within_product_editor_sku_limit(workflow, existing_count):
    client, source = workflow
    # Sixteen different items per rack, with clear aisles and a separate empty shelf.
    racks = [Rack(id='in', type='entrance', shape=[[1]], position=(0, 69)),
             Rack(id='out', type='exit', shape=[[1]], position=(69, 69)),
             Rack(id='counter', type='counter', shape=[[1]], position=(69, 0)),
             Rack(id='empty', type='shelf', shape=[[1]], position=(65, 65))]
    for index, start in enumerate(range(0, existing_count, 16)):
        slots = [Slot(block=0, face='S', level=level + 1,
                      items=[SlotItem(sku=f'custom_{sku}', name=f'Custom {sku}', price=100)
                             for sku in range(start + level * 4, min(start + (level + 1) * 4, existing_count))])
                 for level in range(4) if start + level * 4 < existing_count]
        racks.append(Rack(id=f'stocked_{index}', type='shelf', shape=[[1]],
                          position=(2 + index % 20 * 3, 2 + index // 20 * 3), slots=slots))
    source['store'] = Store(id='large', name='Boundary fixture', type='convenience', currency='USD',
                            grid_size=(70, 70), racks=racks).model_dump(mode='json')
    write_json(setup_path(PID, SID), source)
    body = request(client)
    assert len(CATALOG['water_sports']) == 8
    expected = 200 if existing_count == 4992 else 422
    preview = client.post(URL + '/preview', json=body)
    assert preview.status_code == expected, preview.text[:300]
    saved = client.post(URL + '/save', json={**body, 'request_id': 'e' * 32})
    assert saved.status_code == expected, saved.text[:300]
    if expected == 200:
        from store_emulator.application.product_sources import read_product_source
        child, _ = read_product_source(PID, saved.json()['setup_id'])
        assert len({item.sku for rack in child.racks for slot in rack.slots for item in slot.items}) == 5000
    else:
        assert '5,000' in preview.text and '5,000' in saved.text
        assert not setup_path(PID, 'setup_starter_' + 'e' * 32).exists()
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("stored_kind", ["missing", "custom", "reviewed"])
@pytest.mark.parametrize("uploaded", [False, True])
def test_reused_product_preview_resolves_photos_but_save_preserves_original_values(workflow, currency, stored_kind, uploaded):
    import io
    from PIL import Image
    from store_emulator.application.storage.images import layout_image_url, load_manifest, save_image

    client, source = workflow
    product = next(p for p in CATALOG["pharmacy_care"] if p.en == "Sterile Gauze Pads")
    item = catalog_slot_item(product, currency)
    assert item.image_url
    item.name, item.price = "My own label", 777
    item.image_url = {
        "missing": None,
        "custom": "/custom/selected.png",
        "reviewed": f"/api/projects/{PID}/product-photo-files/" + "a" * 64,
    }[stored_kind]
    source["store"]["currency"] = currency
    source["store"]["racks"][4]["slots"][0]["items"] = [item.model_dump(mode="json")]
    path = setup_path(PID, SID)
    write_json(path, source)
    before = path.read_bytes()
    write_json(path.parent.parent / "metadata.json", {"name": "Photo preview", "currency": currency})
    if uploaded:
        buf = io.BytesIO()
        Image.new("RGB", (40, 60), "red").save(buf, format="PNG")
        save_image(PID, item.sku, buf.getvalue(), "photo.png")
    expected = layout_image_url(PID, item.sku, item.image_url, load_manifest(PID))
    body = request(client, assignments=[{"rack_id": "empty", "category": "pharmacy_care", "skus": [item.sku]}])
    response = client.post(URL + "/preview", json=body)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["reused_skus"] == 1 and report["new_skus"] == 0
    assert report["racks"][0]["products"] == [{**item.model_dump(mode="json"), "image_url": expected}]
    assert path.read_bytes() == before

    saved = client.post(URL + "/save", json={**body, "request_id": "f" * 32})
    assert saved.status_code == 200, saved.text
    child = read_setup(PID, saved.json()["setup_id"])
    placed = next(r for r in child["store"]["racks"] if r["id"] == "empty")
    assert all(p == item.model_dump(mode="json") for s in placed["slots"] for p in s["items"])
    opened = client.get(f"/api/projects/{PID}/setups/{saved.json()['setup_id']}")
    assert opened.status_code == 200, opened.text
    resolved = next(r for r in opened.json()["store"]["racks"] if r["id"] == "empty")
    assert all(p["image_url"] == expected for s in resolved["slots"] for p in s["items"])
    assert path.read_bytes() == before
