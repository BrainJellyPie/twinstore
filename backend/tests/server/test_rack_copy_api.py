"""Rack reuse through the real HTTP, geometry, storage and idempotency layers."""
import pytest
from fastapi.testclient import TestClient
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store

PID, SID = "proj_67916afd", "setup_copy_fixture"
URL = f"/api/projects/{PID}/setups/{SID}/rack-copy"


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client:
        store = Store(id="store", name="Reuse fixture", type="convenience", currency="USD", grid_size=(12, 12), racks=[
            Rack(id="in", type="entrance", shape=[[1]], position=(0, 11)),
            Rack(id="out", type="exit", shape=[[1]], position=(11, 11)),
            Rack(id="source", rack_name="茶 café", type="shelf", shape=[[1]], position=(2, 2), slots=[
                Slot(block=0, face="S", level=1, items=[SlotItem(sku="茶_한글", name="Tea", price=231, regular_price=299, promo="Local", image_url="/photo.png"), SlotItem(sku="zero", name="Sample", price=0)]),
                Slot(block=0, face="W", level=4, items=[SlotItem(sku="other", name="Other", price=999)])]),
            Rack(id="empty", rack_name="Empty shelf", type="shelf", shape=[[1]], position=(5, 2), slots=[Slot(block=0, face="N", level=2, items=[])]),
            Rack(id="empty2", type="shelf", shape=[[1]], position=(8, 2)),
            Rack(id="fridge", type="fridge", shape=[[1]], position=(2, 6)),
        ])
        source = new_setup_data("Source", None, store.model_dump(mode="json")); source["id"] = SID
        write_json(setup_path(PID, SID), source)
        yield client, source


def request(client, **patch):
    response = client.get(URL, params={"source_rack_id": "source"})
    assert response.status_code == 200, response.text
    return {"source_sha256": response.json()["source_sha256"], "currency": "USD", "source_rack_id": "source", "target_rack_ids": ["empty", "empty2"], **patch}


