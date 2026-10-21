"""An operator edits existing shelf products without replacing a whole slot workbook."""
import pytest
from fastapi.testclient import TestClient
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store

PID, SID = "proj_67916afd", "setup_edit_fixture"
URL = f"/api/projects/{PID}/setups/{SID}/product-edits"


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client:
        store = Store(id="store", name="Offline edit fixture", type="convenience", currency="USD", grid_size=(8, 8), racks=[
            Rack(id="in", type="entrance", shape=[[1]], position=(0, 7)),
            Rack(id="out", type="exit", shape=[[1]], position=(7, 7)),
            Rack(id="checkout", type="counter", shape=[[1]], position=(7, 0)),
            Rack(id="shelf", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
                Slot(block=0, face="N", level=1, items=[
                    SlotItem(sku="A", name="Tea", price=101, regular_price=299, promo="Old", image_url="/photo.png"),
                    SlotItem(sku="B", name="Water", price=303),
                ]),
                Slot(block=0, face="N", level=2, items=[SlotItem(sku="A", name="Tea large", price=202)]),
            ]),
        ])
        source = new_setup_data("Source", None, store.model_dump(mode="json"))
        source["id"] = SID
        write_json(setup_path(PID, SID), source)
        yield client, source


def request(client, edits=None):
    catalog = client.get(URL)
    assert catalog.status_code == 200, catalog.text
    data = catalog.json()
    return {"source_sha256": data["source_sha256"], "currency": data["currency"], "edits": edits or [{"sku": "A", "price": 150}]}


def test_preview_save_and_open_product_variant_preserves_original(workflow):
    client, source = workflow
    body = request(client, [{"sku": "A", "name": "차 café", "price": 150, "promo": ""}])
    preview = client.post(URL + "/preview", json=body)
    assert preview.status_code == 200, preview.text
    report = preview.json()
    assert report["changed_placements"] == 2
    assert report["changes"][0]["before"]["prices"] == [101, 202]
    assert report["changes"][0]["after"]["prices"] == [150]
    saved = client.post(URL + "/save", json={**body, "request_id": "a" * 32})
    assert saved.status_code == 200, saved.text
    draft = read_setup(PID, saved.json()["setup_id"])
    assert draft["parentId"] == SID and draft["status"] == "draft"
    items = draft["store"]["racks"][-1]["slots"]
    assert items[0]["items"][0] == {**source["store"]["racks"][-1]["slots"][0]["items"][0], "name": "차 café", "price": 150, "promo": ""}
    assert items[0]["items"][1] == source["store"]["racks"][-1]["slots"][0]["items"][1]
    assert read_setup(PID, SID) == source
    assert client.get(f"/api/projects/{PID}/setups/{draft['id']}").status_code == 200


@pytest.mark.parametrize("patch", [
    {"price": -1}, {"price": 1.2}, {"price": True}, {"price": "100"},
    {"price": 9_007_199_254_740_992}, {"price": float("nan")}, {"price": float("inf")},
    {"name": ""}, {"name": "   "}, {"name": "x" * 201}, {"promo": "x" * 201},
    {"name": None, "price": None, "promo": None}, {"category": "drinks"},
])
def test_bad_edits_are_rejected_without_changing_source(workflow, patch):
    import json
    client, source = workflow
    body = request(client)
    body["edits"] = [{"sku": "A", **patch}]
    result = client.post(URL + "/preview", content=json.dumps(body), headers={"Content-Type": "application/json"})
    assert result.status_code == 422, result.text
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("edits", [[], [{"sku": "A", "price": 1}] * 2, [{"sku": "", "price": 1}], [{"sku": "missing", "price": 1}], [{"sku": str(i), "price": 1} for i in range(501)]])
def test_empty_duplicate_missing_and_excessive_selection(workflow, edits):
    client, _ = workflow
    body = request(client)
    body["edits"] = edits
    assert client.post(URL + "/preview", json=body).status_code == 422


def test_zero_and_maximum_price_preserve_unedited_mixed_fields(workflow):
    client, source = workflow
    for price in (0, 9_007_199_254_740_991):
        body = request(client, [{"sku": "A", "price": price}])
        report = client.post(URL + "/preview", json=body).json()
        assert report["changes"][0]["after"]["prices"] == [price]
        assert report["changes"][0]["after"]["names"] == ["Tea", "Tea large"]
    assert read_setup(PID, SID) == source


def test_no_op_does_not_create_a_draft(workflow):
    client, _ = workflow
    body = request(client, [{"sku": "B", "price": 303}])
    assert client.post(URL + "/preview", json=body).json()["changes"] == []
    assert client.post(URL + "/save", json={**body, "request_id": "b" * 32}).status_code == 422
    assert not setup_path(PID, "setup_products_" + "b" * 32).exists()


@pytest.mark.parametrize("change", ["price", "currency", "removed", "empty"])
def test_stale_preview_cannot_save_after_source_changes(workflow, change):
    client, source = workflow
    body = request(client)
    assert client.post(URL + "/preview", json=body).status_code == 200
    if change == "removed":
        setup_path(PID, SID).unlink()
    else:
        if change == "price": source["store"]["racks"][-1]["slots"][0]["items"][0]["price"] = 999
        if change == "currency": source["store"]["currency"] = "KRW"
        if change == "empty": source["store"] = None
        write_json(setup_path(PID, SID), source)
    assert client.post(URL + "/save", json={**body, "request_id": "b" * 32}).status_code in (404, 409)
    assert not setup_path(PID, "setup_products_" + "b" * 32).exists()


