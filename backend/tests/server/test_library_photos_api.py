"""Real upload, assignment, saved layout and immutable image routes."""
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
PID, SID = "proj_67916afd", "setup_photo_fixture"
URL = f"/api/projects/{PID}/setups/{SID}/library-photos"


def png(color="blue"):
    data = io.BytesIO(); Image.new("RGB", (16, 20), color).save(data, format="PNG"); return data.getvalue()


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client:
        store = Store(id="store", name="Photos fixture", type="convenience", currency="USD", grid_size=(10, 10), racks=[
            Rack(id="in", type="entrance", shape=[[1]], position=(0, 9)),
            Rack(id="out", type="exit", shape=[[1]], position=(9, 9)),
            Rack(id="shelf", type="shelf", shape=[[1]], position=(2, 2), slots=[Slot(block=0, face="S", level=1, items=[
                SlotItem(sku="茶_한글", name="Tea", price=231, regular_price=299, promo="Local"),
                SlotItem(sku="tea2", name="Tea", price=0), SlotItem(sku="茶_한글", name="Tea", price=231)])]),
        ])
        source = new_setup_data("Source", None, store.model_dump(mode="json")); source["id"] = SID
        write_json(setup_path(PID, SID), source)
        uploaded = client.post(f"/api/projects/{PID}/lab/packages", files={"image": ("tea.png", png(), "image/png")}, data={"name": "Tea photo", "sku": "茶_한글", "remove_background": "false"})
        assert uploaded.status_code == 200, uploaded.text
        yield client, source, uploaded.json()


def request(client, **patch):
    response = client.get(URL); assert response.status_code == 200, response.text
    options = response.json(); asset = options["assets"][0]
    return {"source_sha256": options["source_sha256"], "assignments": [{"sku": "茶_한글", "asset_id": asset["asset_id"], "version": asset["version"]}], "replace_existing": False, **patch}