def test_choose_preview_save_open_exact_products_and_preserve_original(workflow):
    client, source = workflow
    options = client.get(URL).json()
    assert options["source_rack_id"] is None and options["targets"] == []
    assert options["sources"][0]["placements"] == 3
    body = request(client)
    preview = client.post(URL + "/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["placements_added"] == 6
    saved = client.post(URL + "/save", json={**body, "request_id": "a" * 32})
    assert saved.status_code == 200, saved.text
    draft = read_setup(PID, saved.json()["setup_id"])
    assert draft["parentId"] == SID and draft["status"] == "draft"
    original = source["store"]["racks"][2]
    for old, new in zip(source["store"]["racks"], draft["store"]["racks"], strict=True):
        if old["id"] in body["target_rack_ids"]:
            assert {k: v for k, v in new.items() if k != "slots"} == {k: v for k, v in old.items() if k != "slots"}
            assert [s for s in new["slots"] if s["items"]] == original["slots"]
            assert all(s in new["slots"] for s in old["slots"])
        else:
            assert old == new
    assert read_setup(PID, SID) == source
    assert client.get(f"/api/projects/{PID}/setups/{draft['id']}").status_code == 200
    assert client.post(URL + "/save", json={**body, "request_id": "a" * 32}).json() == saved.json()


def test_options_keep_english_reasons_and_expose_stable_localization_codes(workflow):
    client, source = workflow
    data = client.get(URL, params={"source_rack_id": "source"}).json()
    targets = {r["id"]: r for r in data["targets"]}
    assert targets["source"]["reason_code"] == "source_rack"
    assert targets["source"]["reason"] == "This is the source rack"
    assert targets["fridge"]["reason_code"] == "fixture_mismatch"
    assert targets["empty"]["reason_code"] is None
    assert targets["empty"]["reason"] is None
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("change,code", [
    ("occupied", "occupied"), ("locked", "target_inaccessible"),
    ("source_locked", "source_inaccessible"), ("invalid_sku", "source_invalid_products"),
])
def test_invalid_racks_have_localizable_codes_without_changing_eligibility(workflow, change, code):
    client, source = workflow
    racks = source["store"]["racks"]
    if change == "occupied": racks[3]["slots"] = racks[2]["slots"]
    if change == "locked": racks[3]["locked_faces"] = [{"block": 0, "face": "S"}]
    if change == "source_locked": racks[2]["locked_faces"] = [{"block": 0, "face": "S"}]
    if change == "invalid_sku": racks[2]["slots"][0]["items"][0]["sku"] = " "
    write_json(setup_path(PID, SID), source)
    invalid_source = change in {"source_locked", "invalid_sku"}
    response = client.get(URL, params={} if invalid_source else {"source_rack_id": "source"})
    assert response.status_code == 200, response.text
    choices = response.json()["sources" if invalid_source else "targets"]
    selected = next(r for r in choices if r["id"] == ("source" if invalid_source else "empty"))
    assert selected["reason_code"] == code and selected["reason"]
    if invalid_source:
        refused = client.get(URL, params={"source_rack_id": "source"})
        assert refused.status_code == 422
        assert refused.json()["detail"] == selected["reason"]
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("patch", [
    {"target_rack_ids": []}, {"target_rack_ids": ["empty"] * 2}, {"target_rack_ids": ["source"]},
    {"target_rack_ids": ["unknown"]}, {"target_rack_ids": ["fridge"]}, {"target_rack_ids": ["in"]},
    {"target_rack_ids": [str(i) for i in range(101)]}, {"target_rack_ids": [""]},
    {"target_rack_ids": ["a" * 201]}, {"target_rack_ids": [None]}, {"target_rack_ids": [True]},
    {"source_rack_id": ""}, {"source_rack_id": "empty"}, {"source_rack_id": "missing"},
    {"currency": "usd"}, {"source_sha256": "nan"}, {"overwrite": True},
])
def test_invalid_choices_do_not_save_or_change_source(workflow, patch):
    client, source = workflow
    body = request(client, **patch)
    assert client.post(URL + "/preview", json=body).status_code == 422
    assert client.post(URL + "/save", json={**body, "request_id": "b" * 32}).status_code == 422
    assert not setup_path(PID, "setup_rackcopy_" + "b" * 32).exists()
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("change", ["products", "position", "currency"])
def test_stale_snapshot_is_rejected_before_writing(workflow, change):
    client, source = workflow
    body = request(client)
    if change == "products": source["store"]["racks"][2]["slots"][0]["items"][0]["price"] += 1
    if change == "position": source["store"]["racks"][3]["position"] = [6, 2]
    if change == "currency": source["store"]["currency"] = "KRW"
    write_json(setup_path(PID, SID), source)
    assert client.post(URL + "/preview", json=body).status_code == 409
    assert client.post(URL + "/save", json={**body, "request_id": "c" * 32}).status_code == 409
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("kind", ["stocked", "locked", "blocked", "shape", "source_locked"])
def test_incompatible_destination_rejects_entire_batch(workflow, kind):
    client, source = workflow
    racks = source["store"]["racks"]
    if kind == "stocked": racks[4]["slots"] = racks[2]["slots"]
    if kind == "locked": racks[4]["locked_faces"] = [{"block": 0, "face": "S"}]
    if kind == "blocked": racks.append(Rack(id="blocker", type="table", shape=[[1]], position=(8, 3)).model_dump(mode="json"))
    if kind == "shape": racks[4]["shape"] = [[1, 1]]
    if kind == "source_locked": racks[2]["locked_faces"] = [{"block": 0, "face": "W"}]
    write_json(setup_path(PID, SID), source)
    digest = client.get(URL).json()["source_sha256"]
    body = {"source_sha256": digest, "currency": "USD", "source_rack_id": "source", "target_rack_ids": ["empty", "empty2"], "request_id": "d" * 32}
    result = client.post(URL + "/save", json=body)
    assert result.status_code == 422, result.text
    assert not setup_path(PID, "setup_rackcopy_" + "d" * 32).exists()
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("price,field,status", [(-1, "price", 409), (float("inf"), "price", 409),
    (9007199254740992, "price", 409), (9007199254740992, "regular_price", 422)])
def test_invalid_or_unsafe_stored_prices_are_not_copied(workflow, price, field, status):
    client, source = workflow
    source["store"]["racks"][2]["slots"][0]["items"][0][field] = price
    write_json(setup_path(PID, SID), source)
    response = client.get(URL, params={"source_rack_id": "source"})
    assert response.status_code == status, response.text


def test_replay_keeps_later_edits_and_deleted_child_stays_deleted(workflow):
    client, source = workflow
    body = {**request(client), "request_id": "e" * 32}
    saved = client.post(URL + "/save", json=body); assert saved.status_code == 200
    path = setup_path(PID, saved.json()["setup_id"])
    draft = read_setup(PID, path.stem); draft["name"] = "Later edit"; write_json(path, draft)
    assert client.post(URL + "/save", json=body).json() == saved.json()
    assert read_setup(PID, path.stem)["name"] == "Later edit"
    assert client.post(URL + "/save", json={**body, "target_rack_ids": ["empty"]}).status_code == 409
    source2 = {**source, "id": "setup_second"}; write_json(setup_path(PID, "setup_second"), source2)
    assert client.post(URL.replace(SID, "setup_second") + "/save", json=body).status_code == 409
    path.unlink()
    assert client.post(URL + "/save", json=body).status_code == 409 and not path.exists()
    assert read_setup(PID, SID) == source


def test_busy_lock_and_lost_write_response_recover_same_identity(workflow, monkeypatch):
    from filelock import FileLock
    from store_emulator.application import rack_copy
    client, _ = workflow
    body = {**request(client), "request_id": "f" * 32}
    path = setup_path(PID, "setup_rackcopy_" + "f" * 32)
    with FileLock(path.parent / ".rack-copy.lock"):
        assert client.post(URL + "/save", json=body).status_code == 409
    real = rack_copy.write_json
    def lost(path, data):
        real(path, data)
        if path.name.startswith("setup_rackcopy_"):
            raise OSError("response interrupted after atomic write")
    monkeypatch.setattr(rack_copy, "write_json", lost)
    assert client.post(URL + "/save", json=body).status_code == 500
    assert path.exists()
    monkeypatch.setattr(rack_copy, "write_json", real)
    recovered = client.post(URL + "/save", json=body)
    assert recovered.status_code == 200 and recovered.json()["setup_id"] == path.stem
    assert len(list(path.parent.glob("setup_rackcopy_*.json"))) == 1


def test_interrupted_child_write_does_not_silently_recreate(workflow, monkeypatch):
    from store_emulator.application import rack_copy
    client, _ = workflow
    body = {**request(client), "request_id": "1" * 32}
    real = rack_copy.write_json
    def fail_child(path, data):
        if path.name.startswith("setup_rackcopy_"): raise OSError("disk full")
        real(path, data)
    monkeypatch.setattr(rack_copy, "write_json", fail_child)
    assert client.post(URL + "/save", json=body).status_code == 500
    monkeypatch.setattr(rack_copy, "write_json", real)
    assert client.post(URL + "/save", json=body).status_code == 409
    assert not setup_path(PID, "setup_rackcopy_" + "1" * 32).exists()


def test_one_hundred_destinations_and_unicode_ids(workflow):
    client, source = workflow
    source["store"]["grid_size"] = [40, 40]
    source["store"]["racks"] = source["store"]["racks"][:3] + [
        Rack(id=f"棚_{i}", type="shelf", shape=[[1]], position=(4 + i % 10 * 3, 4 + i // 10 * 3)).model_dump(mode="json") for i in range(100)]
    write_json(setup_path(PID, SID), source)
    body = request(client, target_rack_ids=[f"棚_{i}" for i in range(100)])
    result = client.post(URL + "/save", json={**body, "request_id": "2" * 32})
    assert result.status_code == 200 and result.json()["placements_added"] == 300, result.text
    saved = read_setup(PID, result.json()["setup_id"])
    assert len({p["sku"] for r in saved["store"]["racks"] for s in r["slots"] for p in s["items"]}) == 3


def test_rotated_multicell_reuses_absolute_faces_and_does_not_rotate_assortment(workflow):
    client, source = workflow
    racks = source["store"]["racks"]
    racks[2].update(shape=[[1, 1]], rotation=90)
    racks[2]["slots"][0]["block"] = 1  # southern end of the rotated footprint
    racks[3].update(shape=[[1], [1]])  # same world footprint, different rotation metadata
    racks[4].update(shape=[[1, 1]])  # incompatible horizontal footprint
    write_json(setup_path(PID, SID), source)
    body = request(client, target_rack_ids=["empty"])
    saved = client.post(URL + "/save", json={**body, "request_id": "3" * 32})
    assert saved.status_code == 200, saved.text
    result = read_setup(PID, saved.json()["setup_id"])["store"]["racks"][3]
    assert result["rotation"] == 0
    assert [s for s in result["slots"] if s["items"]] == racks[2]["slots"]
    assert client.post(URL + "/preview", json={**body, "target_rack_ids": ["empty2"]}).status_code == 422


def test_empty_layout_missing_source_and_unreachable_faces(workflow):
    client, source = workflow
    source["store"]["racks"][2]["slots"] = []
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).json()["sources"] == []
    assert client.get(URL, params={"source_rack_id": "source"}).status_code == 422
    assert client.get(URL.replace(SID, "setup_missing")).status_code == 404
    source["store"]["racks"].append(Rack(id="wall", type="shelf", shape=[[1] * 12], position=(0, 8)).model_dump(mode="json"))
    source["store"]["racks"][2]["slots"] = [Slot(block=0, face="S", items=[SlotItem(sku="X", name="X")]).model_dump(mode="json")]
    write_json(setup_path(PID, SID), source)
    assert "unreachable" in client.get(URL).json()["sources"][0]["reason"]


def test_bad_geometry_and_duplicate_identity_are_actionable(workflow):
    client, source = workflow
    source["store"]["racks"][3]["position"] = [2, 2]
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 422
    source["store"]["racks"][3]["position"] = [5, 2]
    source["store"]["racks"][3]["id"] = "source"
    write_json(setup_path(PID, SID), source)
    assert client.get(URL).status_code == 409


def test_building_context_and_replay_after_source_removal(workflow):
    client, source = workflow
    source["building"] = {"id": "building_1", "name": "Mall", "level": 2, "label": "Upper", "floor_count": 2}
    write_json(setup_path(PID, SID), source)
    body = {**request(client), "request_id": "4" * 32}
    saved = client.post(URL + "/save", json=body)
    assert saved.status_code == 200, saved.text
    assert read_setup(PID, saved.json()["setup_id"])["building"] == source["building"]
    setup_path(PID, SID).unlink()
    assert client.post(URL + "/save", json=body).json() == saved.json()


def test_exact_placement_budget_and_overflow_are_checked_before_write(workflow):
    client, source = workflow
    source["store"]["grid_size"] = [100, 100]
    items = [SlotItem(sku=f"item_{i}", name=f"Item {i}", price=i).model_dump(mode="json") for i in range(4)]
    shelves = [Rack(id="source" if i == 0 else f"target_{i}", type="shelf", shape=[[1] * 63], position=(1, 2 + 3 * i)).model_dump(mode="json") for i in range(26)]
    # 125 accessible sides × four levels × four items = 2,000 placements per rack,
    # within the new 100-tile geometry limit. Keep the exact 50,000/52,000 budget assertions.
    shelves[0]["slots"] = [{"block": b, "face": face, "level": level, "items": items}
                            for b in range(63) for face in ("N", "S") if face == "N" or b < 62
                            for level in range(1, 5)]
    source["store"]["racks"] = [Rack(id="in", type="entrance", shape=[[1]], position=(0, 99)).model_dump(mode="json"), *shelves]
    write_json(setup_path(PID, SID), source)
    body = request(client, target_rack_ids=[f"target_{i}" for i in range(1, 25)])
    allowed = client.post(URL + "/preview", json=body)
    assert allowed.status_code == 200 and allowed.json()["placements_added"] == 48000, allowed.text[:500]
    blocked = client.post(URL + "/save", json={**body, "target_rack_ids": [f"target_{i}" for i in range(1, 26)], "request_id": "5" * 32})
    assert blocked.status_code == 422 and "50,000" in blocked.text
    assert not setup_path(PID, "setup_rackcopy_" + "5" * 32).exists()


def test_preview_resolves_existing_project_image_without_rewriting_stored_products(workflow):
    import io
    from PIL import Image
    from store_emulator.application.storage.images import save_image
    client, source = workflow
    # Normal uploads live in the SKU manifest; persisted slot image_url is commonly null.
    item = source["store"]["racks"][2]["slots"][0]["items"][0]
    item["image_url"] = None
    write_json(setup_path(PID, SID), source)
    photo = io.BytesIO(); Image.new("RGB", (2, 2), "blue").save(photo, format="PNG")
    save_image(PID, item["sku"], photo.getvalue(), "synthetic.png")
    body = request(client)
    preview = client.post(URL + "/preview", json=body)
    assert preview.status_code == 200
    link = preview.json()["slots"][0]["items"][0]["image_url"]
    assert link and client.get(link).status_code == 200
    saved = client.post(URL + "/save", json={**body, "request_id": "6" * 32})
    assert saved.status_code == 200
    draft = read_setup(PID, saved.json()["setup_id"])
    assert draft["store"]["racks"][3]["slots"][1]["items"][0]["image_url"] is None
    opened = client.get(f"/api/projects/{PID}/setups/{draft['id']}").json()
    assert opened["store"]["racks"][3]["slots"][1]["items"][0]["image_url"] == link
    assert read_setup(PID, SID) == source


def test_source_edit_after_snapshot_is_preserved_and_child_uses_reviewed_values(workflow, monkeypatch):
    from store_emulator.application import rack_copy
    client, source = workflow
    body = {**request(client), "request_id": "7" * 32}
    real = rack_copy.copy_products
    def edit_after_snapshot(store, source_id, target_ids):
        result = real(store, source_id, target_ids)
        source["store"]["racks"][2]["slots"][0]["items"][0]["price"] = 999
        write_json(setup_path(PID, SID), source)
        return result
    monkeypatch.setattr(rack_copy, "copy_products", edit_after_snapshot)
    saved = client.post(URL + "/save", json=body)
    assert saved.status_code == 200
    assert read_setup(PID, SID) == source  # No lost update to the independently edited original.
    draft = read_setup(PID, saved.json()["setup_id"])
    assert draft["rack_copy_request"]["source_sha256"] == body["source_sha256"]
    assert draft["store"]["racks"][2]["slots"][0]["items"][0]["price"] == 231
    assert draft["store"]["racks"][3]["slots"][1]["items"][0]["price"] == 231


@pytest.mark.parametrize("currency", ["USD", "CAD", "CNY", "KRW", "JPY", "VND", "EUR", "GBP"])
def test_currency_and_mixed_sku_placement_values_survive_save_and_replay(workflow, currency):
    client, source = workflow
    source["store"]["currency"] = currency
    slots = source["store"]["racks"][2]["slots"]
    slots[0]["items"][0].update(price=9007199254740991, regular_price=9007199254740990)
    slots[1]["items"][0].update(sku=slots[0]["items"][0]["sku"], price=0, name="Different pack", promo="한정 ✨")
    write_json(setup_path(PID, SID), source)
    body = {**request(client, currency=currency), "request_id": "8" * 32}
    wrong = client.post(URL + "/save", json={**body, "currency": "JPY" if currency != "JPY" else "USD"})
    assert wrong.status_code == 409
    assert not setup_path(PID, "setup_rackcopy_" + "8" * 32).exists()
    saved = client.post(URL + "/save", json=body)
    assert saved.status_code == 200, saved.text
    child = read_setup(PID, saved.json()["setup_id"])
    assert child["store"]["currency"] == currency
    for rack in child["store"]["racks"][3:5]:
        assert [s for s in rack["slots"] if s["items"]] == slots
    # Recovery is about the accepted request, even when the source is now invalid.
    changed = {**source, "store": None}
    write_json(setup_path(PID, SID), changed)
    assert client.post(URL + "/save", json=body).json() == saved.json()
    assert read_setup(PID, SID) == changed


@pytest.mark.parametrize("stage", ["before_receipt", "after_receipt", "after_child"])
def test_write_failures_have_durable_and_unambiguous_retry_outcomes(workflow, monkeypatch, stage):
    from store_emulator.application import rack_copy
    client, source = workflow
    body = {**request(client), "request_id": "9" * 32}
    real = rack_copy.write_json
    def fail(path, data):
        receipt = path.parent.name == ".rack-copy"
        if receipt and stage == "before_receipt":
            raise OSError("No space before receipt write")
        real(path, data)
        if receipt and stage == "after_receipt" or not receipt and stage == "after_child":
            raise OSError("Lost write acknowledgement")
    monkeypatch.setattr(rack_copy, "write_json", fail)
    assert client.post(URL + "/save", json=body).status_code == 500
    monkeypatch.setattr(rack_copy, "write_json", real)
    retry = client.post(URL + "/save", json=body)
    assert retry.status_code == (409 if stage == "after_receipt" else 200), retry.text
    children = list(setup_path(PID, SID).parent.glob("setup_rackcopy_*.json"))
    assert len(children) == (0 if stage == "after_receipt" else 1)
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("field,value", [
    ("source_sha256", "a" * 64 + "\n"), ("source_sha256", "A" * 64),
    ("currency", "USD\n"), ("currency", "ＵＳＤ"),
    ("request_id", "a" * 32 + "\n"), ("request_id", "../" + "a" * 29),
    ("request_id", "a" * 31), ("request_id", "a" * 33),
    ("request_id", "Ａ" * 32), ("target_rack_ids", [1]),
])
def test_malformed_request_identities_cannot_create_a_child(workflow, field, value):
    client, source = workflow
    body = {**request(client), "request_id": "a" * 32, field: value}
    assert client.post(URL + "/save", json=body).status_code == 422
    assert not list(setup_path(PID, SID).parent.glob("setup_rackcopy_*.json"))
    assert read_setup(PID, SID) == source


@pytest.mark.parametrize("configured", [False, True])
def test_saved_variant_keeps_operations_and_retry_preserves_later_settings(workflow, configured):
    from store_emulator.application.setups import run_operations, save_layout_operations
    from store_emulator.domain.operations import OperationsConfig
    client, source = workflow[:2]
    operations = OperationsConfig(stock_per_facing=1, backroom_per_product=0,
                                 daily_delivery=False, crew=2, till_schedule={"09": 0}) if configured else None
    if operations is not None:
        source["operations"] = operations.model_dump(mode="json")
        write_json(setup_path(PID, SID), source)
    body = {**request(client), "request_id": "f" * 32}
    response = client.post(URL + "/save", json=body)
    assert response.status_code == 200, response.text
    child = response.json()["setup_id"]
    assert run_operations(PID, child, None, None) == operations
    assert run_operations(PID, child, None, False) is None
    assert read_setup(PID, SID) == source
    changed = OperationsConfig(stock_per_facing=99)
    save_layout_operations(PID, child, changed)
    assert client.post(URL + "/save", json=body).json() == response.json()
    assert run_operations(PID, child, None, None) == changed