def test_idempotent_save_does_not_overwrite_later_edits_or_resurrect_a_deleted_draft(workflow):
    client, _ = workflow
    body = {**request(client), "request_id": "c" * 32}
    saved = client.post(URL + "/save", json=body).json()
    path = setup_path(PID, saved["setup_id"])
    draft = read_setup(PID, saved["setup_id"])
    draft["name"] = "Another operator's change"
    write_json(path, draft)
    # Source deletion does not lose an already accepted result.
    setup_path(PID, SID).unlink()
    assert client.post(URL + "/save", json=body).json() == saved
    assert read_setup(PID, saved["setup_id"])["name"] == draft["name"]
    path.unlink()
    assert client.post(URL + "/save", json=body).status_code == 409
    assert not path.exists()


def test_concurrent_saves_and_changed_payload_replay(workflow):
    from concurrent.futures import ThreadPoolExecutor
    client, _ = workflow
    body = {**request(client), "request_id": "d" * 32}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(URL + "/save", json=body), range(2)))
    assert all(r.status_code in (200, 409) for r in responses)
    assert client.post(URL + "/save", json=body).status_code == 200
    assert len(list(setup_path(PID, SID).parent.glob("setup_products_*.json"))) == 1
    body["edits"] = [{"sku": "A", "price": 999}]
    assert client.post(URL + "/save", json=body).status_code == 409


def test_generation_and_interrupted_write_are_explicit(workflow, monkeypatch):
    from store_emulator.application import product_edits
    client, source = workflow
    body = {**request(client), "request_id": "e" * 32}
    monkeypatch.setattr(product_edits, "find_active_generation", lambda *args: {"running": True})
    assert client.post(URL + "/save", json=body).status_code == 409
    monkeypatch.setattr(product_edits, "find_active_generation", lambda *args: None)
    original = product_edits.write_json
    def fail_draft(path, data):
        if path.name.startswith("setup_products_"): raise OSError("disk full")
        original(path, data)
    monkeypatch.setattr(product_edits, "write_json", fail_draft)
    assert client.post(URL + "/save", json=body).status_code == 500
    monkeypatch.setattr(product_edits, "write_json", original)
    assert client.post(URL + "/save", json=body).status_code == 409
    assert read_setup(PID, SID) == source


def test_legacy_currency_and_full_500_sku_edit_boundary(workflow):
    client, source = workflow
    source["store"]["currency"] = None
    source["generation"] = {"currency": "KRW"}
    source["store"]["racks"] = [
        {**source["store"]["racks"][-1], "id": f"rack_{i}", "slots": [
            {"block": 0, "face": "N", "level": 1, "items": [{"sku": f"sku_{i}", "name": "Tea", "price": 1000}]}
        ]} for i in range(500)
    ]
    write_json(setup_path(PID, SID), source)
    body = request(client, [{"sku": f"sku_{i}", "price": 1500} for i in range(500)])
    assert body["currency"] == "KRW"
    preview = client.post(URL + "/preview", json=body)
    assert preview.status_code == 200 and preview.json()["changed_placements"] == 500


def test_registered_product_image_survives_opening_the_saved_variant(workflow):
    import io
    from PIL import Image
    from store_emulator.application.storage.images import save_image
    client, _ = workflow
    image = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(image, format="PNG")
    save_image(PID, "A", image.getvalue(), "fixture.png")
    before = client.get(f"/api/projects/{PID}/setups/{SID}").json()["store"]["racks"][-1]["slots"][0]["items"][0]["image_url"]
    result = client.post(URL + "/save", json={**request(client), "request_id": "f" * 32}).json()
    after = client.get(f"/api/projects/{PID}/setups/{result['setup_id']}").json()["store"]["racks"][-1]["slots"][0]["items"][0]["image_url"]
    assert before and after == before
    assert client.get(after).status_code == 200


@pytest.mark.parametrize("rid", ["../bad", "a" * 31, "a" * 33, "A" * 32])
def test_invalid_save_id_is_rejected(workflow, rid):
    client, _ = workflow
    assert client.post(URL + "/save", json={**request(client), "request_id": rid}).status_code == 422


def test_catalog_limits_skus_and_placements(workflow):
    client, source = workflow
    fixture = source["store"]["racks"][-1]
    source["store"]["racks"] = [{**fixture, "id": f"r_{i}", "slots": [
        {"block": 0, "face": "N", "level": 1, "items": [{"sku": str(i), "name": "Fixture", "price": 1}]}
    ]} for i in range(5001)]
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 413
    source["store"]["racks"].pop()
    write_json(setup_path(PID, SID), source)
    assert len(client.get(URL).json()["products"]) == 5000
    slots = [{"block": 0, "face": face, "level": level, "items": [{"sku": "A", "name": "Fixture", "price": 1}] * 4} for face in "NSEW" for level in range(1, 5)]
    source["store"]["racks"] = [{**fixture, "id": f"r_{i}", "slots": slots} for i in range(781)]
    source["store"]["racks"].append({**fixture, "id": "last", "slots": slots[:4]})
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).json()["products"][0]["placements"] == 50000
    source["store"]["racks"][-1]["slots"] = slots[:5]
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 413


@pytest.mark.parametrize("broken", ["{", "[]"])
def test_corrupt_source_is_reported_without_a_server_crash(workflow, broken):
    client, _ = workflow
    setup_path(PID, SID).write_text(broken)
    response = client.get(URL)
    assert response.status_code == 409
    assert setup_path(PID, SID).read_text() == broken