def test_upload_preview_save_open_original_preserved(workflow):
    client, source, asset = workflow; body = request(client)
    preview = client.post(URL + "/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["changed_placements"] == 2
    url = preview.json()["changes"][0]["image_url"]
    assert client.get(url).content == png()
    response = client.post(URL + "/save", json={**body, "request_id": "a" * 32})
    assert response.status_code == 200, response.text
    saved = read_setup(PID, response.json()["setup_id"])
    assert saved["parentId"] == SID and saved["status"] == "draft"
    items = saved["store"]["racks"][2]["slots"][0]["items"]
    assert [i["image_url"] for i in items] == [url, None, url]
    for i in items: i["image_url"] = None
    assert saved["store"] == source["store"] and read_setup(PID, SID) == source
    assert client.get(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}").status_code == 200
    assert client.post(URL + "/save", json={**body, "request_id": "a" * 32}).json() == response.json()


def test_saved_image_survives_library_delete_and_unrelated_manifest(workflow):
    client, _, asset = workflow; body = request(client)
    result = client.post(URL + "/save", json={**body, "request_id": "b" * 32}).json()
    assert client.delete(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}").status_code == 204
    assert client.post(f"/api/projects/{PID}/sku-images", params={"sku": "tea2"}, files={"file": ("red.png", png("red"), "image/png")}).status_code == 200
    loaded = client.get(f"/api/projects/{PID}/setups/{result['setup_id']}").json()
    url = loaded["store"]["racks"][2]["slots"][0]["items"][0]["image_url"]
    assert url and client.get(url).content == png()
    assert client.post(URL + "/save", json={**body, "request_id": "b" * 32}).json() == result


@pytest.mark.parametrize("change", ["keep", "replace", "clear"])
def test_bulk_product_rows_preserve_or_explicitly_replace_reviewed_images(workflow, change):
    client, _, _ = workflow
    result = client.post(URL + "/save", json={**request(client), "request_id": "e" * 32}).json()
    sid = result["setup_id"]
    saved = read_setup(PID, sid)
    rows = [{"rack_id": rack["id"], "block": slot["block"], "face": slot["face"], "level": slot["level"], **item}
            for rack in saved["store"]["racks"] for slot in rack["slots"] for item in slot["items"]]
    expected = rows[0]["image_url"]
    if change == "replace":
        image = client.post(f"/api/projects/{PID}/sku-images", params={"sku": "茶_한글"},
                            files={"file": ("red.png", png("red"), "image/png")})
        assert image.status_code == 200, image.text
        expected = image.json()["url"]
    elif change == "clear":
        expected = None
    for row in rows:
        if row["sku"] == "茶_한글":
            row["image_url"] = expected
    response = client.put(f"/api/projects/{PID}/setups/{sid}/slots", json={"slots": rows})
    assert response.status_code == 200, response.text
    items = read_setup(PID, sid)["store"]["racks"][2]["slots"][0]["items"]
    assert [item["image_url"] for item in items] == [expected, None, expected]
    assert [item["regular_price"] for item in items] == [299, 0, 0]
    if expected:
        assert client.get(expected).content == png("red" if change == "replace" else "blue")


def test_existing_photo_requires_explicit_replacement(workflow):
    client, _, _ = workflow
    assert client.post(f"/api/projects/{PID}/sku-images", params={"sku": "茶_한글"}, files={"file": ("red.png", png("red"), "image/png")}).status_code == 200
    body = request(client); assert client.post(URL + "/preview", json=body).status_code == 422
    body["replace_existing"] = True
    result = client.post(URL + "/save", json={**body, "request_id": "c" * 32})
    assert result.status_code == 200, result.text
    saved = client.get(f"/api/projects/{PID}/setups/{result.json()['setup_id']}").json()
    source = client.get(f"/api/projects/{PID}/setups/{SID}").json()
    saved_url = saved["store"]["racks"][2]["slots"][0]["items"][0]["image_url"]
    original_url = source["store"]["racks"][2]["slots"][0]["items"][0]["image_url"]
    assert client.get(saved_url).content == png() and client.get(original_url).content == png("red")

# Separate boundary phase: run after the initial three integration checks.
@pytest.mark.parametrize("patch", [
    {"assignments": []}, {"assignments": None}, {"replace_existing": 1}, {"replace_existing": "true"},
    {"source_sha256": "NaN"}, {"extra": True},
])
def test_invalid_payloads_leave_original_unchanged(workflow, patch):
    client, source, _ = workflow
    response = client.post(URL + "/save", json={**request(client), **patch, "request_id": "d" * 32})
    assert response.status_code == 422
    assert read_setup(PID, SID) == source and not setup_path(PID, "setup_photos_" + "d" * 32).exists()


@pytest.mark.parametrize("patch", [
    {"sku": ""}, {"sku": "  "}, {"sku": True}, {"sku": 0}, {"sku": "x" * 201}, {"sku": "missing"},
    {"asset_id": "../secret"}, {"asset_id": ""}, {"version": "infinity"}, {"version": None},
])
def test_bad_assignment_rejected_before_snapshot(workflow, patch):
    from pathlib import Path
    client, source, _ = workflow; body = request(client)
    body["assignments"][0].update(patch)
    assert client.post(URL + "/preview", json=body).status_code == 422
    assert not (Path(".data") / PID / "product_photos").exists()
    assert read_setup(PID, SID) == source


def test_duplicate_sku_is_not_silently_overwritten(workflow):
    client, _, _ = workflow; body = request(client)
    body["assignments"] *= 2
    assert client.post(URL + "/preview", json=body).status_code == 422


@pytest.mark.parametrize("change", ["name", "price", "currency", "image_manifest", "asset_name", "asset_link", "asset_bytes", "asset_delete"])
def test_stale_layout_or_library_never_saves(workflow, change):
    from store_emulator.application.shelf_lab import package_path
    client, source, asset = workflow; body = request(client)
    if change in {"name", "price"}:
        source["store"]["racks"][2]["slots"][0]["items"][0][change] = "Changed" if change == "name" else 999
    elif change == "currency": source["store"]["currency"] = "KRW"
    elif change == "image_manifest":
        client.post(f"/api/projects/{PID}/sku-images", params={"sku": "tea2"}, files={"file": ("r.png", png("red"), "image/png")})
    elif change == "asset_bytes": package_path(PID, asset["asset_id"]).write_bytes(png("red"))
    elif change == "asset_delete": client.delete(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}")
    else: client.patch(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}", json={"name" if change == "asset_name" else "sku": "changed"})
    write_json(setup_path(PID, SID), source)
    response = client.post(URL + "/save", json={**body, "request_id": "e" * 32})
    assert response.status_code in {404, 409}, response.text
    assert not setup_path(PID, "setup_photos_" + "e" * 32).exists()


def test_min_max_batch_counts_and_duplicate_product_names(workflow):
    client, source, _ = workflow
    all_items = [SlotItem(sku=f"sku{i}", name="Same name", price=0 if i == 0 else 9007199254740991) for i in range(101)]
    source["store"]["racks"] = source["store"]["racks"][:2] + [
        Rack(id=f"r{i}", type="shelf", shape=[[1]], position=(i % 8, i // 8), slots=[
            Slot(block=0, face="S", items=all_items[i * 4:i * 4 + 4])]).model_dump(mode="json") for i in range(26)]
    write_json(setup_path(PID, SID), source)
    body = request(client); choice = body["assignments"][0]
    body["assignments"] = [{**choice, "sku": f"sku{i}"} for i in range(100)]
    response = client.post(URL + "/save", json={**body, "request_id": "f" * 32})
    assert response.status_code == 200, response.text
    assert response.json()["changed_placements"] == 100
    body["assignments"].append({**choice, "sku": "sku100"})
    assert client.post(URL + "/preview", json=body).status_code == 422
    saved = [item for rack in read_setup(PID, response.json()["setup_id"])["store"]["racks"] for slot in rack["slots"] for item in slot["items"]]
    assert saved[0]["price"] == 0 and saved[1]["price"] == 9007199254740991 and saved[100]["image_url"] is None


def test_byte_limits_including_exact_boundary(workflow, monkeypatch):
    from store_emulator.application import library_photos as service
    client, _, _ = workflow; body = request(client); size = len(png())
    monkeypatch.setattr(service, "MAX_PHOTO_BYTES", size)
    monkeypatch.setattr(service, "MAX_BATCH_BYTES", size)
    assert client.post(URL + "/preview", json=body).status_code == 200
    monkeypatch.setattr(service, "MAX_BATCH_BYTES", size - 1)
    assert client.post(URL + "/preview", json=body).status_code == 413
    monkeypatch.setattr(service, "MAX_PHOTO_BYTES", size - 1)
    assert client.get(URL).status_code == 413


def test_library_500_limit(workflow):
    from store_emulator.application.shelf_lab import package_path
    client, _, asset = workflow; path = package_path(PID, asset["asset_id"])
    for n in range(499):
        (path.parent / f"pkg_{n}.png").write_bytes(png())
    assert len(client.get(URL).json()["assets"]) == 500
    (path.parent / "pkg_over.png").write_bytes(png())
    assert client.get(URL).status_code == 413


def test_lock_conflict_safe_retry_and_request_reuse(workflow):
    from filelock import FileLock
    from store_emulator.application.setups import setup_lock_path
    client, source, _ = workflow; body = {**request(client), "request_id": "1" * 32}
    with FileLock(setup_lock_path(PID, SID).with_name(".library-photos.lock")):
        assert client.post(URL + "/save", json=body).status_code == 409
    result = client.post(URL + "/save", json=body); assert result.status_code == 200
    changed = {**body, "replace_existing": True}
    assert client.post(URL + "/save", json=changed).status_code == 409
    other = {**source, "id": "setup_other"}; write_json(setup_path(PID, "setup_other"), other)
    assert client.post(URL.replace(SID, "setup_other") + "/save", json=body).status_code == 409
    setup_path(PID, result.json()["setup_id"]).unlink()
    assert client.post(URL + "/save", json=body).status_code == 409


def test_interrupted_write_does_not_duplicate_layout(workflow, monkeypatch):
    from store_emulator.application import library_photos as service
    client, source, _ = workflow; body = {**request(client), "request_id": "2" * 32}
    original = service.write_json
    def fail(path, data):
        if path.stem.startswith("setup_photos_"): raise OSError("disk full")
        original(path, data)
    monkeypatch.setattr(service, "write_json", fail)
    assert client.post(URL + "/save", json=body).status_code == 500
    monkeypatch.setattr(service, "write_json", original)
    assert client.post(URL + "/save", json=body).status_code == 409
    assert read_setup(PID, SID) == source


def test_corrupt_snapshot_is_repaired_from_verified_library_bytes(workflow):
    from pathlib import Path
    client, _, _ = workflow; body = request(client)
    preview = client.post(URL + "/preview", json=body).json(); url = preview["changes"][0]["image_url"]
    (Path(".data") / PID / "product_photos" / (url.rsplit("/", 1)[1] + ".png")).write_bytes(b"interrupted disk data")
    assert client.post(URL + "/preview", json=body).status_code == 200
    assert client.get(url).content == png()


def test_corrupt_asset_metadata_is_actionable_not_internal_error(workflow):
    from store_emulator.application.shelf_lab import package_path
    client, _, asset = workflow
    package_path(PID, asset["asset_id"]).with_suffix(".json").write_text('[]')
    assert client.get(URL).status_code == 409


def test_resource_scope_and_bad_digest(workflow):
    client, _, _ = workflow
    assert client.get(URL.replace(PID, "no_such_project")).status_code == 404
    assert client.get(f"/api/projects/{PID}/product-photo-files/not-a-hash").status_code == 422
    assert client.get(f"/api/projects/{PID}/product-photo-files/" + "0" * 64).status_code == 404


def test_empty_layout_library_and_corrupt_image(workflow):
    from store_emulator.application.shelf_lab import package_path
    client, source, asset = workflow
    source["store"]["racks"][2]["slots"] = []; write_json(setup_path(PID, SID), source)
    assert client.get(URL).json()["products"] == []
    package_path(PID, asset["asset_id"]).write_bytes(b"not a PNG")
    assert client.get(URL).status_code == 409
    client.delete(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}")
    assert client.get(URL).json()["assets"] == []


def test_asset_lock_and_concurrent_same_save_are_safe(workflow):
    from concurrent.futures import ThreadPoolExecutor
    from filelock import FileLock
    from store_emulator.application.shelf_lab import package_path
    client, source, asset = workflow; body = {**request(client), "request_id": "3" * 32}
    with FileLock(package_path(PID, asset["asset_id"]).with_suffix(".lock")):
        assert client.post(URL + "/save", json=body).status_code == 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(URL + "/save", json=body), range(2)))
    assert all(r.status_code in {200, 409} for r in responses)
    result = client.post(URL + "/save", json=body); assert result.status_code == 200
    assert len(list(setup_path(PID, SID).parent.glob('setup_photos_*.json'))) == 1
    assert read_setup(PID, SID) == source


def test_invalid_second_assignment_does_not_apply_first(workflow):
    from pathlib import Path
    client, source, _ = workflow; body = request(client)
    body["assignments"].append({**body["assignments"][0], "sku": "missing"})
    assert client.post(URL + "/save", json={**body, "request_id": "4" * 32}).status_code == 422
    assert not (Path('.data') / PID / 'product_photos').exists()
    assert read_setup(PID, SID) == source


def test_unselected_manifest_photo_refreshes_but_selected_snapshot_stays_fixed(workflow):
    client, _, _ = workflow
    client.post(f"/api/projects/{PID}/sku-images", params={"sku": "tea2"}, files={"file": ("red.png", png("red"), "image/png")})
    result = client.post(URL + "/save", json={**request(client), "request_id": "5" * 32}).json()
    changed = client.post(f"/api/projects/{PID}/sku-images", params={"sku": "tea2"}, files={"file": ("green.png", png("green"), "image/png")}).json()
    loaded = client.get(f"/api/projects/{PID}/setups/{result['setup_id']}").json()
    items = loaded["store"]["racks"][2]["slots"][0]["items"]
    assert items[1]["image_url"] == changed["url"]
    assert '/product-photo-files/' in items[0]["image_url"]
    assert client.get(items[0]["image_url"]).content == png()


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
